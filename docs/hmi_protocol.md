# Nextion HMI Communication Protocol

Key=value ASCII protocol for bidirectional communication between Raspberry Pi and Nextion HMI.

## Protocol Overview

- **Transport**: Serial UART (115200 baud, 8N1)
- **Format**: ASCII text, one command per line
- **Terminator**: Newline `\n` (0x0A)
- **Encoding**: UTF-8 (ASCII subset)
- **Direction**: Bidirectional (Pi ↔ Nextion)

## Message Format

```
key=value\n
```

- **key**: Variable or command name (no spaces)
- **value**: String, number, or keyword
- **No spaces** around `=` sign

## Pi → Nextion (Status Updates)

The Pi pushes status updates to the Nextion at 10 Hz.

### State Variables

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `state` | String | Current state machine state | `state=IDLE` |
| `safety` | String | Safety status | `safety=READY` |
| `alarm` | String | Current alarm code (empty if none) | `alarm=TIMEOUT_FWD` |

### Motor 1 (Blade)

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `m1.rpm` | Integer | Current/target RPM | `m1.rpm=3500` |
| `m1.status` | String | Running status | `m1.status=RUNNING` |

### Motor 2 (Fixture)

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `m2.vel` | Float | Current/target velocity (mm/s) | `m2.vel=120.0` |
| `m2.accel` | Float | Acceleration (mm/s²) | `m2.accel=2000.0` |
| `m2.status` | String | Motion status | `m2.status=IN_MOTION` |

### Motor 3 (Backstop)

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `m3.pos_mm` | Float | Position in mm (engineering) | `m3.pos_mm=152.500` |
| `m3.pos_in` | Float | Position in inches (customer) | `m3.pos_in=6.004` |
| `m3.vel` | Float | Velocity (mm/s) | `m3.vel=50.0` |
| `m3.status` | String | Status | `m3.status=AT_TARGET` |

### Cycle Info

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `cycle.count` | Integer | Completed cycles | `cycle.count=142` |
| `cycle.time` | Float | Last cycle time (seconds) | `cycle.time=8.2` |

## Nextion → Pi (Commands & Setpoints)

Commands and setpoint changes sent from Nextion to Pi.

### Commands

Format: `cmd=COMMAND_NAME`

| Command | Description |
|---------|-------------|
| `cmd=START` | Start cycle (same as IN1 start button) |
| `cmd=STOP` | Stop current cycle |
| `cmd=RESET_ALARMS` | Clear latched alarms |
| `cmd=HOME_M3` | Home backstop motor |
| `cmd=JOG_M2_FWD` | Jog fixture forward (manual mode) |
| `cmd=JOG_M2_REV` | Jog fixture reverse (manual mode) |
| `cmd=JOG_M3_FWD` | Jog backstop forward |
| `cmd=JOG_M3_REV` | Jog backstop reverse |
| `cmd=STOP_JOG` | Stop all jog motion |

### Setpoints

Format: `key=value`

#### M1 Blade Setpoints

| Key | Type | Range | Description |
|-----|------|-------|-------------|
| `m1.rpm` | Integer | 500-6000 | Target RPM |
| `m1.ramp` | Integer | 0-1000 | Ramp time (ms) |

#### M2 Fixture Setpoints

| Key | Type | Range | Description |
|-----|------|-------|-------------|
| `m2.vel` | Float | 10-400 | Velocity (mm/s) |
| `m2.accel` | Float | 100-5000 | Acceleration (mm/s²) |
| `m2.jerk` | Float | Optional | Jerk limit (mm/s³) |

#### M3 Backstop Setpoints

| Key | Type | Range | Description |
|-----|------|-------|-------------|
| `m3.goto_mm` | Float | 0.0-1000.0 | Move to position (mm) |
| `m3.goto_in` | Float | 0.0-39.37 | Move to position (inches) |
| `m3.vel` | Float | 10-200 | Velocity (mm/s) |
| `m3.accel` | Float | 100-2000 | Acceleration (mm/s²) |

#### Cycle Timing

| Key | Type | Range | Description |
|-----|------|-------|-------------|
| `cycle.dwell` | Float | 0.0-10.0 | Dwell time (seconds) |
| `cycle.air_jet` | Float | 0.0-5.0 | Air jet duration (seconds) |

#### PID Tuning (Engineering Screen)

| Key | Type | Range | Description |
|-----|------|-------|-------------|
| `m3.pid.p` | Float | 0.0-100.0 | Proportional gain |
| `m3.pid.i` | Float | 0.0-10.0 | Integral gain |
| `m3.pid.d` | Float | 0.0-10.0 | Derivative gain |

