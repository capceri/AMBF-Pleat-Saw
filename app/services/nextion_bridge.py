"""
Nextion HMI bridge service.
Implements key=value protocol for bidirectional communication with Nextion display.
"""

import logging
import time
import threading
import serial
from typing import Optional, Dict, Callable
from collections import deque
from utils.units import mm_to_inches, inches_to_mm, format_inches, format_mm


logger = logging.getLogger(__name__)


class NextionBridge:
    """
    Bridge between Pleat Saw controller and Nextion HMI.
    Uses key=value ASCII protocol over serial.
    """

    # Nextion line terminator (for receiving from Nextion)
    TERMINATOR = b'\n'

    # Nextion command terminator (for sending to Nextion)
    NEXTION_END = b'\xFF\xFF\xFF'

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        timeout: float = 0.1,
        update_rate_hz: float = 10.0,
        debounce_ms: int = 100
    ):
        """
        Initialize Nextion bridge.

        Args:
            port: Serial port path (e.g., /dev/ttyAMA0)
            baud: Baud rate (default 115200)
            timeout: Serial read timeout
            update_rate_hz: Rate to push status updates to HMI
            debounce_ms: Debounce time for setpoint changes from HMI
        """
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.update_rate_hz = update_rate_hz
        self.update_interval = 1.0 / update_rate_hz
        self.debounce_ms = debounce_ms

        self.serial: Optional[serial.Serial] = None
        self.is_connected = False

        # State to push to HMI
        self.hmi_state: Dict[str, any] = {
            'state': 'INIT',
            'safety': 'UNKNOWN',
            'm1.rpm': 0,
            'm2.vel': 0.0,
            'm3.pos_mm': 0.0,
            'm3.pos_in': 0.0,
            'alarm': '',
        }

        # Map internal state keys to Nextion object names (ESP32-compatible)
        self.nextion_object_map = {
            'state': 'tState',          # State text object
            'safety': 'tSafety',        # Safety text object
            'm1.rpm': 'tS1',            # Motor 1 speed text
            'm2.vel': 'tS2',            # Motor 2 velocity text
            'm3.pos_mm': 'tPosMm',      # Position in mm
            'm3.pos_in': 'tPos',        # Position in inches (main display)
            'alarm': 'tAlarm',          # Alarm text object
        }

        # Received commands/setpoints from HMI
        self._command_queue = deque()
        self._command_callbacks: Dict[str, list] = {}

        # Debouncing for setpoint changes
        self._last_setpoint_time: Dict[str, float] = {}

        # Threading
        self._running = False
        self._rx_thread: Optional[threading.Thread] = None
        self._tx_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            'tx_count': 0,
            'rx_count': 0,
            'parse_errors': 0,
        }

        # Log callback for web monitor
        self._log_callback = None

    def connect(self) -> bool:
        """
        Open serial connection to Nextion.

        Returns:
            True if connected successfully
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )

            self.is_connected = True
            logger.info(f"Nextion connected: {self.port} @ {self.baud} baud")

            # Clear any pending data
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            return True

        except Exception as e:
            logger.error(f"Nextion connection error: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.serial:
            self.serial.close()
            self.is_connected = False
            logger.info("Nextion disconnected")

    def start(self):
        """Start RX and TX threads."""
        if self._running:
            logger.warning("NextionBridge already running")
            return

        if not self.is_connected:
            logger.error("Cannot start NextionBridge: not connected")
            return

        self._running = True

        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._tx_thread.start()

        logger.info(f"NextionBridge started: {self.update_rate_hz} Hz")

    def stop(self):
        """Stop RX and TX threads."""
        if not self._running:
            return

        self._running = False

        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)

        if self._tx_thread:
            self._tx_thread.join(timeout=2.0)

        logger.info("NextionBridge stopped")

    def _rx_loop(self):
        """Receive loop (runs in separate thread)."""
        buffer = b''

        while self._running:
            try:
                if self.serial.in_waiting > 0:
                    chunk = self.serial.read(self.serial.in_waiting)
                    buffer += chunk

                    # Process complete lines
                    while self.TERMINATOR in buffer:
                        line, buffer = buffer.split(self.TERMINATOR, 1)
                        self._process_rx_line(line.decode('ascii', errors='ignore').strip())

                else:
                    time.sleep(0.01)  # Brief sleep if no data

            except Exception as e:
                logger.error(f"Nextion RX error: {e}")
                time.sleep(0.1)

    def _tx_loop(self):
        """Transmit loop (runs in separate thread)."""
        next_update = time.monotonic()

        while self._running:
            try:
                now = time.monotonic()

                if now >= next_update:
                    self._push_state_to_hmi()
                    next_update += self.update_interval

                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Nextion TX error: {e}")
                time.sleep(0.1)

    def _process_rx_line(self, line: str):
        """
        Process a received line from Nextion.

        ESP32-compatible formats:
            S1=800          -> Set M1 RPM
            S2F=1200        -> Set M2 forward velocity
            S2R=1200        -> Set M2 reverse velocity
            S3=1500         -> Set M1 RPM (saw speed)
            M12.500         -> Move M3 to position (inches)
            H               -> Home M3
            REQ             -> Request live values (refresh)
            REQE            -> Request EEPROM values (refresh)

        Also supports new format:
            cmd=START
            m1.rpm=3500
        """
        if not line:
            return

        self.stats['rx_count'] += 1
        logger.debug(f"Nextion RX: {line}")

        # Call log callback for web monitor
        if self._log_callback:
            self._log_callback(line, 'RX', time.time())

        # Handle ESP32-style single-letter commands (no '=')
        if '=' not in line:
            cmd = line.strip().upper()

            if cmd == 'H':
                # Home command
                self._handle_command('HOME_M3')
                return
            elif cmd == 'REQ' or cmd == 'REQE':
                # Request values - trigger immediate state push
                logger.debug("Nextion requested value refresh")
                return
            elif cmd.startswith('M'):
                # Move command: M12.500 -> move to 12.500 inches
                try:
                    position = float(cmd[1:])
                    self._handle_setpoint('m3.goto_in', str(position))
                    return
                except ValueError:
                    logger.warning(f"Invalid move command: {cmd}")
                    self.stats['parse_errors'] += 1
                    return
            else:
                logger.warning(f"Unknown command (no '='): {line}")
                self.stats['parse_errors'] += 1
                return

        # Parse key=value
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        # Map ESP32 keys to new format
        if key == 'S1':
            # S1=800 -> m1.rpm=800
            self._handle_setpoint('m1.rpm', value)
        elif key == 'S2F':
            # S2F=1200 -> m2.vel_fwd=1200
            self._handle_setpoint('m2.vel_fwd', value)
        elif key == 'S2R':
            # S2R=1200 -> m2.vel_rev=1200
            self._handle_setpoint('m2.vel_rev', value)
        elif key == 'S3':
            # S3=1500 -> m1.rpm=1500 (saw speed = blade rpm)
            self._handle_setpoint('m1.rpm', value)
        elif key == 'cmd':
            # New format command
            self._handle_command(value)
        else:
            # New format setpoint (m1.rpm=, m3.goto_mm=, etc.)
            self._handle_setpoint(key, value)

    def _handle_command(self, cmd: str):
        """Handle command from HMI (e.g., START, STOP)."""
        logger.info(f"Nextion command: {cmd}")

        with self._lock:
            self._command_queue.append(('cmd', cmd))

        # Trigger callbacks
        self._trigger_callbacks('cmd', cmd)

    def _handle_setpoint(self, key: str, value: str):
        """Handle setpoint change from HMI (e.g., m1.rpm=3500)."""
        # Debounce
        now = time.monotonic()
        last_time = self._last_setpoint_time.get(key, 0)

        if now - last_time < (self.debounce_ms / 1000.0):
            logger.debug(f"Debounced setpoint: {key}={value}")
            return

        self._last_setpoint_time[key] = now

        logger.info(f"Nextion setpoint: {key}={value}")

        with self._lock:
            self._command_queue.append(('setpoint', key, value))

        # Trigger callbacks
        self._trigger_callbacks(key, value)

    def _push_state_to_hmi(self):
        """Push current state to HMI using Nextion native commands."""
        with self._lock:
            state_copy = self.hmi_state.copy()

        # Send Nextion commands to update each object
        for key, value in state_copy.items():
            obj_name = self.nextion_object_map.get(key)
            if obj_name:
                self._send_nextion_cmd(f'{obj_name}.txt="{value}"')

    def _send_nextion_cmd(self, cmd: str):
        """
        Send a Nextion native command with 3x 0xFF terminator.

        Args:
            cmd: Nextion command (e.g., 'tS1.txt="800"')
        """
        if not self.is_connected or not self.serial:
            return

        try:
            self.serial.write(cmd.encode('ascii'))
            self.serial.write(self.NEXTION_END)
            self.stats['tx_count'] += 1
            logger.debug(f"Nextion TX: {cmd}")

            # Call log callback for web monitor
            if self._log_callback:
                self._log_callback(cmd, 'TX', time.time())

        except Exception as e:
            logger.error(f"Nextion send error: {e}")

    def _send_line(self, line: str):
        """
        Send a line to Nextion (legacy method for compatibility).
        Now wraps _send_nextion_cmd.
        """
        self._send_nextion_cmd(line)

    # ========== Public API ==========

    def update_state(self, key: str, value):
        """
        Update a state variable to be pushed to HMI.

        Args:
            key: Variable name (e.g., "state", "m1.rpm")
            value: Value (will be converted to string)
        """
        with self._lock:
            self.hmi_state[key] = value

    def update_multiple(self, updates: Dict[str, any]):
        """Update multiple state variables at once."""
        with self._lock:
            self.hmi_state.update(updates)

    def update_position_mm(self, pos_mm: float):
        """
        Update M3 position (converts to both mm and inches for HMI).

        Args:
            pos_mm: Position in millimeters
        """
        pos_in = mm_to_inches(pos_mm)

        with self._lock:
            self.hmi_state['m3.pos_mm'] = format_mm(pos_mm, 3)
            self.hmi_state['m3.pos_in'] = format_inches(pos_in, 3)

    def send_command_immediate(self, key: str, value: str):
        """
        Send a command/value immediately (bypass update loop).

        Args:
            key: Key name (internal format, e.g., "m1.rpm")
            value: Value
        """
        # Map to Nextion object and send
        obj_name = self.nextion_object_map.get(key)
        if obj_name:
            self._send_nextion_cmd(f'{obj_name}.txt="{value}"')
        else:
            logger.warning(f"No Nextion object mapping for key: {key}")

    def send_nextion_text(self, obj_name: str, text: str):
        """
        Send text directly to a Nextion text object.

        Args:
            obj_name: Nextion object name (e.g., "tS1")
            text: Text to display
        """
        self._send_nextion_cmd(f'{obj_name}.txt="{text}"')

    def send_nextion_value(self, obj_name: str, value: int):
        """
        Send numeric value directly to a Nextion object.

        Args:
            obj_name: Nextion object name (e.g., "n0")
            value: Numeric value
        """
        self._send_nextion_cmd(f'{obj_name}.val={value}')

    def get_command(self) -> Optional[tuple]:
        """
        Pop next command from queue.

        Returns:
            Tuple of (type, data...) or None if queue empty
            Examples: ('cmd', 'START'), ('setpoint', 'm1.rpm', '3500')
        """
        with self._lock:
            if self._command_queue:
                return self._command_queue.popleft()
            return None

    def register_callback(self, key: str, callback: Callable):
        """
        Register a callback for a specific key.

        Args:
            key: Key to monitor (e.g., "cmd", "m1.rpm")
            callback: Function to call when key received from HMI
        """
        if key not in self._command_callbacks:
            self._command_callbacks[key] = []

        self._command_callbacks[key].append(callback)

    def _trigger_callbacks(self, key: str, value: str):
        """Trigger all callbacks for a key."""
        callbacks = self._command_callbacks.get(key, [])

        for callback in callbacks:
            try:
                callback(value)
            except Exception as e:
                logger.error(f"Error in Nextion callback for {key}: {e}")

    def get_statistics(self) -> dict:
        """Get communication statistics."""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset communication statistics."""
        self.stats = {
            'tx_count': 0,
            'rx_count': 0,
            'parse_errors': 0,
        }

    def set_log_callback(self, callback):
        """
        Set callback for logging TX/RX messages (for web monitor).

        Args:
            callback: Function(message: str, direction: str, timestamp: float)
        """
        self._log_callback = callback

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"<NextionBridge {self.port} @ {self.baud} baud, {status}>"
