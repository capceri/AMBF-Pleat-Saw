# N4D3E16 Modbus I/O Module Reference

Quick reference for the N4D3E16 16-input / 16-output Modbus RTU module.

## Module Overview

- **Inputs**: 16 channels (NPN, low=active)
- **Outputs**: 16 channels (relay or solid-state, configurable)
- **Communication**: Modbus RTU over RS-485
- **Power**: 12-24V DC

## Configuration

### DIP Switches

The N4D3E16 uses DIP switches for configuration. Refer to your module's manual for exact switch positions.

**Typical Settings**:
- **Slave ID**: Set to **1** (switches 1-7)
- **Baud Rate**: Set to **9600** (switches 8-9)
- **Parity**: None (switch 10)

### Factory Defaults

Most N4D3E16 modules ship with:
- Slave ID: 1
- Baud rate: 9600
- Parity: None
- Data bits: 8
- Stop bits: 1

## Modbus Register Map

### Input Registers (Read Only)

#### Bit-Packed Inputs (Recommended)

| Address | Function | Description |
|---------|----------|-------------|
| 0x00C0  | Read Holding Register | All 16 inputs bit-packed (IN1=bit0, IN16=bit15) |

**Read Example**:
```
Function: 03 (Read Holding Registers)
Address: 0x00C0
Count: 1
Response: Single 16-bit word with all input states
```

Result interpretation:
- Bit 0 (LSB) = IN1
- Bit 1 = IN2
- ...
- Bit 15 (MSB) = IN16

**Logic**: Bit=1 means input is active (NPN low is converted to logic high internally)

#### Per-Input Registers

| Address Range | Function | Description |
|---------------|----------|-------------|
| 0x0081-0x0090 | Read Holding Register | Individual input status (IN1-IN16) |

Values:
- `0x0000` = No input (inactive)
- `0x0001` = Input present (active)

**Read Example** (IN1):
```
Function: 03 (Read Holding Registers)
Address: 0x0081
Count: 1
Response: 0x0001 (active) or 0x0000 (inactive)
```

### Output Registers (Read/Write)

#### Bit-Packed Outputs (Recommended)

| Address | Function | Description |
|---------|----------|-------------|
| 0x0070  | Read/Write Holding Register | All 16 outputs bit-packed (CH1=bit0, CH16=bit15) |

**Write Example** (set CH1 and CH3 ON):
```
Function: 06 (Write Single Register) or 10 (Write Multiple Registers)
Address: 0x0070
Value: 0x0005 (binary 0000000000000101)
Result: CH1=ON, CH2=OFF, CH3=ON, CH4-16=OFF
```

**Logic**: Bit=1 means output ON/energized

#### Per-Output Control

| Address Range | Function | Description |
|---------------|----------|-------------|
| 0x0001-0x0010 | Read/Write Holding Register | Individual output control (CH1-CH16) |

Values:
- `0x0000` = Output OFF
- `0x0001` = Output ON (immediate)
- `0x0100` = Pulse ON for configured duration
- `0x0200` = Delay ON for configured duration

**Write Example** (turn CH1 ON):
```
Function: 06 (Write Single Register)
Address: 0x0001
Value: 0x0001
Result: CH1 turns ON
```

## Python Examples

### Using pymodbus

```python
from pymodbus.client import ModbusSerialClient

# Connect to N4D3E16
client = ModbusSerialClient(
    port='/dev/ttyUSB0',
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1.0
)

client.connect()

# Read all inputs (bit-packed)
result = client.read_holding_registers(address=0x00C0, count=1, slave=1)
if not result.isError():
    inputs = result.registers[0]
    print(f"Inputs: 0x{inputs:04X} (binary: {inputs:016b})")

    # Check individual input
    in1_active = bool(inputs & 0x01)
    in16_active = bool(inputs & 0x8000)
    print(f"IN1: {in1_active}, IN16: {in16_active}")

# Write all outputs (bit-packed)
# Turn on CH1 (clamp) and CH2 (air jet)
outputs = 0x0003  # Binary: 0000000000000011
client.write_register(address=0x0070, value=outputs, slave=1)

# Read single input (IN16 / Safety)
result = client.read_holding_registers(address=0x0090, count=1, slave=1)
if not result.isError():
    in16_state = result.registers[0]
    print(f"IN16 (Safety): {'ACTIVE' if in16_state else 'INACTIVE'}")

client.close()
```

### Reading Inputs

```python
def read_inputs_bitpacked(client, slave_id=1):
    """Read all 16 inputs as a single bit-packed word."""
    result = client.read_holding_registers(
        address=0x00C0,
        count=1,
        slave=slave_id
    )

    if result.isError():
        return None

    return result.registers[0]

def get_input_bit(inputs_word, bit_index):
    """Extract individual input bit (0-15)."""
    return bool((inputs_word >> bit_index) & 1)

# Usage
inputs = read_inputs_bitpacked(client)
if inputs is not None:
    start_button = get_input_bit(inputs, 0)   # IN1
    sensor2 = get_input_bit(inputs, 1)        # IN2
    sensor3 = get_input_bit(inputs, 2)        # IN3
    safety = get_input_bit(inputs, 15)        # IN16
```

