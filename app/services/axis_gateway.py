"""
Axis gateway service for ESP32 motor controllers.
Provides high-level motion control interface.
- M1 & M2: Modbus RTU via ESP32A
- M3: USB Serial via ESP32B (with AS5600 encoder)
"""

import logging
import time
import threading
from glob import glob
from typing import Optional, Dict, Tuple, List
from enum import IntEnum
from services.modbus_master import ModbusMaster
from services.m3_usb_serial import M3USBSerial
from services.esp32a_usb_serial import ESP32AUSBSerial


logger = logging.getLogger(__name__)

# Unit conversion: M3 uses inches
MM_TO_INCHES = 1.0 / 25.4
INCHES_TO_MM = 25.4


# ESP32-A (Blade + Fixture) Register Map
class ESP32A_Reg(IntEnum):
    # M1 Blade
    M1_CMD = 0x0100
    M1_RPM = 0x0101
    M1_STATUS = 0x0102
    M1_RAMP_MS = 0x0103

    # M2 Fixture
    M2_CMD = 0x0120
    M2_VEL_MM_S_x1000 = 0x0121
    M2_ACCEL_MM_S2 = 0x0122
    M2_STATUS = 0x0123
    M2_POS_MM_x1000_LOW = 0x0124
    M2_POS_MM_x1000_HIGH = 0x0125
    M2_JOG_VEL_MM_S_x1000 = 0x0126

    # Common
    FW_VERSION = 0x0140
    HEARTBEAT = 0x0141
    LAST_FAULT_CODE = 0x0142


# ESP32-B (Backstop) Register Map
class ESP32B_Reg(IntEnum):
    M3_CMD = 0x0200
    M3_TARGET_MM_x1000_LOW = 0x0201
    M3_TARGET_MM_x1000_HIGH = 0x0202
    M3_VEL_MM_S_x1000 = 0x0203
    M3_ACCEL_MM_S2 = 0x0204
    M3_STATUS = 0x0205
    M3_POS_MM_x1000_LOW = 0x0206
    M3_POS_MM_x1000_HIGH = 0x0207
    M3_PID_P_x1000 = 0x0208
    M3_PID_I_x1000 = 0x0209
    M3_PID_D_x1000 = 0x020A
    M3_STEPS_PER_MM_x1000 = 0x0210


# Command codes
class M1_Cmd(IntEnum):
    STOP = 0
    RUN = 1
    CLEAR_FAULT = 2


class M2_Cmd(IntEnum):
    STOP = 0
    FWD_UNTIL_S3 = 1
    REV_UNTIL_S2 = 2
    JOG_FWD = 3
    JOG_REV = 4
    CLEAR_FAULT = 5


class M3_Cmd(IntEnum):
    STOP = 0
    GOTO = 1
    HOME = 2
    JOG_FWD = 3
    JOG_REV = 4
    CLEAR_FAULT = 5


