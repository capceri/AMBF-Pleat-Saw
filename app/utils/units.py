"""
Unit conversion utilities for Pleat Saw controller.

All internal calculations use millimeters.
Modbus communication uses fixed-point integers (mm × 1000).
HMI customer display uses inches.
"""

from typing import Union


# Conversion constants
MM_PER_INCH = 25.4
INCH_PER_MM = 1.0 / MM_PER_INCH

# Fixed-point scaling for Modbus
MODBUS_SCALE = 1000


def mm_to_inches(mm: float) -> float:
    """
    Convert millimeters to inches.

    Args:
        mm: Distance in millimeters

    Returns:
        Distance in inches
    """
    return mm * INCH_PER_MM


def inches_to_mm(inches: float) -> float:
    """
    Convert inches to millimeters.

    Args:
        inches: Distance in inches

    Returns:
        Distance in millimeters
    """
    return inches * MM_PER_INCH


def mm_to_modbus(mm: float) -> int:
    """
    Convert millimeters to Modbus fixed-point integer (mm × 1000).

    Args:
        mm: Distance in millimeters

    Returns:
        Fixed-point integer (mm × 1000)
    """
    return int(round(mm * MODBUS_SCALE))


def modbus_to_mm(value: int) -> float:
    """
    Convert Modbus fixed-point integer to millimeters.

    Args:
        value: Fixed-point integer (mm × 1000)

    Returns:
        Distance in millimeters
    """
    return float(value) / MODBUS_SCALE


def mm_s_to_modbus(mm_s: float) -> int:
    """
    Convert mm/s to Modbus fixed-point integer (mm/s × 1000).

    Args:
        mm_s: Velocity in mm/s

    Returns:
        Fixed-point integer (mm/s × 1000)
    """
    return int(round(mm_s * MODBUS_SCALE))


def modbus_to_mm_s(value: int) -> float:
    """
    Convert Modbus fixed-point integer to mm/s.

    Args:
        value: Fixed-point integer (mm/s × 1000)

    Returns:
        Velocity in mm/s
    """
    return float(value) / MODBUS_SCALE


def split_int32(value: int) -> tuple[int, int]:
    """
    Split a signed 32-bit integer into low and high 16-bit words for Modbus.

    Args:
        value: 32-bit signed integer

    Returns:
        Tuple of (low_word, high_word)
    """
    # Handle negative numbers with two's complement
    if value < 0:
        value = (1 << 32) + value  # Convert to unsigned representation

    low = value & 0xFFFF
    high = (value >> 16) & 0xFFFF

    return (low, high)


def combine_int32(low: int, high: int) -> int:
    """
    Combine low and high 16-bit words into a signed 32-bit integer from Modbus.

    Args:
        low: Low 16-bit word
        high: High 16-bit word

    Returns:
        32-bit signed integer
    """
    value = (high << 16) | low

    # Convert from unsigned to signed if needed
    if value & 0x80000000:
        value = value - (1 << 32)

    return value


def format_inches(inches: float, decimal_places: int = 3) -> str:
    """
    Format inches for HMI display.

    Args:
        inches: Distance in inches
        decimal_places: Number of decimal places (default 3)

    Returns:
        Formatted string (e.g., "12.345")
    """
    return f"{inches:.{decimal_places}f}"


def format_mm(mm: float, decimal_places: int = 3) -> str:
    """
    Format millimeters for HMI engineering display.

    Args:
        mm: Distance in millimeters
        decimal_places: Number of decimal places (default 3)

    Returns:
        Formatted string (e.g., "123.456")
    """
    return f"{mm:.{decimal_places}f}"


def clamp(value: Union[int, float], min_val: Union[int, float], max_val: Union[int, float]) -> Union[int, float]:
    """
    Clamp a value between min and max.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(value, max_val))


def rpm_to_hz(rpm: float) -> float:
    """
    Convert RPM to frequency in Hz.

    Args:
        rpm: Revolutions per minute

    Returns:
        Frequency in Hz
    """
    return rpm / 60.0


def hz_to_rpm(hz: float) -> float:
    """
    Convert frequency in Hz to RPM.

    Args:
        hz: Frequency in Hz

    Returns:
        Revolutions per minute
    """
    return hz * 60.0
