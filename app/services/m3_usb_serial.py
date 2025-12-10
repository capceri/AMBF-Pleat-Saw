"""
ESP32B M3 Motor USB Serial Driver with AS5600 Encoder

USB serial communication with ESP32B backstop motor controller v8.0.
Features built-in AS5600 encoder for closed-loop position control.

Protocol:
- Commands: g<inches>, h, s, v<ips>, r, ?
- Automatic position updates at 10 Hz from ESP32B
- Units: INCHES (matching operator interface)

Author: Claude Code
Date: 2025-11-17
"""

import serial
import time
import logging
import threading
from typing import Tuple, Optional
from collections import deque

logger = logging.getLogger(__name__)


class M3USBSerial:
    """
    USB Serial driver for ESP32B M3 backstop motor with AS5600 encoder.

    ESP32B firmware v8.0 provides:
    - Built-in encoder reading (AS5600 on I2C)
    - Closed-loop position control
    - Automatic position updates at 10 Hz
    - All units in INCHES
    """

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, status_callback=None):
        """
        Initialize USB serial connection to ESP32B.

        Args:
            port: USB serial port (e.g., '/dev/ttyUSB0')
            baudrate: Serial baud rate (115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.status_callback = status_callback

        # Current state from automatic updates
        self.position_in = 0.0
        self.velocity_ips = 0.0
        self.encoder_counts = 0
        self.motor_steps = 0
        self.last_update_time = 0.0
        self.in_motion = False

        # Background thread for reading position updates
        self.reader_thread = None
        self.reader_running = False
        self.reader_lock = threading.Lock()

        # Response queue for commands
        self.response_queue = deque(maxlen=20)

        # Default velocity
        self.default_velocity_ips = 1.0

        # Closed-loop parameters (handled by ESP32B firmware)
        self.position_tolerance_in = 0.010  # ±0.010 inch
        self.max_position_error_in = 0.200  # Maximum error before alarm

    def connect(self) -> bool:
        """
        Connect to ESP32B over USB serial and start background reader.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,  # Non-blocking for reader thread
                write_timeout=2.0
            )

            # Wait for ESP32B boot
            time.sleep(1.0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            # Verify we are talking to ESP32B (ID query) before starting reader
            self.serial.write(b"I\n")
            self.serial.flush()
            id_deadline = time.time() + 1.0
            module_id = None
            while time.time() < id_deadline:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                logger.debug("%s RX: %s", self.port, line)
                if line.startswith('ID:'):
                    module_id = line.split(':', 1)[1].strip()
                    break

            if module_id != 'ESP32B':
                logger.error("M3 USB Serial: %s reported ID '%s' (expected ESP32B)", self.port, module_id)
                self.serial.close()
                self.serial = None
                return False

            # Start background reader thread AFTER successful ID
            self.reader_running = True
            self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.reader_thread.start()

            time.sleep(0.2)  # Give reader thread time to start
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            # Test connection with status query
            response = self._send_command('?', wait_for_response=True, timeout=2.0)
            if response and ('STATUS' in response or 'READY' in response):
                self.connected = True
                logger.info(f"M3 USB Serial connected on {self.port}")
                logger.info(f"ESP32B firmware: {response}")
                return True
            else:
                logger.error(f"M3 USB Serial: No valid response from ESP32B")
                # Stop reader thread since connection failed
                self.reader_running = False
                if self.reader_thread:
                    self.reader_thread.join(timeout=1.0)
                return False

        except Exception as e:
            logger.error(f"M3 USB Serial connection failed: {e}")
            self.connected = False
            self.serial = None
            return False

    def disconnect(self):
        """Close USB serial connection and stop background reader."""
        self.reader_running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=2.0)
            self.reader_thread = None

        if self.serial:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
            self.serial = None

        self.connected = False
        logger.info("M3 USB Serial disconnected")

    def is_connected(self) -> bool:
        """Return True if serial port is open and reader active."""
        return self.connected and self.serial is not None and self.serial.is_open

    def _reader_loop(self):
        """
        Background thread continuously reads from serial port.

        Handles:
        - Automatic position updates: "POS <inches> <velocity> <counts> <steps>"
        - Command responses: AT_TARGET, MOVING, STOPPED, etc.
        """
        logger.info("M3 reader thread started")

        while self.reader_running and self.serial and self.serial.is_open:
            try:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()

                if not line:
                    continue

                # Parse automatic position updates
                if line.startswith('POS '):
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            with self.reader_lock:
                                self.position_in = float(parts[1])
                                self.velocity_ips = float(parts[2])
                                self.encoder_counts = int(parts[3])
                                self.motor_steps = int(parts[4])
                                self.last_update_time = time.time()
                                self.in_motion = abs(self.velocity_ips) > 0.01
                        except (ValueError, IndexError) as e:
                            logger.debug(f"M3 parse error: {line} - {e}")

                # All other lines are command responses
                else:
                    with self.reader_lock:
                        self.response_queue.append(line)
                    logger.debug(f"M3 response: {line}")

            except (serial.SerialException, OSError) as e:
                if self.reader_running:
                    logger.error(f"M3 reader error: {e}")
                self.connected = False
                break
            except Exception as e:
                if self.reader_running:
                    logger.error(f"M3 reader error: {e}")
                time.sleep(0.1)

        logger.info("M3 reader thread stopped")
        self.reader_running = False

    def set_status_callback(self, callback):
        """Register callback for status/handshake messages."""
        self.status_callback = callback

    def _send_command(self, command: str, wait_for_response: bool = True, timeout: float = 2.0) -> Optional[str]:
        """
        Send command to ESP32B and optionally wait for response.

        Args:
            command: Command string (e.g., 'g12.5', 'h', 's')
            wait_for_response: Wait for response line
            timeout: Response timeout in seconds

        Returns:
            Response string if wait_for_response=True, None otherwise
        """
        if not self.serial or not self.serial.is_open:
            logger.error("M3 USB Serial not connected")
            return None

        try:
            # Clear response queue
            with self.reader_lock:
                self.response_queue.clear()

            # Send command
            self.serial.write(f"{command}\n".encode())
            self.serial.flush()
            logger.debug(f"M3 sent: {command}")

            if wait_for_response:
                # Wait for response from reader thread
                start_time = time.time()
                while time.time() - start_time < timeout:
                    with self.reader_lock:
                        if self.response_queue:
                            line = self.response_queue.popleft()
                            if self.status_callback:
                                self.status_callback(line)
                            if line.startswith('CMD '):
                                continue
                            return line
                    time.sleep(0.01)

                logger.warning(f"M3 timeout waiting for response to: {command}")
                return None

            return None

        except (serial.SerialException, OSError) as e:
            logger.error(f"M3 USB Serial communication error: {e}")
            self.connected = False
            if self.serial:
                try:
                    self.serial.close()
                except Exception:
                    pass
                self.serial = None
            self.reader_running = False
            return None
        except Exception as e:
            logger.error(f"M3 USB Serial communication error: {e}")
            return None

    def wait_for_completion(self, timeout: float = 30.0) -> Tuple[bool, Optional[str]]:
        """
        Wait for movement to complete (AT_TARGET response).

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (success, message)
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self.reader_lock:
                    if self.response_queue:
                        response = self.response_queue.popleft()
                        if self.status_callback:
                            self.status_callback(response)

                    if 'AT_TARGET' in response:
                        return True, response

                    elif 'ERROR' in response:
                        return False, response

                    elif 'CORRECTING' in response:
                        # Closed-loop correction in progress
                        logger.info(f"M3: {response}")
                        continue
                    elif response.startswith('CMD '):
                        continue

            time.sleep(0.01)

        return False, "TIMEOUT: Movement did not complete"

    def get_position(self) -> float:
        """
        Get current position from automatic updates.

        Returns:
            Position in inches
        """
        with self.reader_lock:
            return self.position_in

    def get_velocity(self) -> float:
        """
        Get current velocity from automatic updates.

        Returns:
            Velocity in inches/sec
        """
        with self.reader_lock:
            return self.velocity_ips

    def is_moving(self) -> bool:
        """
        Check if motor is currently moving.

        Returns:
            True if moving, False if stopped
        """
        with self.reader_lock:
            return self.in_motion

    def goto_position(self, position_in: float, wait_for_completion: bool = True) -> Tuple[bool, str]:
        """
        Move to position in inches (closed-loop with encoder verification).

        The ESP32B firmware handles closed-loop control automatically:
        1. Moves motor to target position
        2. Compares encoder reading to target
        3. Sends correction moves if needed
        4. Returns AT_TARGET when within tolerance

        Args:
            position_in: Target position in inches
            wait_for_completion: Wait for AT_TARGET response

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.connected:
            return False, "Not connected"

        logger.info(f"M3: Moving to {position_in:.3f} inches")

        response = self._send_command(f'g{position_in:.3f}')

        if not response:
            return False, "No response to goto command"

        # Already at target
        if 'AT_TARGET' in response:
            logger.info(f"M3: {response}")
            return True, response

        # Movement started
        if 'MOVING' in response:
            logger.info(f"M3: {response}")

            if wait_for_completion:
                success, message = self.wait_for_completion(timeout=30.0)
                if success:
                    logger.info(f"M3: Movement complete - {message}")
                else:
                    logger.error(f"M3: Movement failed - {message}")
                return success, message
            else:
                return True, "Moving"

        # Unexpected response
        return False, f"Unexpected response: {response}"

    def home(self) -> Tuple[bool, str]:
        """
        Home M3 motor (reset encoder position to 0).

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.connected:
            return False, "Not connected"

        response = self._send_command('h', wait_for_response=True, timeout=1.0)

        # Accept immediate HOMED or HOMING, then wait for HOMED confirmation
        if response and ('HOMED' in response or 'HOMING' in response):
            deadline = time.time() + 10.0
            while time.time() < deadline:
                line = None
                with self.reader_lock:
                    if self.response_queue:
                        line = self.response_queue.popleft()
                if line:
                    if 'HOMED' in line:
                        logger.info("M3: Homed successfully")
                        return True, "Homed"
                    if 'ERROR' in line:
                        return False, line
                time.sleep(0.05)

            return False, "Home timeout waiting for HOMED"

        return False, f"Home failed: {response}"

    def stop(self) -> Tuple[bool, str]:
        """
        Stop M3 motor immediately.

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.connected:
            return False, "Not connected"

        response = self._send_command('s')
        if response and 'STOPPED' in response:
            logger.info(f"M3: {response}")
            return True, response
        return False, f"Stop failed: {response}"

    def set_velocity(self, velocity_ips: float) -> Tuple[bool, str]:
        """
        Set M3 motor velocity.

        Args:
            velocity_ips: Velocity in inches/sec

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.connected:
            return False, "Not connected"

        response = self._send_command(f'v{velocity_ips:.2f}')
        if response and 'VELOCITY' in response:
            self.default_velocity_ips = velocity_ips
            logger.info(f"M3: Velocity set to {velocity_ips:.2f} in/s")
            return True, response
        return False, f"Set velocity failed: {response}"

    def reset_encoder(self) -> Tuple[bool, str]:
        """
        Reset encoder position to 0 (without homing motor).

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.connected:
            return False, "Not connected"

        response = self._send_command('r')
        if response and 'ENCODER_RESET' in response:
            logger.info("M3: Encoder reset")
            return True, "Encoder reset"
        return False, f"Reset failed: {response}"

    def get_status(self) -> Optional[dict]:
        """
        Query M3 motor status (detailed).

        Returns:
            Dict with status info, or None if failed
        """
        if not self.connected:
            return None

        response = self._send_command('?', timeout=1.0)
        if response and 'STATUS' in response:
            # Parse response: "STATUS IDLE | Motor: 1.250 in (12700 steps) | Encoder: 1.252 in (8621 counts) | ..."
            status = {
                'raw_response': response,
                'state': 'UNKNOWN',
                'position_in': self.position_in,
                'velocity_ips': self.velocity_ips,
                'encoder_counts': self.encoder_counts,
                'motor_steps': self.motor_steps
            }

            # Parse state
            if 'MOVING' in response:
                status['state'] = 'MOVING'
            elif 'IDLE' in response:
                status['state'] = 'IDLE'

            return status

        # Return current state from automatic updates
        with self.reader_lock:
            return {
                'state': 'MOVING' if self.in_motion else 'IDLE',
                'position_in': self.position_in,
                'velocity_ips': self.velocity_ips,
                'encoder_counts': self.encoder_counts,
                'motor_steps': self.motor_steps,
                'last_update': self.last_update_time
            }
