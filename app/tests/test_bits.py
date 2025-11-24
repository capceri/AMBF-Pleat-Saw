"""
Unit tests for bit manipulation utilities.
"""

import pytest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.bits import (
    get_bit,
    set_bit,
    toggle_bit,
    bits_to_dict,
    dict_to_bits,
    bits_to_list,
    list_to_bits,
    format_bits,
    count_set_bits,
    get_changed_bits,
)


def test_get_bit():
    """Test getting individual bits."""
    assert get_bit(0b0001, 0) == True
    assert get_bit(0b0001, 1) == False
    assert get_bit(0b1000, 3) == True
    assert get_bit(0x8007, 0) == True
    assert get_bit(0x8007, 15) == True


def test_set_bit():
    """Test setting individual bits."""
    assert set_bit(0b0000, 0, True) == 0b0001
    assert set_bit(0b0001, 1, True) == 0b0011
    assert set_bit(0b0011, 0, False) == 0b0010
    assert set_bit(0xFFFF, 3, False) == 0xFFF7


def test_toggle_bit():
    """Test toggling individual bits."""
    assert toggle_bit(0b0000, 0) == 0b0001
    assert toggle_bit(0b0001, 0) == 0b0000
    assert toggle_bit(0b0010, 0) == 0b0011


def test_bits_to_dict():
    """Test converting bit-packed value to dictionary."""
    bit_map = {'start': 0, 'sensor2': 1, 'sensor3': 2, 'light_curtain': 14, 'safety': 15}

    result = bits_to_dict(0xC007, bit_map)  # Added bit 14 (0x4000) to include light_curtain

    assert result['start'] == True
    assert result['sensor2'] == True
    assert result['sensor3'] == True
    assert result['light_curtain'] == True
    assert result['safety'] == True

    result = bits_to_dict(0x0000, bit_map)

    assert result['start'] == False
    assert result['sensor2'] == False
    assert result['sensor3'] == False
    assert result['light_curtain'] == False
    assert result['safety'] == False


def test_dict_to_bits():
    """Test converting dictionary to bit-packed value."""
    bit_map = {'clamp': 0, 'air_jet': 1, 'green_solid': 2}

    states = {'clamp': True, 'air_jet': False, 'green_solid': True}
    result = dict_to_bits(states, bit_map)

    assert result == 0b0101  # Bits 0 and 2 set

    states = {'clamp': True, 'air_jet': True, 'green_solid': True}
    result = dict_to_bits(states, bit_map)

    assert result == 0b0111  # All 3 bits set


def test_bits_to_list():
    """Test converting bit-packed value to list."""
    result = bits_to_list(0b0101, 4)
    assert result == [True, False, True, False]

    result = bits_to_list(0x000F, 8)
    assert result == [True, True, True, True, False, False, False, False]


def test_list_to_bits():
    """Test converting list to bit-packed value."""
    result = list_to_bits([True, False, True, False])
    assert result == 0b0101

    result = list_to_bits([True, True, True, True])
    assert result == 0b1111


def test_format_bits():
    """Test formatting bits as binary string."""
    assert format_bits(0b0101, 4) == '0101'
    assert format_bits(0x8007, 16) == '1000000000000111'


def test_count_set_bits():
    """Test counting set bits."""
    assert count_set_bits(0b0000) == 0
    assert count_set_bits(0b0001) == 1
    assert count_set_bits(0b0101) == 2
    assert count_set_bits(0b1111) == 4
    assert count_set_bits(0x8007) == 4


def test_get_changed_bits():
    """Test detecting changed bits."""
    old = 0b0001
    new = 0b0011

    changed = get_changed_bits(old, new, 4)

    assert len(changed) == 1
    assert 1 in changed
    assert changed[1] == True

    old = 0b1111
    new = 0b0111

    changed = get_changed_bits(old, new, 4)

    assert len(changed) == 1
    assert 3 in changed
    assert changed[3] == False
