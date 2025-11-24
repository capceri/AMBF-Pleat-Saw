"""
Utility modules for Pleat Saw controller.
"""

from .config import Config, get_config
from .units import (
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
from .bits import (
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

__all__ = [
    # Config
    'Config',
    'get_config',
    # Units
    'mm_to_inches',
    'inches_to_mm',
    'mm_to_modbus',
    'modbus_to_mm',
    'mm_s_to_modbus',
    'modbus_to_mm_s',
    'split_int32',
    'combine_int32',
    'format_inches',
    'format_mm',
    'clamp',
    'rpm_to_hz',
    'hz_to_rpm',
    # Bits
    'get_bit',
    'set_bit',
    'toggle_bit',
    'bits_to_dict',
    'dict_to_bits',
    'bits_to_list',
    'list_to_bits',
    'format_bits',
    'count_set_bits',
    'get_changed_bits',
]