class AxisGateway:
    """
    High-level gateway for motor control via ESP32 Modbus slaves.
    Handles M1 (blade), M2 (fixture), and M3 (backstop).
    """

    def __init__(
        self,
        modbus: ModbusMaster,
        esp32a_id: int,
        esp32b_id: int,
        heartbeat_check_s: float = 2.0,
        m3_usb_port: str = '/dev/ttyUSB0',
        m3_usb_port_candidates: Optional[List[str]] = None,
        esp32a_usb_port: Optional[str] = None,
        esp32a_usb_port_candidates: Optional[List[str]] = None,
    ):
        """
        Initialize axis gateway.

        Args:
            modbus: ModbusMaster instance
            esp32a_id: ESP32-A slave ID (blade + fixture)
            esp32b_id: ESP32-B slave ID (backstop - not used, kept for compatibility)
            heartbeat_check_s: Heartbeat monitoring interval
            m3_usb_port: USB serial port for M3 (ESP32B)
        """
        self.modbus = modbus
        self.esp32a_id = esp32a_id
        self.esp32b_id = esp32b_id  # Kept for compatibility, not used
        self.heartbeat_check_s = heartbeat_check_s

        # M3 USB Serial driver (ESP32B firmware)
        self.m3_port_default = m3_usb_port
        self.m3_port_candidates = m3_usb_port_candidates or []
        self.m3_serial: Optional[M3USBSerial] = None
        self.m3_connected = False
        self.m3_port_in_use: Optional[str] = None
        self._last_m3_reconnect_attempt = 0.0
        self._status_callback = None

        # Cached status values
        self.m1_status = 0
        self.m2_status = 0
        self.m3_status = 0

        self.m2_position_mm = 0.0
        self.m3_position_mm = 0.0  # Kept in mm for compatibility
        self.m3_position_in = 0.0   # Source of truth from encoder

        # Heartbeat tracking
        self._last_heartbeat_a = 0
        self._last_heartbeat_b = 0
        self._last_heartbeat_check = time.monotonic()

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # ESP32-A USB serial (blade + fixture)
        self.esp32a_serial = ESP32AUSBSerial(
            port=esp32a_usb_port,
            port_candidates=esp32a_usb_port_candidates or []
        )
        self.esp32a_connected = False

    def start(self):
        """Start background heartbeat monitoring and connect M3 USB serial."""
        if self._running:
            return

        # Connect ESP32-A USB Serial (blade + fixture)
        if self.esp32a_serial.connect():
            self.esp32a_connected = True
            logger.info("ESP32-A USB Serial connected successfully")
        else:
            self.esp32a_connected = False
            logger.error("ESP32-A USB Serial connection failed")

        # Connect M3 USB Serial
        if self._connect_m3_serial():
            logger.info(f"M3 USB Serial connected successfully on {self.m3_port_in_use}")
        else:
            logger.error("M3 USB Serial connection failed")

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("AxisGateway started")

    def stop(self):
        """Stop background monitoring and disconnect M3 USB serial."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

        # Disconnect USB Serial devices
        self.esp32a_serial.disconnect()
        self._disconnect_m3_serial()

        logger.info("AxisGateway stopped")

    def _get_m3_port_scan_list(self) -> List[str]:
        """Build an ordered list of USB serial ports to try."""
        candidates = []

        if self.m3_port_default:
            candidates.append(self.m3_port_default)

        for port in self.m3_port_candidates:
            if port not in candidates:
                candidates.append(port)

        auto_ports = sorted(glob('/dev/ttyUSB*') + glob('/dev/ttyACM*'))
        for port in auto_ports:
            if port not in candidates:
                candidates.append(port)

        return candidates

    def set_status_callback(self, callback):
        """Register callback for status messages (for web monitor)."""
        self._status_callback = callback

    def _ensure_esp32a(self) -> bool:
        """Ensure ESP32-A USB connection is ready."""
        if not self.esp32a_serial:
            return False

        if not self.esp32a_serial.ensure_connection():
            logger.error("ESP32-A USB serial not connected")
            self.esp32a_connected = False
            return False

        self.esp32a_connected = True
        return True

    def _disconnect_m3_serial(self):
        """Disconnect current M3 serial connection."""
        if self.m3_serial:
            try:
                self.m3_serial.disconnect()
            except Exception as e:
                logger.error(f"M3 USB Serial disconnect error: {e}")
        self.m3_serial = None
        self.m3_connected = False
        self.m3_port_in_use = None

    def _connect_m3_serial(self) -> bool:
        """Attempt to connect to M3 USB serial on any available port."""
        ports_to_try = self._get_m3_port_scan_list()
        for port in ports_to_try:
            try:
                logger.info(f"Attempting M3 USB Serial connection on {port}...")
                serial_driver = M3USBSerial(port=port)
                serial_driver.set_status_callback(self._handle_m3_status_message)
                if serial_driver.connect():
                    self.m3_serial = serial_driver
                    self.m3_connected = True
                    self.m3_port_in_use = port
                    self._last_m3_reconnect_attempt = time.monotonic()
                    logger.info(f"M3 USB Serial connected on {port}")
                    return True
            except Exception as e:
                logger.error(f"M3 USB Serial connection attempt failed on {port}: {e}")

        self.m3_serial = None
        self.m3_connected = False
        self.m3_port_in_use = None
        return False

    def _is_m3_serial_healthy(self) -> bool:
        """Check if M3 serial driver is connected and port open."""
        return (
            self.m3_connected and
            self.m3_serial is not None and
            self.m3_serial.is_connected()
        )

    def _handle_m3_status_message(self, message: str):
        """Forward M3 status/handshake messages."""
        logger.info(f"M3: {message}")
        if self._status_callback:
            try:
                self._status_callback(message)
            except Exception as exc:
                logger.error(f"Status callback error: {exc}")

    def _monitor_loop(self):
        """Background loop for heartbeat monitoring."""
        while self._running:
            try:
                now = time.monotonic()

                if not self._is_m3_serial_healthy():
                    if now - self._last_m3_reconnect_attempt > 2.0:
                        logger.warning("M3 USB Serial disconnected, attempting reconnect...")
                        self._disconnect_m3_serial()
                        self._connect_m3_serial()

                if now - self._last_heartbeat_check >= self.heartbeat_check_s:
                    self._check_heartbeats()
                    self._last_heartbeat_check = now

                time.sleep(0.1)

            except Exception as e:
                logger.error(f"AxisGateway monitor error: {e}")

    def _check_heartbeats(self):
        """Check ESP32 heartbeat counters."""
        if self._ensure_esp32a():
            status = self.esp32a_serial.query_status()
            if status.raw_line:
                logger.debug(f"ESP32-A STATUS: {status.raw_line}")

    # ========== M1 Blade Motor ==========

    def m1_start(self, rpm: int, ramp_ms: int = 200) -> bool:
        """
        Start blade motor.

        Args:
            rpm: Target RPM (500-6000)
            ramp_ms: Acceleration ramp time in milliseconds

        Returns:
            True if command sent successfully
        """
        logger.info(f"M1 START: {rpm} RPM, ramp {ramp_ms} ms")

        if not self._ensure_esp32a():
            return False

        success, msg = self.esp32a_serial.set_m1_rpm(rpm)
        if not success:
            logger.error(f"M1 start failed: {msg}")
        return success

    def m1_stop(self) -> bool:
        """Stop blade motor."""
        logger.info("M1 STOP")
        if not self._ensure_esp32a():
            return False
        success, msg = self.esp32a_serial.stop_m1()
        if not success:
            logger.error(f"M1 stop failed: {msg}")
        return success

    def m1_clear_fault(self) -> bool:
        """Clear M1 fault."""
        logger.info("M1 CLEAR_FAULT")
        return self.m1_stop()

    def m1_get_status(self) -> Optional[Dict[str, bool]]:
        """
        Get M1 status flags.

        Returns:
            Dictionary with keys: running, fault, ready
        """
        if not self._ensure_esp32a():
            return None

        status = self.esp32a_serial.query_status()
        with self._lock:
            self.m1_status = 1 if status.m1_running else 0

        return {
            'running': status.m1_running,
            'fault': False,
            'ready': True,
        }

    # ========== M2 Fixture Motor ==========

    def m2_set_velocity(self, vel_mm_s: float, accel_mm_s2: float) -> bool:
        """
        Set M2 velocity and acceleration parameters.

        Args:
            vel_mm_s: Velocity in mm/s
            accel_mm_s2: Acceleration in mm/s^2

        Returns:
            True if successful
        """
        if not self._ensure_esp32a():
            return False

        logger.info(f"M2 velocity: {vel_mm_s} mm/s (USB serial)")
        success, msg = self.esp32a_serial.set_m2_velocity(vel_mm_s)
        if not success:
            logger.error(f"M2 velocity set failed: {msg}")
        return success

    def m2_feed_forward(self) -> bool:
        """Command M2 to feed forward until Sensor3."""
        logger.info("M2 FEED_FWD (until S3)")
        if not self._ensure_esp32a():
            return False
        success, msg = self.esp32a_serial.feed_forward()
        if not success:
            logger.error(f"M2 feed forward failed: {msg}")
        return success

    def m2_feed_reverse(self) -> bool:
        """Command M2 to feed reverse until Sensor2."""
        logger.info("M2 FEED_REV (until S2)")
        if not self._ensure_esp32a():
            return False
        success, msg = self.esp32a_serial.feed_reverse()
        if not success:
            logger.error(f"M2 feed reverse failed: {msg}")
        return success

    def m2_stop(self) -> bool:
        """Stop M2 fixture motor."""
        logger.info("M2 STOP")
        if not self._ensure_esp32a():
            return False
        success, msg = self.esp32a_serial.stop_m2()
        if not success:
            logger.error(f"M2 stop failed: {msg}")
        return success

    def m2_jog_forward(self, vel_mm_s: float) -> bool:
        """Jog M2 forward at specified velocity."""
        logger.info(f"M2 JOG_FWD: {vel_mm_s} mm/s")
        if not self._ensure_esp32a():
            return False

        success, msg = self.esp32a_serial.set_m2_velocity(vel_mm_s)
        if not success:
            logger.error(f"M2 jog forward velocity failed: {msg}")
            return False
        success, msg = self.esp32a_serial.feed_forward()
        if not success:
            logger.error(f"M2 jog forward command failed: {msg}")
        return success

    def m2_jog_reverse(self, vel_mm_s: float) -> bool:
        """Jog M2 reverse at specified velocity."""
        logger.info(f"M2 JOG_REV: {vel_mm_s} mm/s")
        if not self._ensure_esp32a():
            return False

        success, msg = self.esp32a_serial.set_m2_velocity(vel_mm_s)
        if not success:
            logger.error(f"M2 jog reverse velocity failed: {msg}")
            return False
        success, msg = self.esp32a_serial.feed_reverse()
        if not success:
            logger.error(f"M2 jog reverse command failed: {msg}")
        return success

    def m2_get_status(self) -> Optional[Dict[str, bool]]:
        """
        Get M2 status flags.

        Returns:
            Dictionary with keys: in_motion, at_s2, at_s3, fault, homed
        """
        if not self._ensure_esp32a():
            return None

        status = self.esp32a_serial.query_status()
        with self._lock:
            self.m2_status = 1 if status.m2_in_motion else 0

        return {
            'in_motion': status.m2_in_motion,
            'at_s2': False,
            'at_s3': False,
            'fault': False,
            'homed': True,
        }

    # ========== M3 Backstop Motor (USB Serial with AS5600 Encoder) ==========

    def m3_goto(self, target_mm: float, vel_mm_s: float, accel_mm_s2: float) -> bool:
        """
        Command M3 to move to target position (closed-loop with encoder).

        Args:
            target_mm: Target position in mm
            vel_mm_s: Velocity in mm/s (converted to inches/sec)
            accel_mm_s2: Acceleration (not used by ESP32B v8.0)

        Returns:
            True if successful
        """
        if not self.m3_connected:
            logger.error("M3: USB serial not connected")
            return False

        # Convert mm to inches for ESP32B v8.0
        target_in = target_mm * MM_TO_INCHES
        vel_ips = vel_mm_s * MM_TO_INCHES

        logger.info(f"M3 GOTO: {target_mm:.2f} mm ({target_in:.3f} in) @ {vel_mm_s:.1f} mm/s ({vel_ips:.2f} in/s)")

        # Set velocity first
        success, msg = self.m3_serial.set_velocity(vel_ips)
        if not success:
            logger.error(f"M3 set velocity failed: {msg}")
            return False

        # Send goto command (with wait for completion)
        success, msg = self.m3_serial.goto_position(target_in, wait_for_completion=True)
        if success:
            logger.info(f"M3: {msg}")
        else:
            logger.error(f"M3: {msg}")

        return success

    def m3_home(self) -> bool:
        """Command M3 to home (reset encoder to 0)."""
        if not self.m3_connected:
            logger.error("M3: USB serial not connected")
            return False

        logger.info("M3 HOME")
        success, msg = self.m3_serial.home()
        if success:
            logger.info(f"M3: {msg}")
            # Update cached position when homed
            with self._lock:
                self.m3_position_mm = 0.0
        else:
            logger.error(f"M3: {msg}")

        return success

    def m3_stop(self) -> bool:
        """Stop M3 backstop motor."""
        if not self.m3_connected:
            logger.error("M3: USB serial not connected")
            return False

        logger.info("M3 STOP")
        success, msg = self.m3_serial.stop()
        if success:
            logger.info(f"M3: {msg}")
        else:
            logger.error(f"M3: {msg}")

        return success

    def m3_get_position(self) -> Optional[float]:
        """
        Get M3 current position from encoder.

        Returns:
            Position in mm (converted from inches), or None on error
        """
        if not self.m3_connected:
            return None

        # Get position from automatic updates (inches)
        pos_in = self.m3_serial.get_position()

        # Convert to mm for compatibility with rest of system
        pos_mm = pos_in * INCHES_TO_MM

        with self._lock:
            self.m3_position_in = pos_in
            self.m3_position_mm = pos_mm

        return pos_mm

    def m3_get_status(self) -> Optional[Dict[str, bool]]:
        """
        Get M3 status flags from USB serial.

        Returns:
            Dictionary with keys: in_motion, homed, at_target, fault, encoder_detected,
            plus position/encoder telemetry when available.
        """
        if not self.m3_connected:
            return None

        status_dict = self.m3_serial.get_status()

        if status_dict is None:
            return None

        position_in = status_dict.get('position_in', None)
        velocity_ips = status_dict.get('velocity_ips', None)
        encoder_counts = status_dict.get('encoder_counts', None)
        motor_steps = status_dict.get('motor_steps', None)
        last_update = status_dict.get('last_update', None)

        # Cache latest position for other services
        if position_in is not None:
            with self._lock:
                self.m3_position_in = position_in
                self.m3_position_mm = position_in * INCHES_TO_MM

        # Map to expected format
        return {
            'in_motion': status_dict.get('state') == 'MOVING',
            'homed': True,  # Always true for encoder-based system
            'at_target': not (status_dict.get('state') == 'MOVING'),
            'fault': False,  # TODO: Add fault detection
            'limit_min': False,  # Not implemented in USB firmware
            'limit_max': False,  # Not implemented in USB firmware
            'encoder_detected': status_dict.get('encoder_counts', 0) != 0 or status_dict.get('last_update', 0) > 0,
            'position_in': position_in,
            'velocity_ips': velocity_ips,
            'encoder_counts': encoder_counts,
            'motor_steps': motor_steps,
            'last_update': last_update,
        }

    def m3_reset_encoder(self) -> bool:
        """
        Reset M3 encoder position to 0 (without homing motor).

        Returns:
            True if successful
        """
        if not self.m3_connected:
            logger.error("M3: USB serial not connected")
            return False

        logger.info("M3 RESET ENCODER")
        success, msg = self.m3_serial.reset_encoder()
        if success:
            logger.info(f"M3: {msg}")
        else:
            logger.error(f"M3: {msg}")

        return success

    # ========== Emergency Stop ==========

    def stop_all_motors(self):
        """Stop all motors gracefully (for pause)."""
        logger.info("STOPPING ALL MOTORS (PAUSE)")

        self.m1_stop()
        self.m2_stop()
        self.m3_stop()

    def emergency_stop_all(self):
        """Emergency stop all motors (Category 0)."""
        logger.warning("EMERGENCY STOP ALL MOTORS")

        self.m1_stop()
        self.m2_stop()
        self.m3_stop()

    def __repr__(self) -> str:
        return f"<AxisGateway esp32a={self.esp32a_id}, esp32b={self.esp32b_id}>"
