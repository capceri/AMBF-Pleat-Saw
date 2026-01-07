"""
Web Monitoring Dashboard Service
Provides real-time monitoring and manual control for commissioning and troubleshooting.
"""

import logging
import subprocess
import threading
import time
from typing import Dict, Any, Optional, Callable
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

MM_PER_INCH = 25.4
DEFAULT_M3_OFFSET_MM = 220.0


class WebMonitor:
    """
    Web-based monitoring and control dashboard.

    Features:
    - Real-time system status display
    - Live I/O monitoring
    - Motor status and position display
    - Manual control commands for testing
    - Alarm history and statistics
    - WebSocket for real-time updates
    """

    def __init__(
        self,
        io_poller,
        axis_gateway,
        supervisor,
        nextion_bridge,
        modbus_master,
        config: Dict[str, Any],
        port: int = 5000,
        host: str = '0.0.0.0',
        update_rate_hz: float = 10.0,
    ):
        """
        Initialize web monitor.

        Args:
            io_poller: IOPoller instance
            axis_gateway: AxisGateway instance
            supervisor: Supervisor instance
            nextion_bridge: NextionBridge instance
            modbus_master: ModbusMaster instance
            config: Configuration dictionary
            port: Web server port
            host: Host to bind to
            update_rate_hz: Real-time update frequency
        """
        self.io = io_poller
        self.axis = axis_gateway
        self.supervisor = supervisor
        self.hmi = nextion_bridge
        self.modbus = modbus_master
        self.config = config

        self.port = port
        self.host = host
        self.update_interval = 1.0 / update_rate_hz

        # Flask app
        self.app = Flask(
            __name__,
            template_folder='../web/templates',
            static_folder='../web/static'
        )
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins='*',
            async_mode='threading'
        )

        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._update_thread: Optional[threading.Thread] = None

        # Track manual jog state for limit enforcement
        self._manual_jog_dir: Optional[str] = None  # 'fwd', 'rev', or None

        # Initialization errors for diagnostics
        self.init_errors = []

        # Setup routes and handlers
        self._setup_routes()
        self._setup_socketio()

        if hasattr(self.axis, 'set_status_callback'):
            self.axis.set_status_callback(self._emit_status_message)

        logger.info("Web monitor initialized on http://%s:%d", host, port)

    def _setup_routes(self):
        """Setup Flask HTTP routes."""

        @self.app.route('/')
        def index():
            """Main operator interface (touchscreen)."""
            return render_template('operator.html')

        @self.app.route('/engineering')
        def engineering():
            """Deprecated engineering route -> redirect to main dashboard."""
            return redirect('/dashboard', code=302)

        @self.app.route('/dashboard')
        def dashboard():
            """Commissioning dashboard page."""
            return render_template('dashboard.html')

        @self.app.route('/api/status')
        def api_status():
            """Get current system status."""
            return jsonify(self._get_system_status())

        @self.app.route('/api/inputs')
        def api_inputs():
            """Get current input states."""
            return jsonify(self._get_input_states())

        @self.app.route('/api/input_overrides')
        def api_input_overrides():
            """Get current input override states."""
            return jsonify(self._get_input_overrides())

        @self.app.route('/api/outputs')
        def api_outputs():
            """Get current output states."""
            return jsonify(self._get_output_states())

        @self.app.route('/api/motors')
        def api_motors():
            """Get motor status and positions."""
            return jsonify(self._get_motor_status())

        @self.app.route('/api/statistics')
        def api_statistics():
            """Get system statistics."""
            return jsonify(self._get_statistics())

        @self.app.route('/api/config')
        def api_config():
            """Get current configuration."""
            return jsonify({
                'motion': self.config.get('motion', {}),
                'io_map': self.config.get('io_map', {}),
            })

        @self.app.route('/api/engineering_params')
        def api_engineering_params():
            """Get current engineering parameters (for dashboard persistence)."""
            offset_mm = 0.0
            if self.axis and hasattr(self.axis, 'get_m3_offset'):
                try:
                    offset_mm = float(self.axis.get_m3_offset())
                except Exception:
                    offset_mm = 0.0

            if self.supervisor:
                return jsonify({
                    'm1_rpm': self.supervisor.m1_rpm,
                    'm2_vel_fwd_mm_s': self.supervisor.m2_vel_fwd_mm_s,
                    'm2_vel_rev_mm_s': self.supervisor.m2_vel_rev_mm_s,
                    'm2_fwd_timeout': self.supervisor.m2_fwd_timeout,
                    'm2_rev_timeout': self.supervisor.m2_rev_timeout,
                    'm3_offset_mm': offset_mm,
                })
            else:
                # Return defaults from config if supervisor not available
                return jsonify({
                    'm1_rpm': self.config['motion']['m1_blade']['rpm_default'],
                    'm2_vel_fwd_mm_s': self.config['motion']['m2_fixture']['default_speed_mm_s'],
                    'm2_vel_rev_mm_s': self.config['motion']['m2_fixture']['default_speed_mm_s'],
                    'm2_fwd_timeout': self.config['motion']['m2_fixture']['timeout_fwd_s'],
                    'm2_rev_timeout': self.config['motion']['m2_fixture']['timeout_rev_s'],
                    'm3_offset_mm': offset_mm,
                })

        @self.app.route('/api/wifi/scan')
        def api_wifi_scan():
            """Scan for nearby WiFi networks."""
            networks, error = self._scan_wifi_networks()
            return jsonify({
                'success': error is None,
                'networks': networks,
                'error': error,
            })

        @self.app.route('/api/wifi/connect', methods=['POST'])
        def api_wifi_connect():
            """Connect to a WiFi network using nmcli."""
            payload = request.get_json(silent=True) or {}
            ssid = str(payload.get('ssid', '')).strip()
            password = str(payload.get('password', '') or '')

            if not ssid:
                return jsonify({
                    'success': False,
                    'error': 'SSID is required.',
                }), 400

            result, error = self._connect_wifi(ssid, password)
            if error:
                return jsonify({
                    'success': False,
                    'error': error,
                }), 500

            return jsonify({
                'success': True,
                'message': result,
            })

        @self.app.route('/api/diagnostics')
        def api_diagnostics():
            """Get diagnostic information including connection status and errors."""
            # Check connection status for each hardware component
            modbus_connected = False
            nextion_connected = False

            # Check Modbus connection
            modbus_info = {
                'connected': False,
                'status': 'Disconnected',
                'description': 'RS-485 Modbus RTU (I/O and Motors)',
                'device': 'Not found'
            }

            if self.modbus is not None:
                try:
                    modbus_connected = hasattr(self.modbus, 'is_connected') and self.modbus.is_connected
                    modbus_info['connected'] = modbus_connected
                    modbus_info['status'] = 'Connected' if modbus_connected else 'Disconnected'
                    if modbus_connected and hasattr(self.modbus, 'detected_port') and self.modbus.detected_port:
                        modbus_info['device'] = self.modbus.detected_port
                    elif hasattr(self.modbus, 'port_candidates'):
                        modbus_info['device'] = f"Tried: {', '.join(self.modbus.port_candidates)}"
                except Exception:
                    modbus_connected = False

            # Check Nextion connection - DISABLED (Nextion not part of project)
            nextion_connected = False
            # if self.hmi is not None:
            #     try:
            #         nextion_connected = hasattr(self.hmi, '_connected') and self.hmi._connected
            #     except Exception:
            #         nextion_connected = False

            return jsonify({
                'init_errors': self.init_errors,
                'connections': {
                    'modbus': modbus_info,
                    'nextion': {
                        'connected': False,
                        'status': 'Disabled',
                        'description': 'Nextion HMI Display (not part of project)'
                    }
                },
                'services_status': {
                    'io_poller': self.io is not None,
                    'axis_gateway': self.axis is not None,
                    'supervisor': self.supervisor is not None,
                    'web_monitor': True  # Always true if we're responding
                },
                'timestamp': time.time()
            })

        @self.app.route('/api/command', methods=['POST'])
        def api_command():
            """Execute manual control command."""
            try:
                data = request.get_json()
                result = self._execute_command(data)
                return jsonify(result)
            except Exception as e:
                logger.error(f"Command execution error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

    def _setup_socketio(self):
        """Setup WebSocket event handlers."""

        @self.socketio.on('connect')
        def handle_connect():
            """Client connected."""
            logger.info("Client connected to WebSocket")
            emit('status', {'message': 'Connected to Pleat Saw Controller'})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnected."""
            logger.info("Client disconnected from WebSocket")

        @self.socketio.on('request_update')
        def handle_request_update():
            """Client requests immediate update."""
            self._broadcast_update()

        @self.socketio.on('command')
        def handle_command(data):
            """Execute command from WebSocket."""
            try:
                result = self._execute_command(data)
                emit('command_result', result)
            except Exception as e:
                logger.error(f"WebSocket command error: {e}")
                emit('command_result', {'success': False, 'error': str(e)})

    def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        try:
            sup_state = self.supervisor.get_state() if self.supervisor else 'UNKNOWN'
            sup_stats = self.supervisor.get_statistics() if self.supervisor else {}

            # Get safety and light curtain status
            inputs = self.io.get_all_inputs() if self.io else {}
            safety_ok = inputs.get('safety', False)
            light_curtain_ok = inputs.get('light_curtain', False)

            return {
                'state': sup_state,
                'safety': 'READY' if safety_ok else 'NOT_READY',
                'light_curtain': 'OK' if light_curtain_ok else 'BLOCKED',
                'paused': 'PAUSED' if (self.supervisor and hasattr(self.supervisor, 'is_paused') and self.supervisor.is_paused) else 'RUNNING',
                'alarm': self.supervisor.current_alarm if self.supervisor else None,
                'cycle_count': sup_stats.get('cycles_completed', 0),
                'pause_events': sup_stats.get('pause_events_total', 0),
                'uptime': time.time() - self.supervisor._start_time if self.supervisor and hasattr(self.supervisor, '_start_time') else 0,
                'timestamp': time.time(),
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}

    def _get_input_states(self) -> Dict[str, Any]:
        """Get all input states."""
        try:
            if self.io:
                return {
                    'inputs': self.io.get_all_inputs(),
                    'timestamp': time.time(),
                }
            return {'error': 'IO poller not available'}
        except Exception as e:
            logger.error(f"Error getting inputs: {e}")
            return {'error': str(e)}

    def _get_input_overrides(self) -> Dict[str, Any]:
        """Get all input override states."""
        try:
            if self.io:
                overrides = self.io.get_input_overrides()
                # Include detailed info for each input
                input_details = {}
                for name in overrides.keys():
                    input_details[name] = self.io.get_input_with_override_info(name)

                return {
                    'overrides': overrides,
                    'details': input_details,
                    'timestamp': time.time(),
                }
            return {'error': 'IO poller not available'}
        except Exception as e:
            logger.error(f"Error getting input overrides: {e}")
            return {'error': str(e)}

    def _get_output_states(self) -> Dict[str, Any]:
        """Get all output states."""
        try:
            if self.io:
                return {
                    'outputs': self.io.get_all_outputs(),
                    'timestamp': time.time(),
                }
            return {'error': 'IO poller not available'}
        except Exception as e:
            logger.error(f"Error getting outputs: {e}")
            return {'error': str(e)}

    def _get_motor_status(self) -> Dict[str, Any]:
        """Get motor status for all axes."""
        try:
            if not self.axis:
                return {'error': 'Axis gateway not available'}

            m1_status = self.axis.m1_get_status()
            m2_status = self.axis.m2_get_status()
            m3_status = self.axis.m3_get_status()

            # Handle None responses from axis gateway when hardware disconnected
            m3_backstop = {}
            position_mm = None
            offset_mm = DEFAULT_M3_OFFSET_MM

            if hasattr(self.axis, 'get_m3_offset'):
                try:
                    offset_mm = float(self.axis.get_m3_offset())
                except Exception:
                    offset_mm = DEFAULT_M3_OFFSET_MM

            if m3_status and isinstance(m3_status, dict):
                m3_backstop = {**m3_status}
                pos_in = m3_status.get('position_in')
                if pos_in is not None:
                    position_mm = pos_in * MM_PER_INCH

            # Fallback to axis cached position if status didn't include telemetry
            if position_mm is None:
                m3_pos = self.axis.m3_get_position()
                if m3_pos is not None:
                    position_mm = m3_pos
                else:
                    # Use cached value to avoid dropping to zero when temporarily unavailable
                    position_mm = getattr(self.axis, 'm3_position_mm', None)

            raw_position_mm = position_mm if position_mm is not None else 0.0
            m3_backstop['raw_position_mm'] = raw_position_mm
            m3_backstop['offset_mm'] = offset_mm
            m3_backstop['position_mm'] = raw_position_mm + offset_mm

            # Build M2 fixture view with IO-backed limit switches
            m2_fixture = {
                'in_motion': False,
                'at_s2': False,
                'at_s3': False,
                'at_s4': False,
                'fault': False,
            }

            if m2_status and isinstance(m2_status, dict):
                m2_fixture['in_motion'] = m2_status.get('in_motion', False)
                m2_fixture['at_s2'] = m2_status.get('at_s2', False)
                m2_fixture['at_s3'] = m2_status.get('at_s3', False)
                m2_fixture['at_s4'] = m2_status.get('at_s4', False)
                m2_fixture['fault'] = m2_status.get('fault', False)

            if self.io:
                # Use IO poller inputs if available
                m2_fixture['at_s2'] = bool(self.io.get_input('sensor2')) if self.io.get_input('sensor2') is not None else m2_fixture['at_s2']
                m2_fixture['at_s3'] = bool(self.io.get_input('sensor3')) if self.io.get_input('sensor3') is not None else m2_fixture['at_s3']
                # Optional S4 input if wired/mapped
                s4_val = self.io.get_input('sensor4') if hasattr(self.io, 'get_input') else None
                if s4_val is not None:
                    m2_fixture['at_s4'] = bool(s4_val)

            return {
                'm1_blade': m1_status if m1_status else {'error': 'Not available'},
                'm2_fixture': m2_fixture,
                'm3_backstop': m3_backstop if m3_backstop else {'error': 'Not available'},
                'timestamp': time.time(),
            }
        except Exception as e:
            logger.error(f"Error getting motor status: {e}")
            return {'error': str(e)}

    def _get_statistics(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            stats = {}

            if self.modbus:
                stats['modbus'] = self.modbus.get_statistics()

            if self.io:
                stats['io'] = self.io.get_statistics()

            if self.supervisor:
                stats['supervisor'] = self.supervisor.get_statistics()

            stats['timestamp'] = time.time()
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'error': str(e)}

    def _run_nmcli_command(self, args, timeout: float, use_sudo: bool = False):
        if use_sudo:
            args = ['sudo', '-n'] + args

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return None, 'nmcli not found on system.'
        except subprocess.TimeoutExpired:
            return None, 'nmcli command timed out.'

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or 'nmcli command failed.'
            return None, error_msg

        return result.stdout.strip(), None

    def _scan_wifi_networks(self):
        nmcli_args = [
            'nmcli',
            '-f',
            'SSID,SIGNAL,SECURITY,IN-USE',
            '-m',
            'multiline',
            'dev',
            'wifi',
            'list',
            '--rescan',
            'yes',
        ]

        output, error = self._run_nmcli_command(
            nmcli_args,
            timeout=15,
            use_sudo=True,
        )
        if error and 'sudo' in error.lower():
            output, error = self._run_nmcli_command(
                nmcli_args,
                timeout=15,
                use_sudo=False,
            )
        if error:
            logger.warning("WiFi scan failed: %s", error)
            return [], error

        networks = []
        current = {}

        for line in output.splitlines():
            if not line.strip():
                if current:
                    networks.append(current)
                    current = {}
                continue
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip().lower()
            if key == 'ssid' and current:
                networks.append(current)
                current = {}
            current[key] = value.strip()

        if current:
            networks.append(current)

        cleaned = []
        for entry in networks:
            ssid = entry.get('ssid', '')
            if ssid == '--':
                ssid = ''
            signal_raw = entry.get('signal', '')
            try:
                signal = int(signal_raw)
            except (TypeError, ValueError):
                signal = None
            security = entry.get('security', '')
            in_use_value = entry.get('in-use', '').strip().lower()
            in_use = in_use_value in ('*', 'yes', 'true', '1')
            cleaned.append({
                'ssid': ssid,
                'signal': signal,
                'security': security,
                'in_use': in_use,
                'hidden': ssid == '',
            })

        deduped = {}
        for entry in cleaned:
            key = entry['ssid'] if entry['ssid'] else f"__hidden_{len(deduped)}"
            if key not in deduped:
                deduped[key] = entry
                continue
            existing = deduped[key]
            if entry['in_use'] and not existing['in_use']:
                deduped[key] = entry
                continue
            if existing['in_use'] and not entry['in_use']:
                continue
            if (entry['signal'] or 0) > (existing['signal'] or 0):
                deduped[key] = entry

        final_list = list(deduped.values())
        final_list.sort(key=lambda item: (
            not item['in_use'],
            -(item['signal'] or 0),
            item['ssid'].lower() if item['ssid'] else '',
        ))

        return final_list, None

    def _connect_wifi(self, ssid: str, password: str):
        args = ['nmcli', 'dev', 'wifi', 'connect', ssid]
        if password:
            args += ['password', password]

        output, error = self._run_nmcli_command(args, timeout=30, use_sudo=True)
        if error and 'sudo' in error.lower():
            output, error = self._run_nmcli_command(args, timeout=30, use_sudo=False)
        if error:
            logger.warning("WiFi connect failed for %s: %s", ssid, error)
            return None, error

        return output or f'Connected to {ssid}.', None

    def _execute_command(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a manual control command.

        Args:
            data: Command data with 'command' and optional parameters

        Returns:
            Result dictionary with success status
        """
        command = data.get('command')
        params = data.get('params', {})

        logger.info(f"Executing command: {command} with params: {params}")

        try:
            if command == 'start_cycle':
                # Trigger start
                if self.supervisor:
                    self.supervisor.handle_hmi_command({'cmd': 'START'})
                return {'success': True, 'message': 'Cycle started'}

            elif command == 'stop_cycle':
                # Emergency stop
                if self.supervisor:
                    self.supervisor.handle_hmi_command({'cmd': 'STOP'})
                return {'success': True, 'message': 'Cycle stopped'}

            elif command == 'reset_alarms':
                # Reset alarms
                if self.supervisor:
                    self.supervisor.reset_alarms()
                return {'success': True, 'message': 'Alarms reset'}

            elif command == 'set_output':
                # Set single output
                output_name = params.get('name')
                state = params.get('state', False)
                if self.io and output_name:
                    self.io.set_output(output_name, state)
                    return {'success': True, 'message': f'Output {output_name} set to {state}'}
                return {'success': False, 'error': 'Invalid parameters'}

            elif command == 'm1_start':
                # Start blade motor
                rpm = params.get('rpm', 3500)
                if self.axis:
                    self.axis.m1_start(rpm)
                    return {'success': True, 'message': f'M1 started at {rpm} RPM'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm1_stop':
                # Stop blade motor
                if self.axis:
                    self.axis.m1_stop()
                    return {'success': True, 'message': 'M1 stopped'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'set_m1_rpm':
                # Set M1 RPM for automatic cycles
                rpm = params.get('rpm', 700)
                if self.supervisor:
                    success = self.supervisor.set_m1_rpm(int(rpm))
                    if success:
                        return {'success': True, 'message': f'M1 auto RPM set to {rpm}'}
                    return {'success': False, 'error': f'RPM {rpm} out of range'}
                return {'success': False, 'error': 'Supervisor not available'}
            elif command == 'set_m2_fwd_velocity':
                # Set M2 forward velocity for automatic cycles
                vel = params.get('vel', 120)
                if self.supervisor:
                    success = self.supervisor.set_m2_fwd_velocity(float(vel))
                    if success:
                        return {'success': True, 'message': f'M2 auto forward velocity set to {vel} mm/s'}
                    return {'success': False, 'error': f'Velocity {vel} out of range'}
                return {'success': False, 'error': 'Supervisor not available'}
            elif command == 'set_m2_rev_velocity':
                # Set M2 reverse velocity for automatic cycles
                vel = params.get('vel', 120)
                if self.supervisor:
                    success = self.supervisor.set_m2_rev_velocity(float(vel))
                    if success:
                        return {'success': True, 'message': f'M2 auto reverse velocity set to {vel} mm/s'}
                    return {'success': False, 'error': f'Velocity {vel} out of range'}
                return {'success': False, 'error': 'Supervisor not available'}
            elif command == 'm2_jog_forward':
                # Jog fixture forward - temporarily override S3 to allow manual jog
                vel = params.get('vel', 50)
                if self.axis and self.io:
                    # Block if forward limit is active
                    if self.io.get_input('sensor3'):
                        return {'success': False, 'error': 'Cannot jog forward - at forward limit (S3)'}
                    self.axis.m2_jog_forward(vel)
                    self._manual_jog_dir = 'fwd'
                    return {'success': True, 'message': f'M2 jogging forward at {vel} mm/s'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm2_jog_reverse':
                # Jog fixture reverse - temporarily override S2 to allow manual jog
                vel = params.get('vel', 50)
                if self.axis and self.io:
                    # Block if reverse/home limit is active
                    if self.io.get_input('sensor2'):
                        return {'success': False, 'error': 'Cannot jog reverse - at reverse limit (S2)'}
                    self.axis.m2_jog_reverse(vel)
                    self._manual_jog_dir = 'rev'
                    return {'success': True, 'message': f'M2 jogging reverse at {vel} mm/s'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm2_stop':
                # Stop fixture motor and clear sensor overrides
                if self.axis:
                    self.axis.m2_stop()
                    # Clear sensor overrides used for manual jog
                    if self.io:
                        self.io.set_input_override('sensor2', None)
                        self.io.set_input_override('sensor3', None)
                    self._manual_jog_dir = None
                    return {'success': True, 'message': 'M2 stopped (overrides cleared)'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm3_goto':
                # Move backstop to position
                position = params.get('position', 0)
                velocity = params.get('velocity', 50)  # Default 50 mm/s
                accel = params.get('accel', 500)  # Default 500 mm/s²
                if self.axis:
                    try:
                        offset_mm = float(self.axis.get_m3_offset()) if hasattr(self.axis, 'get_m3_offset') else 0.0
                    except Exception:
                        offset_mm = 0.0
                    raw_target = float(position) - offset_mm
                    if raw_target < 0:
                        logger.warning("M3 target %.3f mm below offset %.3f mm - clamping to 0", position, offset_mm)
                        raw_target = 0.0

                    self.axis.m3_goto(raw_target, velocity, accel)
                    return {
                        'success': True,
                        'message': f'M3 moving to {position} mm (raw {raw_target:.3f} mm with offset {offset_mm:.3f} mm)'
                    }
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm3_home':
                # Home backstop
                if self.axis:
                    self.axis.m3_home()
                    return {'success': True, 'message': 'M3 homing'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'm3_stop':
                # Stop backstop
                if self.axis:
                    self.axis.m3_stop()
                    return {'success': True, 'message': 'M3 stopped'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'set_m3_offset':
                # Set engineering offset for M3 readouts/targets
                offset_mm = float(params.get('offset_mm', 0))
                if offset_mm < 0:
                    return {'success': False, 'error': 'Offset must be zero or positive'}
                if self.axis and hasattr(self.axis, 'set_m3_offset'):
                    if self.axis.set_m3_offset(offset_mm):
                        return {'success': True, 'message': f'M3 offset set to {offset_mm:.3f} mm'}
                    return {'success': False, 'error': 'Failed to apply M3 offset'}
                return {'success': False, 'error': 'Axis gateway not available'}

            elif command == 'set_input_override':
                # Set input override for diagnostic purposes
                input_name = params.get('name')
                override_state = params.get('state')  # True, False, or None (to disable)

                if self.io and input_name:
                    if self.io.set_input_override(input_name, override_state):
                        if override_state is None:
                            return {'success': True, 'message': f'Input override disabled for {input_name}'}
                        else:
                            return {'success': True, 'message': f'Input {input_name} overridden to {override_state}'}
                    else:
                        return {'success': False, 'error': f'Failed to override input {input_name}'}
                return {'success': False, 'error': 'Invalid parameters or I/O not available'}

            elif command == 'clear_input_overrides':
                # Clear all input overrides
                if self.io:
                    self.io.clear_all_input_overrides()
                    return {'success': True, 'message': 'All input overrides cleared'}
                return {'success': False, 'error': 'I/O not available'}

            else:
                return {'success': False, 'error': f'Unknown command: {command}'}

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {'success': False, 'error': str(e)}

    def _broadcast_update(self):
        """Broadcast current status to all connected clients."""
        try:
            status = {
                'system': self._get_system_status(),
                'inputs': self._get_input_states(),
                'outputs': self._get_output_states(),
                'motors': self._get_motor_status(),
            }
            self.socketio.emit('update', status)

            # Broadcast Nextion statistics - DISABLED (Nextion not part of project)
            # if self.hmi:
            #     nextion_stats = self.hmi.get_statistics()
            #     nextion_stats['connected'] = self.hmi.is_connected
            #     self.socketio.emit('nextion_stats', nextion_stats)

        except Exception as e:
            logger.error(f"Error broadcasting update: {e}")

    def _update_loop(self):
        """Background loop for real-time updates."""
        logger.info("Web monitor update loop started")

        while self._running:
            try:
                self._broadcast_update()

                # Enforce manual jog limits: stop if limit switch hit while jogging
                if self.io and self.axis and self._manual_jog_dir:
                    if self._manual_jog_dir == 'fwd' and self.io.get_input('sensor3'):
                        logger.warning("Manual jog forward stopped at S3")
                        self.axis.m2_stop()
                        self._manual_jog_dir = None
                    elif self._manual_jog_dir == 'rev' and self.io.get_input('sensor2'):
                        logger.warning("Manual jog reverse stopped at S2")
                        self.axis.m2_stop()
                        self._manual_jog_dir = None

                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(1.0)

        logger.info("Web monitor update loop stopped")

    def _emit_status_message(self, message: str):
        """Emit status message to connected clients."""
        try:
            self.socketio.emit('status', {'message': message})
        except Exception as exc:
            logger.error(f"Failed to emit status message: {exc}")

    def set_init_errors(self, errors: list):
        """
        Set initialization errors for diagnostics display.

        Args:
            errors: List of error messages from initialization
        """
        self.init_errors = errors
        if errors:
            logger.warning(f"Web monitor tracking {len(errors)} initialization error(s)")

    def start(self):
        """Start web server."""
        if self._running:
            logger.warning("Web monitor already running")
            return

        self._running = True

        # Register Nextion log callback - DISABLED (Nextion not part of project)
        # if self.hmi:
        #     self.hmi.set_log_callback(self._handle_nextion_log)

        # Start update broadcast thread
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name='WebMonitorUpdate'
        )
        self._update_thread.start()

        # Start Flask server in thread
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name='WebMonitorServer'
        )

        logger.info(f"Starting Flask server thread for {self.host}:{self.port}...")
        self._thread.start()

        # Wait and check if thread is alive
        time.sleep(1)
        if self._thread.is_alive():
            logger.info(f"Web monitor server thread is running (Thread ID: {self._thread.ident})")
        else:
            logger.error(f"Web monitor server thread DIED immediately!")
            logger.error("Thread may have crashed during startup - check logs above for exceptions")

        logger.info(f"Web monitor started at http://{self.host}:{self.port}")

    def _run_server(self):
        """Run Flask server (in thread)."""
        logger.info(f"_run_server thread starting, binding to {self.host}:{self.port}")
        logger.info(f"Thread name: {threading.current_thread().name}")
        logger.info(f"Thread ID: {threading.current_thread().ident}")

        try:
            logger.info("About to call socketio.run()...")
            logger.info(f"Flask app: {self.app}")
            logger.info(f"SocketIO: {self.socketio}")

            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True,
                log_output=False
            )
            logger.info("socketio.run() returned normally (server stopped)")

        except Exception as e:
            logger.error(f"Web server error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception args: {e.args}")

    def _handle_nextion_log(self, message: str, direction: str, timestamp: float):
        """
        Handle Nextion TX/RX log messages.

        Args:
            message: The message sent/received
            direction: 'TX' or 'RX'
            timestamp: Unix timestamp
        """
        try:
            self.socketio.emit('nextion_log', {
                'message': message,
                'direction': direction,
                'timestamp': timestamp
            })
        except Exception as e:
            logger.error(f"Error emitting nextion log: {e}")

    def stop(self):
        """Stop web server."""
        if not self._running:
            return

        logger.info("Stopping web monitor...")
        self._running = False

        if self._update_thread:
            self._update_thread.join(timeout=2.0)

        # Note: Flask/eventlet server doesn't stop cleanly in thread
        # Service restart will handle cleanup

        logger.info("Web monitor stopped")

    def get_statistics(self) -> Dict[str, Any]:
        """Get web monitor statistics."""
        return {
            'running': self._running,
            'url': f'http://{self.host}:{self.port}',
        }
