# RS-485 Wiring Guide

Complete wiring instructions for the shared RS-485 bus connecting all Modbus devices.

## Bus Topology

The Pleat Saw system uses a **multi-drop RS-485 bus** with the following devices:

- **Raspberry Pi** (Modbus Master) - USB RS-485 adapter
- **N4D3E16** I/O Module (Slave ID 1)
- **ESP32-A** Blade + Fixture Controller (Slave ID 2)
- **ESP32-B** Backstop Controller (Slave ID 3)

## Wiring Diagram

```
[Raspberry Pi USB RS-485]
         |
         A ----+---- [120Ω Termination]
         B    |
              |
         A    B
         |    |
    [N4D3E16 Module]
         |    |
         A    B
         |    |
    [ESP32-A RS-485]
         |    |
         A    B
         |    |
    [ESP32-B RS-485]
         |    |
         A----+---- [120Ω Termination]
         B
```

## Cable Specification

- **Type**: Shielded twisted pair (STP), 24 AWG or better
- **Max length**: 1200m (4000 ft) total bus length at 9600 baud
- **Topology**: Daisy chain (linear trunk), avoid star/branch
- **Shield**: Connect shield to earth ground at ONE point only (master end)

### Recommended Cable

- Belden 3105A (24 AWG, 2-pair, foil shield)
- Alpha Wire 6161 (24 AWG, twisted pair, braid shield)
- Any quality industrial RS-485 cable

## Termination Resistors

### Why Termination is Required

RS-485 requires 120Ω termination resistors at **both physical ends** of the bus to prevent signal reflections at high baud rates.

### Termination Locations

1. **Master end** (Raspberry Pi RS-485 adapter)
2. **Far end** (ESP32-B, last device on bus)

### Wiring Termination

Connect a 120Ω ±5% 1/4W resistor between A and B at each end:

```
A ----[120Ω]---- B
```

Some RS-485 modules have built-in jumpers for termination. Check your specific hardware.

## Bias Resistors (Optional but Recommended)

Bias resistors improve idle-state noise immunity by pulling A and B to known states when no device is transmitting.

### Master-side bias (at Raspberry Pi):

- **Pull-up**: 560Ω from A to +5V
- **Pull-down**: 560Ω from B to GND

```
+5V ----[560Ω]---- A
B ----[560Ω]---- GND
```

Not all USB RS-485 adapters expose bias resistor connections. If unavailable, skip this step.

## Device Connections

### Raspberry Pi

- **Hardware**: USB to RS-485 adapter (e.g., FTDI USB-RS485-WE-1800-BT)
- **Connections**: A, B from adapter to bus trunk
- **Configuration**: `/dev/ttyUSB0` at 9600 baud in `config/system.yaml`
- **Termination**: Install 120Ω termination resistor inside adapter or on screw terminals

### N4D3E16 I/O Module

- **Connections**:
  - Terminal A to bus A
  - Terminal B (or D-) to bus B
  - GND to common ground (optional but recommended)
- **DIP Switches**: Set slave ID to **1** (consult N4D3E16 manual for switch positions)
- **Baud Rate**: Set to **9600** via DIP switches (factory default)
- **Termination**: Do NOT terminate (middle of bus)

### ESP32-A (Blade + Fixture)

- **Connections**:
  - RS-485 module A to bus A
  - RS-485 module B to bus B
  - DE and RE pins tied together to GPIO4
- **TTL to RS-485**: Use MAX485 or equivalent module
- **Power**: 3.3V or 5V depending on RS-485 module
- **Slave ID**: 2 (set in firmware)
- **Termination**: Do NOT terminate (middle of bus)

### ESP32-B (Backstop)

- **Connections**:
  - RS-485 module A to bus A
  - RS-485 module B to bus B
  - DE and RE pins tied together to GPIO4
- **TTL to RS-485**: Use MAX485 or equivalent module
- **Power**: 3.3V or 5V depending on RS-485 module
- **Slave ID**: 3 (set in firmware)
- **Termination**: Install 120Ω termination resistor (end of bus)

## Grounding and Shielding

### Ground Connection

- Connect **common ground** between all devices
- Use a separate ground wire or run alongside RS-485 cable
- **DO NOT rely on RS-485 cable for power ground**

### Shield Connection

- Connect cable shield to **chassis ground** at **ONE location only** (master/Pi end)
- Do NOT connect shield at both ends (creates ground loop)
- If noise issues occur, try connecting shield at far end instead

## Pin Assignments

### ESP32 RS-485 Modules

| ESP32 Pin | RS-485 Module | Function |
|-----------|---------------|----------|
| GPIO17    | DI (TXD)      | Transmit Data |
| GPIO16    | RO (RXD)      | Receive Data |
| GPIO4     | DE + RE       | Direction Control (tied together) |
| 3.3V      | VCC           | Power (check module voltage) |
| GND       | GND           | Ground |

### N4D3E16 Terminals

| Terminal | Function |
|----------|----------|
| A (or D+)| RS-485 A |
| B (or D-)| RS-485 B |
| GND      | Ground   |

## Testing the Bus

### Using mbpoll (Modbus command-line tool)

Install mbpoll:
```bash
sudo apt-get install mbpoll
```

Test each device:

```bash
# Test N4D3E16 (slave 1) - read inputs at 0x00C0
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0xC0 -c 1 /dev/ttyUSB0

# Test ESP32-A (slave 2) - read firmware version at 0x0140
mbpoll -m rtu -b 9600 -P none -a 2 -t 3 -r 0x140 -c 1 /dev/ttyUSB0

# Test ESP32-B (slave 3) - read M3 status at 0x0205
mbpoll -m rtu -b 9600 -P none -a 3 -t 3 -r 0x205 -c 1 /dev/ttyUSB0
```

Expected: Each command should return data without timeout errors.

## Troubleshooting

### No response from devices

1. **Check wiring**: Verify A and B are not swapped
2. **Check termination**: Ensure 120Ω resistors at both ends
3. **Check baud rate**: All devices must be 9600 baud
4. **Check slave IDs**: N4D3E16=1, ESP32-A=2, ESP32-B=3
5. **Check power**: Verify all devices powered on

### Intermittent communication

1. **Add termination**: If missing, add 120Ω at both ends
2. **Check cable length**: Keep total bus under 1200m
3. **Check cable quality**: Use shielded twisted pair
4. **Add bias resistors**: Improve idle-state noise immunity
5. **Check ground**: Ensure common ground between devices

### CRC errors

1. **Check cable**: May be damaged or wrong type
2. **Check termination**: Wrong value or missing
3. **Reduce baud rate**: Try 4800 if 9600 has errors
4. **Check EMI**: Route cable away from motors/VFDs

### Wrong data or addresses

1. **Verify slave IDs**: Check DIP switches and firmware
2. **Check endianness**: 16-bit registers may be swapped
3. **Verify register addresses**: Consult device manuals

## Reference

- **RS-485 Standard**: TIA/EIA-485-A
- **Modbus RTU**: Modbus.org specification
- **Baud Rate**: 9600, 8N1 (8 data bits, no parity, 1 stop bit)
- **Max Nodes**: 32 devices per segment (using standard transceivers)
