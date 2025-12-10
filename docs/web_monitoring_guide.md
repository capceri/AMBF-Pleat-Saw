# Web Monitoring Dashboard - User Guide

## Overview

The Pleat Saw Controller includes a built-in web-based monitoring dashboard designed for commissioning, troubleshooting, and fault-finding. The dashboard provides real-time visibility into all system components and allows manual control for testing purposes.

**Accessing the Dashboard:**
- Default URL: `http://<raspberry-pi-ip>:5000`
- Example: `http://192.168.1.100:5000`
- From the Pi itself: `http://localhost:5000`

---

## Features

### Real-Time Monitoring
- **System Status**: Current state, safety status, alarms, cycle count, uptime
- **Digital I/O**: Live display of all inputs (sensors, buttons) and outputs (solenoids, lamps)
- **Motor Status**: Position, motion state, faults for all three axes
- **Statistics**: Modbus communication counters, I/O polling statistics, alarm history
- **Command Log**: Real-time console showing all commands and responses

### Manual Control
- **Cycle Control**: Start/stop cycles, reset alarms
- **Output Testing**: Toggle individual outputs (clamp, air jet, lamps)
- **Motor Testing**:
  - M1 Blade: Start/stop at specified RPM
  - M2 Fixture: Jog forward/reverse at specified velocity
  - M3 Backstop: Move to position, home axis
- **Parameter Adjustment**: Change speeds and positions on the fly

### Live Updates
- **WebSocket Connection**: Real-time updates (10 Hz default)
- **Automatic Reconnection**: Dashboard reconnects if connection drops
- **Color-Coded Indicators**: Green = ON/READY, Gray = OFF, Red = FAULT

---

## Dashboard Layout

### 1. Header
- **Title**: Pleat Saw Controller - Monitoring Dashboard
- **Connection Status**: Shows connected/disconnected with indicator dot
  - Green dot = Connected to controller
  - Red dot = Disconnected

### 2. System Status Panel
Displays overall system state:
- **State**: Current process state (IDLE, FEED_FWD, ALARM, etc.)
- **Safety**: Safety input status (READY / NOT_READY)
- **Alarm**: Current alarm code (if any)
- **Cycle Count**: Total completed cycles
- **Uptime**: Time since controller started

### 3. Digital Inputs Panel
Shows real-time state of all inputs:
- **Start Button (IN1)**: Operator start button
- **Sensor2 / Home (IN2)**: Fixture reverse limit
- **Sensor3 / Forward (IN3)**: Fixture forward limit
- **Safety (IN16)**: Safety circuit status (ACTIVE = READY)

**Indicator Colors:**
- Green "ON" = Input active
- Gray "OFF" = Input inactive

### 4. Digital Outputs Panel
Shows and controls all outputs:
- **Clamp (CH1)**: Pneumatic clamp
- **Air Jet (CH2)**: Air blast solenoid
- **Green Solid (CH3)**: Ready lamp
- **Green Flash (CH4)**: Running lamp

**Controls:**
- Click "Toggle" button to manually switch output ON/OFF
- Use for testing wiring and solenoid operation

### 5. Motor Status Panels

#### M1 - Blade Motor
- **Status Indicators**:
  - Running: Motor is spinning
  - Fault: Motor controller fault
  - Ready: Motor controller ready
- **Controls**:
  - RPM input: Set target speed (500-6000 RPM)
  - Start: Start motor at specified RPM
  - Stop: Stop motor

#### M2 - Fixture Motor
- **Status Indicators**:
  - In Motion: Motor is moving
  - At S2: Sensor2 detected (home position)
  - At S3: Sensor3 detected (forward position)
  - Fault: Motor controller fault
- **Controls**:
  - Vel input: Set jog velocity (10-400 mm/s)
  - Jog FWD: Move forward continuously
  - Jog REV: Move reverse continuously
  - Stop: Stop motor

#### M3 - Backstop Motor
- **Status Indicators**:
  - Position: Current position in mm
  - In Motion: Motor is moving
  - At Target: Reached target position
  - Homed: Position reference established
  - Fault: Motor controller fault
- **Controls**:
  - Target input: Set target position (0-1000 mm)
  - Go To: Move to target position
  - Home: Set current position as zero
  - Stop: Stop motor

### 6. Cycle Control Panel
Main process control buttons:
- **Start Cycle**: Begin automatic cycle (same as pressing start button)
- **Emergency Stop**: Immediate stop of all motion (Category 0)
- **Reset Alarms**: Clear alarm condition after fault is resolved

