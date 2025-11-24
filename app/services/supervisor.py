"""
Supervisor state machine for Pleat Saw controller.
Implements the complete process flow with safety interlocks and timeouts.
"""

import logging
import time
import threading
import yaml
import os
from enum import Enum
from typing import Optional, Dict
from services.io_poller import IOPoller
from services.axis_gateway import AxisGateway
from services.nextion_bridge import NextionBridge


logger = logging.getLogger(__name__)

# Runtime parameters file for persistence across reboots
RUNTIME_PARAMS_FILE = 'config/runtime_params.yaml'


class State(Enum):
    """Process states."""
    INIT = "INIT"
    IDLE = "IDLE"
    PRECHECK = "PRECHECK"
    START_SPINDLE = "START_SPINDLE"
    FEED_FWD = "FEED_FWD"
    DWELL = "DWELL"
    FEED_REV = "FEED_REV"
    CLAMP = "CLAMP"
    SAW_STOP = "SAW_STOP"
    AIR_JET = "AIR_JET"
    COMPLETE = "COMPLETE"
    ALARM = "ALARM"
    ESTOP = "ESTOP"
    PAUSE = "PAUSE"
    MANUAL_HOME_M2 = "MANUAL_HOME_M2"


class Supervisor:
    """
    Supervisor state machine for pleat saw process control.
    Manages process flow, safety interlocks, and alarm handling.
    """

    def __init__(
        self,
        io: IOPoller,
        axis: AxisGateway,
        hmi: NextionBridge,
        config: dict,
        loop_rate_hz: float = 50.0
    ):
        """
        Initialize supervisor.

        Args:
            io: IOPoller instance
            axis: AxisGateway instance
            hmi: NextionBridge instance
            config: Configuration dictionary
            loop_rate_hz: State machine loop rate
        """
        self.io = io
        self.axis = axis
        self.hmi = hmi
        self.config = config
        self.loop_rate_hz = loop_rate_hz
        self.loop_interval = 1.0 / loop_rate_hz

        # Current state
        self.state = State.INIT
        self.prev_state = State.INIT

        # State entry time (for timeouts and dwells)
        self.state_entry_time = 0.0

        # Alarms
        self.current_alarm = ""
        self.alarm_latched = False

        # Safety (ESTOP)
        self.safety_ok = False
        self.last_safety_check = 0.0

        # Pause (Light curtain)
        self.light_curtain_ok = False
        self.is_paused = False
        self.pause_saved_state = None  # Save state before pause for resume
        self.pause_saved_outputs = None  # Save output states before pause

        # Process parameters (from config)
        self.m1_rpm = config['motion']['m1_blade']['rpm_default']
        self.m1_ramp_ms = config['motion']['m1_blade']['ramp_ms']
        self.m1_start_timeout = config['motion']['m1_blade']['timeout_start_s']

        self.m2_vel_fwd_mm_s = config['motion']['m2_fixture']['default_speed_mm_s']
        self.m2_vel_rev_mm_s = config['motion']['m2_fixture']['default_speed_mm_s']  # Same default, user can change
        self.m2_accel = config['motion']['m2_fixture']['default_accel_mm_s2']
        self.m2_fwd_timeout = config['motion']['m2_fixture']['timeout_fwd_s']
        self.m2_rev_timeout = config['motion']['m2_fixture']['timeout_rev_s']

        self.dwell_s = config['motion']['cycle']['dwell_after_s3_s']
        self.air_jet_s = config['motion']['cycle']['air_jet_s']
        self.saw_spindown_s = config['motion']['cycle']['saw_spindown_s']
        self.clamp_confirm_s = config['motion']['cycle'].get('clamp_confirm_s', 0.1)

        self.watchdog_timeout_s = config['system']['safety']['watchdog_timeout_s']

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()

        # Statistics
        self.stats = {
            'cycles_complete': 0,
            'alarms_total': 0,
            'estops_total': 0,
            'pause_events_total': 0,
        }

        # Green lamp flash state
        self._green_flash_state = False
        self._last_flash_toggle = 0.0
        self._flash_period_s = 0.5  # 2 Hz

        # Load runtime parameters (override defaults with saved values)
        self._load_runtime_params()

    def start(self):
        """Start supervisor state machine."""
        if self._running:
            logger.warning("Supervisor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()

        logger.info(f"Supervisor started: {self.loop_rate_hz} Hz")

    def stop(self):
        """Stop supervisor state machine."""
        if not self._running:
            return

        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)

        logger.info("Supervisor stopped")

    def _save_runtime_params(self):
        """Save runtime parameters to file for persistence across reboots."""
        try:
            params = {
                'm1_rpm': self.m1_rpm,
                'm2_vel_fwd_mm_s': self.m2_vel_fwd_mm_s,
                'm2_vel_rev_mm_s': self.m2_vel_rev_mm_s,
                'm2_fwd_timeout': self.m2_fwd_timeout,
                'm2_rev_timeout': self.m2_rev_timeout,
            }

            # Ensure config directory exists
            os.makedirs(os.path.dirname(RUNTIME_PARAMS_FILE), exist_ok=True)

            with open(RUNTIME_PARAMS_FILE, 'w') as f:
                yaml.dump(params, f, default_flow_style=False)

            logger.info(f"Runtime parameters saved to {RUNTIME_PARAMS_FILE}")
        except Exception as e:
            logger.error(f"Failed to save runtime parameters: {e}")

    def _load_runtime_params(self):
        """Load runtime parameters from file if it exists."""
        if not os.path.exists(RUNTIME_PARAMS_FILE):
            logger.info(f"No runtime parameters file found at {RUNTIME_PARAMS_FILE}, using config defaults")
            return

        try:
            with open(RUNTIME_PARAMS_FILE, 'r') as f:
                params = yaml.safe_load(f)

            if params:
                if 'm1_rpm' in params:
                    self.m1_rpm = params['m1_rpm']
                    logger.info(f"Loaded M1 RPM: {self.m1_rpm}")

                if 'm2_vel_fwd_mm_s' in params:
                    self.m2_vel_fwd_mm_s = params['m2_vel_fwd_mm_s']
                    logger.info(f"Loaded M2 forward velocity: {self.m2_vel_fwd_mm_s} mm/s")

                if 'm2_vel_rev_mm_s' in params:
                    self.m2_vel_rev_mm_s = params['m2_vel_rev_mm_s']
                    logger.info(f"Loaded M2 reverse velocity: {self.m2_vel_rev_mm_s} mm/s")

                if 'm2_fwd_timeout' in params:
                    self.m2_fwd_timeout = params['m2_fwd_timeout']
                    logger.info(f"Loaded M2 forward timeout: {self.m2_fwd_timeout} s")

                if 'm2_rev_timeout' in params:
                    self.m2_rev_timeout = params['m2_rev_timeout']
                    logger.info(f"Loaded M2 reverse timeout: {self.m2_rev_timeout} s")

                logger.info("Runtime parameters loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load runtime parameters: {e}, using config defaults")

    def _main_loop(self):
        """Main state machine loop."""
        next_tick = time.monotonic()

        while self._running:
            try:
                # Check safety (global interlock) - ESTOP
                self._check_safety()

                # Check light curtain (pause)
                self._check_light_curtain()

                # Update green flash lamp
                self._update_flash_lamp()

                # Run state machine
                self._state_machine()

                # Update HMI
                self._update_hmi()

                # Sleep until next tick
                now = time.monotonic()
                sleep_time = next_tick - now

                if sleep_time > 0:
                    time.sleep(sleep_time)

                next_tick += self.loop_interval

            except Exception as e:
                logger.error(f"Supervisor loop error: {e}")
                time.sleep(0.1)

    def _check_safety(self):
        """Check safety input (global interlock) - ESTOP functionality."""
        now = time.monotonic()

        # Check watchdog
        if now - self.last_safety_check > self.watchdog_timeout_s:
            logger.warning("Safety watchdog timeout")

        self.last_safety_check = now

        # Read safety input (ESTOP)
        safety = self.io.get_input('safety')

        if safety is None:
            logger.error("Failed to read safety input (ESTOP)")
            return

        # Check for safety drop (ESTOP condition)
        if self.safety_ok and not safety:
            logger.error("SAFETY CIRCUIT DROPPED - EMERGENCY STOP")
            self._emergency_stop()

        self.safety_ok = safety

    def _emergency_stop(self):
        """Execute Category 0 emergency stop."""
        self.stats['estops_total'] += 1

        # Stop all motors immediately
        self.axis.emergency_stop_all()

        # Set outputs to safe state
        safe_outputs = {
            'clamp': False,
            'air_jet': False,
            'green_solid': False,
            'green_flash': False,
        }
        self.io.set_outputs(safe_outputs)

        # Latch alarm
        self.current_alarm = "SAFETY_ESTOP"
        self.alarm_latched = True

        # Transition to ESTOP state
        self._transition_to(State.ESTOP)

    def _check_light_curtain(self):
        """Check light curtain input for pause functionality."""
        # Read light curtain input
        light_curtain = self.io.get_input('light_curtain')

        if light_curtain is None:
            logger.error("Failed to read light curtain input")
            return

        # Light curtain logic: active = OK to run, inactive = PAUSE
        light_curtain_blocked = not light_curtain

        # Check for state changes
        if not self.light_curtain_ok and light_curtain:
            # Light curtain restored - resume if we were paused
            logger.info("Light curtain restored - resuming operation")
            self._resume_from_pause()
        elif self.light_curtain_ok and not light_curtain:
            # Light curtain blocked - pause if we're in a running state
            logger.info("Light curtain blocked - pausing operation")
            self._initiate_pause()

        self.light_curtain_ok = light_curtain

    def _initiate_pause(self):
        """Initiate pause due to light curtain."""
        # Only pause if we're in a running state (not IDLE, ALARM, ESTOP)
        pausable_states = [
            State.PRECHECK, State.START_SPINDLE, State.FEED_FWD,
            State.DWELL, State.FEED_REV, State.CLAMP,
            State.SAW_STOP, State.AIR_JET, State.COMPLETE,
            State.MANUAL_HOME_M2
        ]

        if self.state in pausable_states:
            logger.info(f"Pausing from state: {self.state.value}")
            self.stats['pause_events_total'] += 1

            # Save current state and outputs
            self.pause_saved_state = self.state
            self.pause_saved_outputs = self._get_current_outputs()

            # Stop all motors but preserve outputs
            self.axis.stop_all_motors()

            # Mark as paused and transition to PAUSE state
            self.is_paused = True
            self._transition_to(State.PAUSE)

    def _resume_from_pause(self):
        """Resume operation after pause."""
        if self.is_paused and self.pause_saved_state is not None:
            logger.info(f"Resuming to state: {self.pause_saved_state.value}")

            # Restore outputs if configured to preserve them
            if self.pause_saved_outputs:
                self.io.set_outputs(self.pause_saved_outputs)

            # Clear pause flags
            self.is_paused = False
            saved_state = self.pause_saved_state
            self.pause_saved_state = None
            self.pause_saved_outputs = None

            # Resume to saved state
            self._transition_to(saved_state)

    def _get_current_outputs(self):
        """Get current output states for pause/resume."""
        try:
            return {
                'clamp': self.io.get_output('clamp'),
                'air_jet': self.io.get_output('air_jet'),
                'green_solid': self.io.get_output('green_solid'),
                'green_flash': self.io.get_output('green_flash'),
            }
        except Exception as e:
            logger.error(f"Failed to get current outputs: {e}")
            return None

    def _update_flash_lamp(self):
        """Update green flashing lamp (2 Hz during run)."""
        now = time.monotonic()

        if now - self._last_flash_toggle >= self._flash_period_s:
            if self.state not in [State.IDLE, State.INIT, State.ALARM, State.ESTOP, State.PAUSE]:
                self._green_flash_state = not self._green_flash_state
                self.io.set_output('green_flash', self._green_flash_state)

            self._last_flash_toggle = now

    def _state_machine(self):
        """Execute state machine logic."""
        if self.state == State.INIT:
            self._state_init()
        elif self.state == State.IDLE:
            self._state_idle()
        elif self.state == State.PRECHECK:
            self._state_precheck()
        elif self.state == State.START_SPINDLE:
            self._state_start_spindle()
        elif self.state == State.FEED_FWD:
            self._state_feed_fwd()
        elif self.state == State.DWELL:
            self._state_dwell()
        elif self.state == State.FEED_REV:
            self._state_feed_rev()
        elif self.state == State.CLAMP:
            self._state_clamp()
        elif self.state == State.SAW_STOP:
            self._state_saw_stop()
        elif self.state == State.AIR_JET:
            self._state_air_jet()
        elif self.state == State.COMPLETE:
            self._state_complete()
        elif self.state == State.ALARM:
            self._state_alarm()
        elif self.state == State.ESTOP:
            self._state_estop()
        elif self.state == State.PAUSE:
            self._state_pause()
        elif self.state == State.MANUAL_HOME_M2:
            self._state_manual_home_m2()

    # ========== State Handlers ==========

    def _state_init(self):
        """INIT state: System initialization."""
        # Set outputs to safe state
        self.io.set_output('clamp', False)
        self.io.set_output('air_jet', False)
        self.io.set_output('green_solid', False)
        self.io.set_output('green_flash', False)

        # Transition to IDLE
        self._transition_to(State.IDLE)

    def _state_idle(self):
        """IDLE state: Waiting for start command."""
        # Set green solid lamp
        self.io.set_output('green_solid', True)
        self.io.set_output('green_flash', False)

        # Check for start button
        if self.io.get_input('start'):
            logger.info("START button pressed")
            self._transition_to(State.PRECHECK)

    def _state_precheck(self):
        """PRECHECK state: Verify safety and readiness."""
        # Check safety
        if not self.safety_ok:
            self._raise_alarm("PRECHECK_SAFETY_NOT_READY")
            return

        # Check no alarms
        if self.alarm_latched:
            self._raise_alarm("PRECHECK_ALARM_LATCHED")
            return

        # Check M2 is at home position (sensor2/IN2)
        if not self.io.get_input('sensor2'):
            self._raise_alarm("PRECHECK_M2_NOT_HOME")
            return

        # All checks passed
        logger.info("Precheck passed, starting cycle")
        self._transition_to(State.START_SPINDLE)

    def _state_start_spindle(self):
        """START_SPINDLE state: Start blade motor."""
        elapsed = time.monotonic() - self.state_entry_time

        # Send start command immediately and retry every 0.5s if not running
        # This ensures fast response even if first command fails
        if elapsed < 0.1 or (elapsed % 0.5) < 0.02:
            self.axis.m1_start(self.m1_rpm, self.m1_ramp_ms)

        # Wait for RUNNING status
        status = self.axis.m1_get_status()

        if status and status['running']:
            logger.info("Blade running")
            self._transition_to(State.FEED_FWD)

        # Timeout check
        elif elapsed > self.m1_start_timeout:
            self._raise_alarm("TIMEOUT_BLADE_START")

    def _state_feed_fwd(self):
        """FEED_FWD state: Feed forward until Sensor3."""
        elapsed = time.monotonic() - self.state_entry_time

        # Start feed on entry and retry every 0.5s if command fails
        if elapsed < 0.1 or (elapsed % 0.5) < 0.02:
            self.axis.m2_set_velocity(self.m2_vel_fwd_mm_s, self.m2_accel)
            self.axis.m2_feed_forward()

        # Check for Sensor3 (forward detect)
        if self.io.get_input('sensor3'):
            logger.info("Sensor3 detected")
            self.axis.m2_stop()
            self._transition_to(State.DWELL)

        # Timeout check
        elif elapsed > self.m2_fwd_timeout:
            self.axis.m2_stop()
            self._raise_alarm("TIMEOUT_FWD")

    def _state_dwell(self):
        """DWELL state: Pause at forward position."""
        elapsed = time.monotonic() - self.state_entry_time

        if elapsed >= self.dwell_s:
            logger.info("Dwell complete")
            self._transition_to(State.FEED_REV)

    def _state_feed_rev(self):
        """FEED_REV state: Feed reverse until Sensor2."""
        elapsed = time.monotonic() - self.state_entry_time

        # Start reverse on entry and retry every 0.5s if command fails
        if elapsed < 0.1 or (elapsed % 0.5) < 0.02:
            self.axis.m2_set_velocity(self.m2_vel_rev_mm_s, self.m2_accel)
            self.axis.m2_feed_reverse()

        # Check for Sensor2 (reverse/home detect)
        if self.io.get_input('sensor2'):
            logger.info("Sensor2 detected")
            self.axis.m2_stop()
            self._transition_to(State.CLAMP)

        # Timeout check
        elif elapsed > self.m2_rev_timeout:
            self.axis.m2_stop()
            self._raise_alarm("TIMEOUT_REV")

    def _state_clamp(self):
        """CLAMP state: Activate clamp."""
        elapsed = time.monotonic() - self.state_entry_time

        # Activate clamp on entry
        if elapsed < 0.1:
            self.io.set_output('clamp', True)

        # Brief confirmation delay
        if elapsed >= self.clamp_confirm_s:
            logger.info("Clamp activated")
            self._transition_to(State.SAW_STOP)

    def _state_saw_stop(self):
        """SAW_STOP state: Stop blade motor."""
        elapsed = time.monotonic() - self.state_entry_time

        # Stop blade on entry
        if elapsed < 0.1:
            self.axis.m1_stop()

        # Wait for spindown
        if elapsed >= self.saw_spindown_s:
            logger.info("Blade stopped")
            self._transition_to(State.AIR_JET)

    def _state_air_jet(self):
        """AIR_JET state: Pulse air jet."""
        elapsed = time.monotonic() - self.state_entry_time

        # Turn on air jet on entry
        if elapsed < 0.1:
            self.io.set_output('air_jet', True)

        # Turn off after duration
        if elapsed >= self.air_jet_s:
            self.io.set_output('air_jet', False)
            logger.info("Air jet complete")
            self._transition_to(State.COMPLETE)

    def _state_complete(self):
        """COMPLETE state: Cycle finished."""
        elapsed = time.monotonic() - self.state_entry_time

        # On entry: release clamp, set lights, update stats
        if elapsed < 0.1:
            # Release clamp
            self.io.set_output('clamp', False)

            # Set green solid lamp
            self.io.set_output('green_solid', True)
            self.io.set_output('green_flash', False)

            # Update stats
            self.stats['cycles_complete'] += 1

            logger.info(f"Cycle complete (total: {self.stats['cycles_complete']})")

        # Send M2 stop commands repeatedly to eliminate residual motion
        # Send every 100ms for 0.5 seconds to ensure motor fully stops
        if elapsed < 0.5 and (elapsed % 0.1) < 0.02:
            self.axis.m2_stop()
            if elapsed < 0.15:
                logger.debug("Sending M2 stop commands to eliminate residual motion")

        # After 0.5s, return to IDLE
        if elapsed >= 0.5:
            self._transition_to(State.IDLE)

    def _state_alarm(self):
        """ALARM state: Alarm condition."""
        # Stop all motion
        self.axis.emergency_stop_all()

        # Set outputs safe
        self.io.set_output('clamp', False)
        self.io.set_output('air_jet', False)
        self.io.set_output('green_solid', False)
        self.io.set_output('green_flash', False)

        # Wait for RESET_ALARMS command from HMI
        # (handled in command callback)

    def _state_estop(self):
        """ESTOP state: Emergency stop."""
        # Remain in ESTOP until safety restored and reset
        if self.safety_ok and not self.alarm_latched:
            logger.info("ESTOP cleared")
            self._transition_to(State.IDLE)

    def _state_pause(self):
        """PAUSE state: Light curtain blocked - waiting for restore."""
        # Just wait in this state until light curtain is restored
        # The _check_light_curtain() method will handle resume
        pass

    def _state_manual_home_m2(self):
        """MANUAL_HOME_M2 state: Manual homing of M2 fixture to S2 sensor."""
        elapsed = time.monotonic() - self.state_entry_time

        # Start reverse on entry at 30% of auto reverse speed
        if elapsed < 0.1:
            vel = self.m2_vel_rev_mm_s * 0.3
            self.axis.m2_set_velocity(vel, self.m2_accel)
            self.axis.m2_feed_reverse()
            logger.info(f"Manual M2 homing started @ {vel:.1f} mm/s (30% auto speed)")

        # Retry command every 0.5s if needed
        elif (elapsed % 0.5) < 0.02:
            vel = self.m2_vel_rev_mm_s * 0.3
            self.axis.m2_set_velocity(vel, self.m2_accel)
            self.axis.m2_feed_reverse()

        # Check for Sensor2 (home detect)
        if self.io.get_input('sensor2'):
            logger.info("Manual M2 homing complete - Sensor2 detected")
            self.axis.m2_stop()
            self._transition_to(State.IDLE)

        # Timeout check (use the reverse timeout)
        elif elapsed > self.m2_rev_timeout:
            logger.warning("Manual M2 homing timeout")
            self.axis.m2_stop()
            self._transition_to(State.IDLE)

    # ========== Helpers ==========

    def _transition_to(self, new_state: State):
        """Transition to a new state."""
        if new_state != self.state:
            logger.info(f"State transition: {self.state.value} -> {new_state.value}")

            self.prev_state = self.state
            self.state = new_state
            self.state_entry_time = time.monotonic()

    def _raise_alarm(self, alarm_code: str):
        """Raise an alarm and transition to ALARM state."""
        logger.error(f"ALARM: {alarm_code}")

        self.current_alarm = alarm_code
        self.alarm_latched = True
        self.stats['alarms_total'] += 1

        self._transition_to(State.ALARM)

    def reset_alarms(self):
        """Reset latched alarms (called by HMI command)."""
        if not self.safety_ok:
            logger.warning("Cannot reset alarms: safety not OK")
            return False

        logger.info("Alarms reset")
        self.current_alarm = ""
        self.alarm_latched = False

        if self.state == State.ALARM or self.state == State.ESTOP:
            self._transition_to(State.IDLE)

        return True

    def _update_hmi(self):
        """Update HMI with current state and status."""
        # Nextion HMI disabled - skip updates
        if self.hmi is None:
            return

        self.hmi.update_multiple({
            'state': self.state.value,
            'safety': 'READY' if self.safety_ok else 'NOT_READY',
            'light_curtain': 'OK' if self.light_curtain_ok else 'BLOCKED',
            'paused': 'PAUSED' if self.is_paused else 'RUNNING',
            'm1.rpm': self.m1_rpm,
            'm2.vel': self.m2_vel_fwd_mm_s,  # Show forward velocity on HMI
            'alarm': self.current_alarm,
        })

        # Update M3 position
        pos = self.axis.m3_get_position()
        if pos is not None:
            self.hmi.update_position_mm(pos)

    def handle_hmi_command(self, cmd: str):
        """
        Handle command from HMI.

        Args:
            cmd: Command string (e.g., "START", "STOP", "RESET_ALARMS")
        """
        logger.info(f"HMI command: {cmd}")

        if cmd == "RESET_ALARMS":
            self.reset_alarms()

        elif cmd == "STOP":
            if self.state not in [State.IDLE, State.ALARM, State.ESTOP]:
                logger.info("STOP requested")
                self.axis.m1_stop()
                self.axis.m2_stop()
                self._transition_to(State.IDLE)

        elif cmd == "HOME_M3":
            self.axis.m3_home()

        # Additional commands can be added here

    def handle_hmi_setpoint(self, key: str, value: str):
        """
        Handle setpoint from HMI.

        Args:
            key: Setpoint key (e.g., "m1.rpm", "m2.vel_fwd", "m3.goto_in")
            value: Setpoint value as string
        """
        logger.info(f"HMI setpoint: {key}={value}")

        try:
            if key == "m1.rpm":
                # Set M1 blade RPM
                rpm = int(value)
                self.set_m1_rpm(rpm)

            elif key == "m2.vel_fwd":
                # Set M2 forward velocity
                vel = float(value)
                self.set_m2_fwd_velocity(vel)

            elif key == "m2.vel_rev":
                # Set M2 reverse velocity
                vel = float(value)
                self.set_m2_rev_velocity(vel)

            elif key == "m3.goto_in":
                # Move M3 to position (inches)
                pos_in = float(value)
                pos_mm = pos_in * 25.4  # Convert to mm
                self.axis.m3_goto(pos_mm)

            elif key == "m3.goto_mm":
                # Move M3 to position (mm)
                pos_mm = float(value)
                self.axis.m3_goto(pos_mm)

            else:
                logger.warning(f"Unknown HMI setpoint: {key}")

        except ValueError as e:
            logger.error(f"Invalid HMI setpoint value for {key}={value}: {e}")

    def get_state(self) -> str:
        """Get current state as string."""
        return self.state.value if self.state else 'UNKNOWN'

    def get_statistics(self) -> dict:
        """Get supervisor statistics."""
        return self.stats.copy()

    def manual_home_m2(self) -> bool:
        """
        Trigger manual homing of M2 fixture motor to S2 sensor.
        Only allowed from IDLE state.
        Returns True if homing started, False if not allowed.
        """
        if self.state != State.IDLE:
            logger.warning(f"Cannot start manual M2 homing from state {self.state.value}")
            return False

        if not self.safety_ok:
            logger.warning("Cannot start manual M2 homing: safety not OK")
            return False

        logger.info("Manual M2 homing requested")
        self._transition_to(State.MANUAL_HOME_M2)
        return True

    def set_m1_rpm(self, rpm: int) -> bool:
        """Set M1 blade RPM for automatic cycles."""
        rpm_min = self.config['motion']['m1_blade']['rpm_min']
        rpm_max = self.config['motion']['m1_blade']['rpm_max']

        if rpm_min <= rpm <= rpm_max:
            self.m1_rpm = rpm
            logger.info(f"M1 RPM updated to {rpm}")
            self._save_runtime_params()
            return True
        else:
            logger.warning(f"M1 RPM {rpm} out of range [{rpm_min}-{rpm_max}]")
            return False

    def set_m2_fwd_velocity(self, vel_mm_s: float) -> bool:
        """Set M2 forward velocity for automatic cycles."""
        vel_min = self.config['motion']['m2_fixture']['speed_mm_s_min']
        vel_max = self.config['motion']['m2_fixture']['speed_mm_s_max']

        if vel_min <= vel_mm_s <= vel_max:
            self.m2_vel_fwd_mm_s = vel_mm_s
            logger.info(f"M2 forward velocity updated to {vel_mm_s} mm/s")
            self._save_runtime_params()
            return True
        else:
            logger.warning(f"M2 forward velocity {vel_mm_s} out of range [{vel_min}-{vel_max}]")
            return False

    def set_m2_rev_velocity(self, vel_mm_s: float) -> bool:
        """Set M2 reverse velocity for automatic cycles."""
        vel_min = self.config['motion']['m2_fixture']['speed_mm_s_min']
        vel_max = self.config['motion']['m2_fixture']['speed_mm_s_max']

        if vel_min <= vel_mm_s <= vel_max:
            self.m2_vel_rev_mm_s = vel_mm_s
            logger.info(f"M2 reverse velocity updated to {vel_mm_s} mm/s")
            self._save_runtime_params()
            return True
        else:
            logger.warning(f"M2 reverse velocity {vel_mm_s} out of range [{vel_min}-{vel_max}]")
            return False

    def set_m2_fwd_timeout(self, timeout_s: float) -> bool:
        """Set M2 forward timeout for automatic cycles."""
        if 1.0 <= timeout_s <= 120.0:
            self.m2_fwd_timeout = timeout_s
            logger.info(f"M2 forward timeout updated to {timeout_s} s")
            self._save_runtime_params()
            return True
        else:
            logger.warning(f"M2 forward timeout {timeout_s} out of range [1.0-120.0]")
            return False

    def set_m2_rev_timeout(self, timeout_s: float) -> bool:
        """Set M2 reverse timeout for automatic cycles."""
        if 1.0 <= timeout_s <= 120.0:
            self.m2_rev_timeout = timeout_s
            logger.info(f"M2 reverse timeout updated to {timeout_s} s")
            self._save_runtime_params()
            return True
        else:
            logger.warning(f"M2 reverse timeout {timeout_s} out of range [1.0-120.0]")
            return False

    def __repr__(self) -> str:
        return f"<Supervisor state={self.state.value}, safety={'OK' if self.safety_ok else 'NOT_OK'}>"
