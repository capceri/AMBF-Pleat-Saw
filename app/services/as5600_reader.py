"""
AS5600 Magnetic Encoder Reader for M3 Backstop Position

Reads angular position from AS5600 and converts to linear position in mm.
AS5600 provides 12-bit resolution (0-4095) for 360 degrees.

Author: Claude Code
Date: 2025-11-14
"""

from smbus2 import SMBus
import logging
import time

logger = logging.getLogger(__name__)


class AS5600Reader:
    """
    AS5600 12-bit magnetic encoder reader on Pi I2C bus.
    """

    # AS5600 I2C address
    I2C_ADDRESS = 0x36

    # AS5600 registers
    REG_STATUS = 0x0B
    REG_RAW_ANGLE_HIGH = 0x0C
    REG_RAW_ANGLE_LOW = 0x0D
    REG_ANGLE_HIGH = 0x0E
    REG_ANGLE_LOW = 0x0F

    def __init__(self, i2c_bus: int = 1, counts_per_mm: float = 400.0):
        """
        Initialize AS5600 encoder reader.

        Args:
            i2c_bus: I2C bus number (default: 1 for Raspberry Pi)
            counts_per_mm: Encoder counts per mm of linear motion
                         (default: 400 to match motor steps/mm)
        """
        self.bus = SMBus(i2c_bus)
        self.counts_per_mm = counts_per_mm
        self.zero_offset = 0  # For homing

    def read_raw_angle(self) -> int:
        """
        Read raw 12-bit angle from AS5600 (0-4095).

        Returns:
            Raw angle value (0-4095)
        """
        try:
            high = self.bus.read_byte_data(self.I2C_ADDRESS, self.REG_RAW_ANGLE_HIGH)
            low = self.bus.read_byte_data(self.I2C_ADDRESS, self.REG_RAW_ANGLE_LOW)
            raw_angle = ((high & 0x0F) << 8) | low
            return raw_angle
        except Exception as e:
            logger.error(f"AS5600: Failed to read raw angle: {e}")
            return None

    def read_angle_degrees(self) -> float:
        """
        Read angle in degrees (0-360).

        Returns:
            Angle in degrees
        """
        raw = self.read_raw_angle()
        if raw is None:
            return None
        return (raw / 4095.0) * 360.0

    def read_position(self) -> float:
        """
        Read linear position in mm.

        Converts encoder angle to linear position using counts_per_mm.
        Applies zero offset from homing.

        Returns:
            Position in mm, or None if read failed
        """
        raw = self.read_raw_angle()
        if raw is None:
            return None

        # Convert raw angle to position
        # Assuming linear motion converts to encoder rotation
        position_counts = raw - self.zero_offset
        position_mm = position_counts / self.counts_per_mm

        return position_mm

    def home(self):
        """
        Set current position as zero reference.
        """
        raw = self.read_raw_angle()
        if raw is not None:
            self.zero_offset = raw
            logger.info(f"AS5600: Homed at raw angle {raw}")

    def get_status(self) -> dict:
        """
        Read AS5600 status register.

        Returns:
            Dict with status flags
        """
        try:
            status = self.bus.read_byte_data(self.I2C_ADDRESS, self.REG_STATUS)
            return {
                'magnet_detected': bool(status & 0x20),
                'magnet_too_strong': bool(status & 0x08),
                'magnet_too_weak': bool(status & 0x10),
                'raw_status': status
            }
        except Exception as e:
            logger.error(f"AS5600: Failed to read status: {e}")
            return None

    def close(self):
        """Close I2C bus."""
        self.bus.close()