### Writing Outputs

```python
def write_outputs_bitpacked(client, outputs_word, slave_id=1):
    """Write all 16 outputs as a single bit-packed word."""
    result = client.write_register(
        address=0x0070,
        value=outputs_word,
        slave=slave_id
    )

    return not result.isError()

def set_output_bit(current_word, bit_index, state):
    """Set or clear a single output bit."""
    if state:
        return current_word | (1 << bit_index)
    else:
        return current_word & ~(1 << bit_index)

# Usage - maintain shadow register to avoid read-before-write
current_outputs = 0x0000

# Turn on clamp (CH1, bit 0)
current_outputs = set_output_bit(current_outputs, 0, True)

# Turn on air jet (CH2, bit 1)
current_outputs = set_output_bit(current_outputs, 1, True)

# Write to module
write_outputs_bitpacked(client, current_outputs)
```

## Pleat Saw I/O Mapping

### Inputs

| N4D3E16 Input | Bit Index | Function | Active State |
|---------------|-----------|----------|--------------|
| IN1  | 0  | Start Button | NPN low (module reads as 1) |
| IN2  | 1  | Sensor2 (fixture reverse/home) | NPN low |
| IN3  | 2  | Sensor3 (fixture forward) | NPN low |
| IN16 | 15 | Safety (READY when active) | Circuit complete |

**Safety Logic**: IN16 bit=1 means safety circuit is READY (safe to operate).

### Outputs

| N4D3E16 Output | Bit Index | Function | ON State |
|----------------|-----------|----------|----------|
| CH1 | 0 | Pneumatic Clamp | Energized = Clamped |
| CH2 | 1 | Air Jet Solenoid | Energized = Jetting |
| CH3 | 2 | Green Solid Lamp | Energized = Lit |
| CH4 | 3 | Green Flash Lamp | Energized = Lit |

## Command Reference

### Read All Inputs

```bash
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0xC0 -c 1 /dev/ttyUSB0
```

Expected output:
```
-- Polling slave 1...
[49152]: 0x8007
```

Interpretation: `0x8007 = 1000000000000111` (binary)
- IN1=1 (active)
- IN2=1 (active)
- IN3=1 (active)
- IN16=1 (active, READY)

### Write All Outputs OFF

```bash
mbpoll -m rtu -b 9600 -P none -a 1 -t 4 -r 0x70 -c 1 /dev/ttyUSB0 -- 0
```

### Write Clamp ON, Air Jet ON

```bash
mbpoll -m rtu -b 9600 -P none -a 1 -t 4 -r 0x70 -c 1 /dev/ttyUSB0 -- 3
```

(`3 = 0x0003 = binary 11 = CH1 and CH2 ON`)

### Read Single Input (IN16 / Safety)

```bash
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0x90 -c 1 /dev/ttyUSB0
```

## Troubleshooting

### No Response from Module

1. **Check power**: Verify 12-24V DC supply connected and LED lit
2. **Check RS-485 wiring**: Verify A and B not swapped
3. **Check slave ID**: Default is 1, verify DIP switches
4. **Check baud rate**: Default is 9600, verify DIP switches
5. **Check termination**: Module in middle of bus should NOT have termination

### Inputs Always Read 0 or 0xFFFF

1. **Wiring**: NPN sensors need power from module (if provided) or external supply
2. **Sensor type**: Module expects NPN (sinking) sensors, not PNP (sourcing)
3. **Common ground**: Ensure sensors and module share common ground

### Outputs Don't Activate

1. **Check output type**: Relay outputs may need external power for coil
2. **Check load**: Verify load is within module's rating
3. **Check register write**: Use bit-packed (0x0070) for immediate response
4. **Verify write command**: Function 06 (single) or 10 (multiple) both work

### Intermittent Communication

1. **Add termination**: If at bus end, add 120Ω terminator
2. **Check cable**: Use shielded twisted pair
3. **Check ground**: Connect common ground between devices
4. **Reduce poll rate**: If polling too fast, add delay between reads

## Specifications

- **Supply Voltage**: 12-24V DC
- **Input Type**: NPN sinking (low = active)
- **Output Type**: Relay or solid-state (configurable by model)
- **Output Rating**: Typically 2A @ 250V AC (relay) or 500mA @ 30V DC (SSR)
- **RS-485**: Half-duplex, 2-wire (A, B)
- **Baud Rates**: 4800, 9600, 19200, 38400 (DIP switch selectable)
- **Protocol**: Modbus RTU
- **Operating Temperature**: -10°C to +60°C

## References

- Modbus Protocol: https://modbus.org/specs.php
- pymodbus Documentation: https://pymodbus.readthedocs.io/
- N4D3E16 Manual: Consult manufacturer documentation
