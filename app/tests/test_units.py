"""
Unit tests for unit conversion utilities.
"""

import pytest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.units import (
    mm_to_inches,
    inches_to_mm,
    mm_to_modbus,
    modbus_to_mm,
    mm_s_to_modbus,
    modbus_to_mm_s,
    split_int32,
    combine_int32,
    format_inches,
    format_mm,
    clamp,
    rpm_to_hz,
    hz_to_rpm,
)


def test_mm_to_inches():
    """Test mm to inches conversion."""
    assert abs(mm_to_inches(25.4) - 1.0) < 0.001
    assert abs(mm_to_inches(50.8) - 2.0) < 0.001
    assert abs(mm_to_inches(0.0) - 0.0) < 0.001


def test_inches_to_mm():
    """Test inches to mm conversion."""
    assert abs(inches_to_mm(1.0) - 25.4) < 0.001
    assert abs(inches_to_mm(2.0) - 50.8) < 0.001
    assert abs(inches_to_mm(0.0) - 0.0) < 0.001


def test_mm_to_modbus():
    """Test mm to Modbus fixed-point conversion."""
    assert mm_to_modbus(1.0) == 1000
    assert mm_to_modbus(25.4) == 25400
    assert mm_to_modbus(0.001) == 1
    assert mm_to_modbus(152.500) == 152500


def test_modbus_to_mm():
    """Test Modbus fixed-point to mm conversion."""
    assert abs(modbus_to_mm(1000) - 1.0) < 0.001
    assert abs(modbus_to_mm(25400) - 25.4) < 0.001
    assert abs(modbus_to_mm(152500) - 152.5) < 0.001


def test_mm_s_to_modbus():
    """Test mm/s to Modbus fixed-point conversion."""
    assert mm_s_to_modbus(120.0) == 120000
    assert mm_s_to_modbus(1.5) == 1500


def test_modbus_to_mm_s():
    """Test Modbus fixed-point to mm/s conversion."""
    assert abs(modbus_to_mm_s(120000) - 120.0) < 0.001
    assert abs(modbus_to_mm_s(1500) - 1.5) < 0.001


def test_split_int32():
    """Test splitting 32-bit integer into 16-bit words."""
    low, high = split_int32(0x12345678)
    assert low == 0x5678
    assert high == 0x1234

    low, high = split_int32(152500)
    assert combine_int32(low, high) == 152500

    # Test negative number
    low, high = split_int32(-1000)
    value = combine_int32(low, high)
    assert value == -1000


def test_combine_int32():
    """Test combining 16-bit words into 32-bit integer."""
    assert combine_int32(0x5678, 0x1234) == 0x12345678
    assert combine_int32(0xFFFF, 0xFFFF) == -1


def test_split_combine_roundtrip():
    """Test split/combine round trip."""
    test_values = [0, 1, -1, 1000, -1000, 152500, -152500, 0x7FFFFFFF, -0x80000000]

    for value in test_values:
        low, high = split_int32(value)
        result = combine_int32(low, high)
        assert result == value, f"Failed for {value}"


def test_format_inches():
    """Test formatting inches for display."""
    assert format_inches(1.2345, 3) == "1.234"  # Python uses banker's rounding (round half to even)
    assert format_inches(1.2355, 3) == "1.236"  # Rounds up
    assert format_inches(0.0, 3) == "0.000"
    assert format_inches(12.3, 3) == "12.300"


def test_format_mm():
    """Test formatting mm for display."""
    assert format_mm(123.456, 3) == "123.456"
    assert format_mm(0.0, 3) == "0.000"


def test_clamp():
    """Test clamping values."""
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
    assert clamp(5.5, 0.0, 10.0) == 5.5


def test_rpm_to_hz():
    """Test RPM to Hz conversion."""
    assert abs(rpm_to_hz(60.0) - 1.0) < 0.001
    assert abs(rpm_to_hz(3600.0) - 60.0) < 0.001


def test_hz_to_rpm():
    """Test Hz to RPM conversion."""
    assert abs(hz_to_rpm(1.0) - 60.0) < 0.001
    assert abs(hz_to_rpm(60.0) - 3600.0) < 0.001