## Nextion Response Format

After receiving a message, Nextion should respond:

- **Success**: `ok\n`
- **Error**: `err=DESCRIPTION\n`

Example:
```
Pi → Nextion: m1.rpm=3500\n
Nextion → Pi: ok\n
```

## Debouncing

Setpoint changes from HMI are debounced with a 100ms timeout (configurable) to prevent excessive updates during slider/number pad adjustments.

## Units

### Internal (Pi/Modbus)

- Linear: **millimeters (mm)**
- Velocity: **mm/s**
- Acceleration: **mm/s²**

### Customer Display (Nextion)

- Linear: **inches (in)**
- Format: `0.000` (3 decimal places)

### Engineering Display (Nextion)

- Linear: **millimeters (mm)**
- Format: `0.000` (3 decimal places)

## Example Communication Session

```
# Pi sends initial state
Pi→HMI: state=IDLE\n
Pi→HMI: safety=READY\n
Pi→HMI: m1.rpm=0\n
Pi→HMI: m3.pos_in=6.000\n

# User changes M3 target on HMI
HMI→Pi: m3.goto_in=8.500\n
Pi→HMI: ok\n

# User presses START on HMI
HMI→Pi: cmd=START\n
Pi→HMI: ok\n

# Pi sends status updates during cycle (10 Hz)
Pi→HMI: state=START_SPINDLE\n
Pi→HMI: m1.rpm=3500\n
Pi→HMI: m1.status=RUNNING\n

Pi→HMI: state=FEED_FWD\n
Pi→HMI: m2.status=IN_MOTION\n

# Cycle completes
Pi→HMI: state=COMPLETE\n
Pi→HMI: cycle.count=143\n
Pi→HMI: state=IDLE\n
```

## Nextion Page Variables

### Required Text Objects

#### Status Page
- `txt_state` - Current state
- `txt_safety` - Safety status
- `txt_alarm` - Alarm code
- `txt_m1_rpm` - Blade RPM
- `txt_m3_pos` - Backstop position (inches)
- `txt_cycle_count` - Cycle counter

#### Engineering Page
- `num_m1_rpm` - RPM setpoint (number input)
- `num_m2_vel` - Fixture velocity (number input)
- `num_m3_target` - Backstop target (number input, mm)
- `sld_m2_vel` - Fixture velocity slider
- `txt_m3_pos_mm` - Position in mm

### Button Touch Events

In Nextion Editor, configure button touch events to send commands:

```
// START button Touch Release Event
prints "cmd=START",10

// STOP button
prints "cmd=STOP",10

// RESET ALARMS button
prints "cmd=RESET_ALARMS",10

// M3 GOTO button (after number entry)
prints "m3.goto_in=",0
prints num_m3_target.val,0
prints 10
```

### Slider Value Changes

```
// Fixture velocity slider
prints "m2.vel=",0
prints sld_m2_vel.val,0
prints 10
```

## Implementation Notes

### On Raspberry Pi

The `NextionBridge` service handles all communication:

```python
from services import NextionBridge

hmi = NextionBridge(port='/dev/ttyAMA0', baud=115200)
hmi.connect()
hmi.start()

# Update state
hmi.update_state('state', 'IDLE')
hmi.update_state('m1.rpm', 3500)

# Update position (converts mm → inches automatically)
hmi.update_position_mm(152.5)

# Register command callback
def handle_start(cmd):
    print(f"START command received")

hmi.register_callback('cmd', handle_start)
```

### On Nextion

1. Create variables/objects with names matching protocol keys
2. Configure touch events to send commands via `prints`
3. Update display values when receiving updates from Pi
4. Use timers for periodic refreshes if needed

## Troubleshooting

### No data from Pi

- Check serial port: `/dev/ttyAMA0` configured in `config/system.yaml`
- Check baud rate: 115200
- Verify cable TX→RX, RX→TX crossover
- Check Pi UART enabled: `dtoverlay=uart0` in `/boot/config.txt`

### Garbled text

- Baud rate mismatch
- Wrong wiring (TX/RX not crossed)
- Cable too long or poor quality

### Commands not received by Pi

- Check Nextion sends `\n` terminator (ASCII 10)
- Verify `prints` commands in button events
- Check Pi logs for parse errors

### Setpoints not updating

- Debounce delay (100ms) - wait before expecting response
- Check value ranges (out-of-range values may be clamped)
- Verify key names match exactly (case-sensitive)
