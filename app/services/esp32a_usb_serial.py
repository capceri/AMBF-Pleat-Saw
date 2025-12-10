"""
ESP32-A USB Serial Driver (M1 blade + M2 fixture)

Provides a lightweight wrapper around the ESP32-A firmware's USB protocol:
    I/i       → "ID:ESP32A"
    ?         → "STATUS M1:RUN rpm=1234 | M2:STOP vel=0.0 dir=REV"
    1r<rpm>   → run blade at RPM
    1s        → stop blade
    2v<vel>   → set M2 velocity (mm/s)
    2f / 2b   → feed forward/reverse
    2s        → stop M2
"""

from __future__ import annotations

import glob
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import serial

logger = logging.getLogger(__name__)


@dataclass
class ESP32AStatus:
    """Represents the parsed STATUS line."""

    m1_running: bool = False
    m1_rpm: int = 0
    m2_in_motion: bool = False
    m2_velocity_mm_s: float = 0.0
    m2_direction: str = "STOP"
    raw_line: Optional[str] = None


class ESP32AUSBSerial:
    """Simple USB serial helper for ESP32-A dual-motor board."""

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        port_candidates: Optional[List[str]] = None,
        status_timeout_s: float = 1.0,
    ):
        self.port = port
        self.port_candidates = port_candidates or []
        self.baudrate = baudrate
        self.status_timeout_s = status_timeout_s

        self.serial: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.connected = False
        self.status = ESP32AStatus()

    # ------------------------------------------------------------------ #
    # Connection helpers
    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        """Try to locate and open the ESP32-A port."""
        candidates = []
        if self.port:
            candidates.append(self.port)
        candidates.extend(self.port_candidates)
        auto_ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
        for p in auto_ports:
            if p not in candidates:
                candidates.append(p)

        for candidate in candidates:
            if self._try_port(candidate):
                self.port = candidate
                logger.info("ESP32-A USB connected on %s", candidate)
                self.connected = True
                return True

        logger.error("ESP32-A USB: no matching port found (%s)", candidates)
        self.connected = False
        return False

    def _try_port(self, port: str) -> bool:
        try:
            ser = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=0.3,
                write_timeout=1.0,
            )
        except serial.SerialException as exc:
            logger.debug("ESP32-A USB: %s unavailable (%s)", port, exc)
            return False

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        ser.write(b"I\n")
        ser.flush()

        deadline = time.time() + 1.0
        module_id = None
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            logger.debug("%s RX: %s", port, line)
            if line.startswith("ID:"):
                module_id = line.split(":", 1)[1].strip()
                break

        if module_id == "ESP32A":
            self.serial = ser
            return True

        ser.close()
        return False

    def disconnect(self):
        if self.serial:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
        self.serial = None
        self.connected = False

    def ensure_connection(self) -> bool:
        if self.serial and self.serial.is_open:
            return True
        logger.warning("ESP32-A USB lost connection, attempting reconnect...")
        return self.connect()

    # ------------------------------------------------------------------ #
    # Command/response helpers
    # ------------------------------------------------------------------ #
    def _send_command(
        self,
        command: str,
        expect: Optional[Tuple[str, ...]] = None,
        timeout: float = 1.0,
    ) -> Tuple[bool, str]:
        if not self.ensure_connection():
            return False, "USB not connected"

        with self.lock:
            try:
                self.serial.reset_input_buffer()
                self.serial.write(f"{command}\n".encode("ascii"))
                self.serial.flush()
            except serial.SerialException as exc:
                logger.error("ESP32-A USB write failed: %s", exc)
                self.connected = False
                return False, str(exc)

            responses: List[str] = []
            deadline = time.time() + timeout

            while time.time() < deadline:
                try:
                    line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                except serial.SerialException as exc:
                    self.connected = False
                    return False, str(exc)

                if not line:
                    continue

                responses.append(line)
                self._handle_line(line)

                if expect:
                    if any(line.startswith(prefix) for prefix in expect):
                        return True, line
                else:
                    # For fire-and-forget commands, return immediately after first response
                    return True, line

            if not responses:
                return False, "No response"

            if expect:
                return False, responses[-1]

            return True, responses[-1]

    def _handle_line(self, line: str):
        if line.startswith("STATUS"):
            self.status = self._parse_status(line)

    @staticmethod
    def _parse_status(line: str) -> ESP32AStatus:
        status = ESP32AStatus(raw_line=line)
        try:
            parts = line.replace("STATUS", "").split("|")
            if len(parts) >= 1:
                m1_part = parts[0].strip()
                if "M1" in m1_part:
                    status.m1_running = "RUN" in m1_part
                    if "rpm=" in m1_part:
                        status.m1_rpm = int(m1_part.split("rpm=", 1)[1].split()[0])

            if len(parts) >= 2:
                m2_part = parts[1]
                state_token = m2_part.split()[0] if m2_part else ""
                # In motion only if state token is not STOP
                status.m2_in_motion = state_token and "STOP" not in state_token
                if "vel=" in m2_part:
                    status.m2_velocity_mm_s = float(m2_part.split("vel=", 1)[1].split()[0])
                if "dir=" in m2_part:
                    status.m2_direction = m2_part.split("dir=", 1)[1].strip()
        except Exception as exc:
            logger.debug("ESP32-A status parse error (%s): %s", exc, line)
        return status

    # ------------------------------------------------------------------ #
    # Public API used by AxisGateway
    # ------------------------------------------------------------------ #
    def set_m1_rpm(self, rpm: int) -> Tuple[bool, str]:
        return self._send_command(f"1r{int(rpm)}", expect=("M1_RUN",))

    def stop_m1(self) -> Tuple[bool, str]:
        return self._send_command("1s", expect=("M1_STOPPED",))

    def set_m2_velocity(self, vel_mm_s: float) -> Tuple[bool, str]:
        vel = max(0.0, vel_mm_s)
        return self._send_command(f"2v{vel:.1f}")

    def feed_forward(self) -> Tuple[bool, str]:
        return self._send_command("2f", expect=("M2_FWD",))

    def feed_reverse(self) -> Tuple[bool, str]:
        return self._send_command("2b", expect=("M2_REV",))

    def stop_m2(self) -> Tuple[bool, str]:
        return self._send_command("2s", expect=("M2_STOPPED",))

    def query_status(self) -> ESP32AStatus:
        """Send STATUS command and parse reply."""
        success, resp = self._send_command("?", timeout=self.status_timeout_s)
        if success and isinstance(resp, str) and resp.startswith("STATUS"):
            self.status = self._parse_status(resp)
        return self.status

    def get_status_snapshot(self) -> ESP32AStatus:
        return self.status