### 7. System Statistics Panel
Communication and performance counters:
- **Modbus Reads**: Total Modbus read transactions
- **Modbus Writes**: Total Modbus write transactions
- **Modbus Errors**: Communication errors
- **I/O Polls**: Total input polling cycles
- **I/O Changes**: Number of input state changes
- **Total Alarms**: Cumulative alarm count

### 8. Command Log (Console)
Scrolling log of all commands and responses:
- **Timestamps**: Each entry shows exact time
- **Color Coding**:
  - Green: Successful commands
  - Red: Errors
  - Yellow: Warnings
  - Blue: Informational messages

---

## Commissioning Procedures

### Phase 1: Basic Connectivity Test

1. **Access Dashboard**
   - Open web browser on laptop/tablet
   - Navigate to `http://<pi-ip>:5000`
   - Verify connection indicator turns green

2. **Check System Status**
   - Verify State shows "IDLE" or current state
   - Check Safety status (should be "READY" if IN16 active)
   - Observe that all indicators update in real-time

### Phase 2: I/O Verification

#### Test Inputs
1. **Sensor Testing**
   - Physically activate Sensor2 (IN2)
   - Verify indicator changes to "ON" on dashboard
   - Release sensor, verify "OFF"
   - Repeat for Sensor3 (IN3)

2. **Start Button Test**
   - Press start button
   - Verify Start (IN1) shows "ON"
   - Release, verify "OFF"

3. **Safety Circuit Test** ⚠️ **CRITICAL**
   - Verify Safety (IN16) shows "READY" when safety OK
   - Open safety circuit (e-stop button, guard, etc.)
   - Verify Safety shows "NOT_READY"
   - System should transition to ALARM or ESTOP state
   - Reset safety, then click "Reset Alarms"
   - System should return to IDLE

#### Test Outputs
1. **Individual Output Test**
   - Click "Toggle" for Clamp (CH1)
   - Listen for solenoid actuation
   - Verify indicator changes to "ON"
   - Click "Toggle" again to turn OFF

2. **Repeat for All Outputs**
   - Test Air Jet (CH2)
   - Test Green Solid (CH3)
   - Test Green Flash (CH4)

### Phase 3: Motor Testing

#### M1 Blade Motor (No Load First!)
1. **Low Speed Test**
   - Ensure blade is disconnected or guard is open
   - Set RPM to 500 (minimum)
   - Click "Start"
   - Verify "Running" indicator turns ON
   - Listen for motor spin
   - Click "Stop"
   - Verify "Running" turns OFF

2. **Speed Ramp Test**
   - Test at 1000, 2000, 3000 RPM
   - Observe smooth acceleration
   - Check for vibration or noise

#### M2 Fixture Motor
1. **Jog Test**
   - Set Vel to 50 mm/s (slow speed)
   - Click "Jog FWD"
   - Verify "In Motion" turns ON
   - Observe fixture movement
   - Click "Stop"

2. **Sensor Detection Test**
   - Jog forward until Sensor3 triggers
   - Verify "At S3" indicator turns ON
   - Jog reverse until Sensor2 triggers
   - Verify "At S2" indicator turns ON

#### M3 Backstop Motor
1. **Homing**
   - Click "Home" button
   - Verify "Homed" indicator turns ON
   - Position should show 0.000 mm

2. **Position Test**
   - Set Target to 10.0 mm
   - Click "Go To"
   - Verify "In Motion" turns ON during move
   - When complete, "At Target" should turn ON
   - Position should read ~10.000 mm

3. **Position Accuracy**
   - Test multiple positions: 25, 50, 100 mm
   - Verify position reading matches target within ±0.010 mm

### Phase 4: Automatic Cycle Test

1. **Dry Run (No Blade)**
   - Ensure M1 blade is disabled or disconnected
   - Click "Start Cycle"
   - Observe state changes:
     - IDLE → PRECHECK → START_SPINDLE → FEED_FWD → ...
   - Watch console log for each state transition

2. **Monitor Timing**
   - FWD motion should complete within timeout (5s default)
   - Dwell period (1.5s default)
   - REV motion should complete within timeout (5s default)
   - Air jet pulse (1.0s default)

3. **Safety Interrupt Test** ⚠️ **CRITICAL**
   - Start cycle
   - During FEED_FWD state, open safety circuit
   - Verify immediate transition to ESTOP
   - All motors should stop
   - Outputs should go to safe state
   - Restore safety
   - Click "Reset Alarms" to recover

---

## Troubleshooting with Dashboard

### Connection Issues

