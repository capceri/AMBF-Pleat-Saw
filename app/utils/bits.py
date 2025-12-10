"""
Bit manipulation utilities for I/O operations.
Used for N4D3E16 bit-packed input/output registers.
"""

from typing import Dict, List


def get_bit(value: int, bit_index: int) -> bool:
    """
    Get the state of a specific bit in an integer.

    Args:
        value: Integer value
        bit_index: Bit position (0-15)

    Returns:
        True if bit is set, False otherwise
    """
    return bool((value >> bit_index) & 1)


def set_bit(value: int, bit_index: int, state: bool) -> int:
    """
    Set or clear a specific bit in an integer.

    Args:
        value: Integer value
        bit_index: Bit position (0-15)
        state: True to set bit, False to clear

    Returns:
        Modified integer value
    """
    if state:
        return value | (1 << bit_index)
    else:
        return value & ~(1 << bit_index)


def toggle_bit(value: int, bit_index: int) -> int:
    """
    Toggle a specific bit in an integer.

    Args:
        value: Integer value
        bit_index: Bit position (0-15)

    Returns:
        Modified integer value
    """
    return value ^ (1 << bit_index)


def bits_to_dict(value: int, bit_map: Dict[str, int]) -> Dict[str, bool]:
    """
    Convert a bit-packed integer to a dictionary of named boolean values.

    Args:
        value: Bit-packed integer
        bit_map: Dictionary mapping names to bit indices

    Returns:
        Dictionary mapping names to boolean states

    Example:
        >>> bit_map = {"start": 0, "sensor2": 1, "sensor3": 2, "safety": 15}
        >>> bits_to_dict(0x8007, bit_map)
        {'start': True, 'sensor2': True, 'sensor3': True, 'safety': True}
    """
    result = {}
    for name, bit_index in bit_map.items():
        result[name] = get_bit(value, bit_index)
    return result


def dict_to_bits(states: Dict[str, bool], bit_map: Dict[str, int]) -> int:
    """
    Convert a dictionary of named boolean values to a bit-packed integer.

    Args:
        states: Dictionary mapping names to boolean states
        bit_map: Dictionary mapping names to bit indices

    Returns:
        Bit-packed integer

    Example:
        >>> bit_map = {"clamp": 0, "air_jet": 1, "green_solid": 2}
        >>> dict_to_bits({"clamp": True, "air_jet": False, "green_solid": True}, bit_map)
        5  # 0b0101
    """
    value = 0
    for name, state in states.items():
        if name in bit_map:
            bit_index = bit_map[name]
            value = set_bit(value, bit_index, state)
    return value


def bits_to_list(value: int, num_bits: int = 16) -> List[bool]:
    """
    Convert a bit-packed integer to a list of boolean values.

    Args:
        value: Bit-packed integer
        num_bits: Number of bits to extract (default 16)

    Returns:
        List of boolean values, index 0 = bit 0

    Example:
        >>> bits_to_list(0x0005, 4)
        [True, False, True, False]
    """
    return [get_bit(value, i) for i in range(num_bits)]


def list_to_bits(bits: List[bool]) -> int:
    """
    Convert a list of boolean values to a bit-packed integer.

    Args:
        bits: List of boolean values, index 0 = bit 0

    Returns:
        Bit-packed integer

    Example:
        >>> list_to_bits([True, False, True, False])
        5  # 0b0101
    """
    value = 0
    for i, state in enumerate(bits):
        if state:
            value |= (1 << i)
    return value


def format_bits(value: int, num_bits: int = 16) -> str:
    """
    Format a bit-packed integer as a binary string for debugging.

    Args:
        value: Bit-packed integer
        num_bits: Number of bits to display (default 16)

    Returns:
        Binary string representation

    Example:
        >>> format_bits(0x8007, 16)
        '1000000000000111'
    """
    return format(value, f'0{num_bits}b')


def count_set_bits(value: int) -> int:
    """
    Count the number of set bits in an integer.

    Args:
        value: Integer value

    Returns:
        Number of bits set to 1

    Example:
        >>> count_set_bits(0x8007)
        4
    """
    count = 0
    while value:
        count += value & 1
        value >>= 1
    return count


def get_changed_bits(old_value: int, new_value: int, num_bits: int = 16) -> Dict[int, bool]:
    """
    Get a dictionary of bits that changed between two values.

    Args:
        old_value: Previous bit-packed integer
        new_value: Current bit-packed integer
        num_bits: Number of bits to check (default 16)

    Returns:
        Dictionary mapping bit index to new state (only for changed bits)

    Example:
        >>> get_changed_bits(0x0001, 0x0003, 16)
        {1: True}  # Bit 1 changed from 0 to 1
    """
    changed = {}
    xor_result = old_value ^ new_value

    for i in range(num_bits):
        if get_bit(xor_result, i):
            changed[i] = get_bit(new_value, i)

    return changed