**Problem:** Red "Disconnected" indicator
- **Check**: Is Pleat Saw service running?
  - SSH to Pi: `sudo systemctl status pleat-saw`
- **Check**: Is web monitor enabled?
  - Verify in `/home/pi/pleat_saw/config/system.yaml`
  - Look for `web_monitor: enabled: true`
- **Check**: Firewall blocking port 5000?
  - Test from Pi: `curl http://localhost:5000`
- **Fix**: Restart service: `sudo systemctl restart pleat-saw`

### Modbus Communication Errors

**Problem:** High error count in statistics
- **Symptom**: Modbus Errors counter increasing rapidly
- **Check**: RS-485 wiring connections
- **Check**: Termination resistors installed (120Ω at each end)
- **Check**: Baud rate matches (9600 for all devices)
- **Action**: View detailed logs: `sudo journalctl -u pleat-saw -f`

### Input Not Responding

**Problem:** Input indicator doesn't change when sensor activated
- **Check**: Sensor wiring (NPN, low=active)
- **Check**: Sensor power supply (typically 24V DC)
- **Check**: N4D3E16 LED for that input channel
- **Action**: Toggle output to verify N4D3E16 communication working

### Output Not Actuating

**Problem:** Indicator shows ON but solenoid doesn't actuate
- **Check**: Output wiring to solenoid
- **Check**: Power supply to output card (typically 24V DC)
- **Check**: N4D3E16 LED for that output channel
- **Action**: Measure voltage at output terminal with multimeter

### Motor Not Moving

**Problem:** Start/jog command sent but no motion
- **Check**: Motor "Fault" indicator (RED = fault present)
- **Check**: Motor "Ready" indicator (must be ON)
- **Check**: Enable signals from safety circuit
- **Check**: RS-485 communication to ESP32 (Modbus Reads/Writes increasing)
- **Action**: View ESP32 serial debug output if available

### Position Inaccuracy (M3)

**Problem:** M3 position reading doesn't match physical position
- **Symptom**: "At Target" turns ON but part is wrong location
- **Check**: Encoder wiring (A, B channels)
- **Check**: Encoder power supply
- **Check**: Steps per mm calibration in config
- **Action**: Re-home axis (click "Home" at known position)
- **Action**: Verify PID tuning (may oscillate if gains too high)

### Cycle Timeout Alarms

**Problem:** TIMEOUT_FWD or TIMEOUT_REV alarms during cycle
- **Symptom**: State machine stops in ALARM, console shows timeout
- **Cause 1**: Sensor not triggering (misaligned, failed)
  - Test sensor manually, watch input indicator
- **Cause 2**: Motion too slow, doesn't reach sensor in time
  - Increase timeout in `config/motion.yaml`
  - Or increase motor velocity
- **Cause 3**: Sensor stuck ON (wiring short, sensor failed)
  - Check input is OFF before starting cycle

---

## Configuration

### Web Monitor Settings

Edit `/home/pi/pleat_saw/config/system.yaml`:

```yaml
services:
  web_monitor:
    enabled: true          # Enable/disable web dashboard
    port: 5000             # Web server port (default 5000)
    host: 0.0.0.0          # Bind to all interfaces
    update_rate_hz: 10     # Real-time update frequency
    require_auth: false    # Future: enable authentication
    debug: false           # Flask debug mode (development only)
```

**Parameters:**
- **port**: Change if port 5000 conflicts with another service
- **host**:
  - `0.0.0.0` = Accessible from network (default)
  - `127.0.0.1` = Local only (Pi only)
- **update_rate_hz**: Higher = more responsive, more CPU/network load
  - Recommended: 5-20 Hz
  - Default: 10 Hz (100ms updates)

### Restart After Config Changes

```bash
sudo systemctl restart pleat-saw
```

---

## Safety Warnings

⚠️ **IMPORTANT SAFETY INFORMATION**

1. **Manual Control is for Testing Only**
   - Dashboard commands bypass normal interlocks
   - Operator responsible for safe operation
   - Keep clear of moving parts

2. **Emergency Stop Always Available**
   - Dashboard "Emergency Stop" button
   - Physical e-stop buttons on machine
   - Safety circuit must remain functional

3. **Commissioning Sequence**
   - Follow commissioning checklist in order
   - Do not skip safety tests
   - Test emergency stop BEFORE full-speed operation

4. **Production Use**
   - Dashboard is supplementary to Nextion HMI
   - Not intended as primary operator interface
   - Use for diagnostics and troubleshooting

5. **Network Security**
   - Dashboard has no authentication (v1.0)
   - Accessible to anyone on network
   - Restrict network access in production
   - Future versions will add password protection

---

## API Reference (Advanced)

For programmatic access or custom integrations:

### HTTP Endpoints

#### GET /api/status
Returns overall system status.

**Response:**
```json
{
  "state": "IDLE",
  "safety": "READY",
  "alarm": null,
  "cycle_count": 42,
  "uptime": 3600.5,
  "timestamp": 1698765432.123
}
```

#### GET /api/inputs
Returns current input states.

**Response:**
```json
{
  "inputs": {
    "start": false,
    "sensor2": true,
    "sensor3": false,
    "safety": true
  },
  "timestamp": 1698765432.123
}
```

#### GET /api/outputs
Returns current output states.

**Response:**
```json
{
  "outputs": {
    "clamp": false,
    "air_jet": false,
    "green_solid": true,
    "green_flash": false
  },
  "timestamp": 1698765432.123
}
```

#### GET /api/motors
Returns motor status and positions.

**Response:**
```json
{
  "m1_blade": {
    "running": false,
    "fault": false,
    "ready": true
  },
  "m2_fixture": {
    "in_motion": false,
    "at_s2": true,
    "at_s3": false,
    "fault": false,
    "homed": true
  },
  "m3_backstop": {
    "in_motion": false,
    "homed": true,
    "at_target": true,
    "fault": false,
    "position_mm": 152.453
  },
  "timestamp": 1698765432.123
}
```

#### GET /api/statistics
Returns system statistics.

**Response:**
```json
{
  "modbus": {
    "read_count": 10543,
    "write_count": 3421,
    "error_count": 2
  },
  "io": {
    "poll_count": 50234,
    "change_count": 87
  },
  "supervisor": {
    "cycles_complete": 42,
    "alarms_total": 1,
    "estops_total": 0
  },
  "timestamp": 1698765432.123
}
```

#### POST /api/command
Execute manual control command.

**Request Body:**
```json
{
  "command": "m1_start",
  "params": {
    "rpm": 3500
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "M1 started at 3500 RPM"
}
```

**Commands:**
- `start_cycle` - Start automatic cycle
- `stop_cycle` - Emergency stop
- `reset_alarms` - Clear alarms
- `set_output` - Toggle output (params: name, state)
- `m1_start` - Start blade (params: rpm)
- `m1_stop` - Stop blade
- `m2_jog_forward` - Jog forward (params: vel)
- `m2_jog_reverse` - Jog reverse (params: vel)
- `m2_stop` - Stop fixture
- `m3_goto` - Move to position (params: position)
- `m3_home` - Home backstop
- `m3_stop` - Stop backstop

### WebSocket Events

#### Client → Server

**Event:** `connect`
- Establishes WebSocket connection
- Server responds with status message

**Event:** `request_update`
- Client requests immediate status update
- Server responds with `update` event

**Event:** `command`
- Execute command via WebSocket
- Same format as POST /api/command
- Server responds with `command_result` event

#### Server → Client

**Event:** `status`
- Connection status messages
- Payload: `{message: string}`

**Event:** `update`
- Real-time status broadcast (10 Hz default)
- Payload: Combined system, inputs, outputs, motors data

**Event:** `command_result`
- Result of command execution
- Payload: `{success: bool, message: string, error: string}`

---

## Performance Notes

### Resource Usage
- **CPU**: ~5-10% on Raspberry Pi 3/4 (with 10 Hz updates)
- **Memory**: ~50 MB for Flask + SocketIO
- **Network**: ~10 KB/s per connected client (10 Hz)

### Scalability
- Supports multiple concurrent clients
- Each client receives same real-time updates
- Tested with up to 5 simultaneous connections

### Responsiveness
- Command latency: <100 ms (local network)
- Update latency: 100 ms (10 Hz default)
- WebSocket reconnect: Automatic, ~2s delay

---

## Version History

### v1.0 (2025-10-22)
- Initial release
- Real-time monitoring of all system components
- Manual control for commissioning
- WebSocket live updates
- RESTful API endpoints
- No authentication (network security required)

### Planned Enhancements (Future)
- User authentication (username/password)
- Historical data logging and graphing
- Downloadable reports (CSV/PDF)
- Mobile-responsive design
- Alarm history viewer
- Configuration editor in web UI

---

## Support

For technical support or questions:
1. Check troubleshooting section above
2. Review system logs: `sudo journalctl -u pleat-saw -f`
3. Check main documentation in `/home/pi/pleat_saw/docs/`
4. Contact controls engineering team

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
**For:** Pleat Saw Controller v3.0
