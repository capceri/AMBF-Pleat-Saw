# Nextion HMI Programming Prompt for Pleat Saw Controller

**Purpose**: This prompt will guide you (or an AI assistant) in creating a complete Nextion HMI project for the Pleat Saw industrial controller.

**Target**: Nextion Enhanced display (3.5" or 5" recommended)

**Communication**: Serial UART at 115200 baud using key=value ASCII protocol

---

## Background Context

You are creating a Nextion touchscreen HMI for an industrial pleat saw machine controller. The HMI communicates with a Raspberry Pi controller via serial using a simple key=value ASCII protocol. The system controls three motors (blade, fixture, backstop) and monitors safety interlocks through a deterministic state machine.

**Key Requirements**:
- Two main pages: **Customer Screen** (operator) and **Engineering Screen** (setup/diagnostics)
- Real-time status display (state, safety, alarms)
- Motor parameter adjustment (RPM, speeds, positions)
- Start/Stop/Reset controls
- Position display in **inches** for customer, **millimeters** for engineering
- Alarm display and acknowledgment
- Visual indicators (green lamps, status colors)

---

## Protocol Specification

### Message Format

**From Pi → Nextion**: Status updates pushed at 10 Hz
```
key=value\n
```

**From Nextion → Pi**: Commands and setpoints
```
cmd=COMMAND\n
key=value\n
```

### Pi → Nextion Variables (Receive)

The Nextion will receive these status updates from the Pi:

#### System Status
- `state` (String): Current state (IDLE, FEED_FWD, DWELL, COMPLETE, ALARM, ESTOP, etc.)
- `safety` (String): Safety status (READY, NOT_READY)
- `alarm` (String): Current alarm code (empty if none, e.g., "TIMEOUT_FWD")
- `cycle.count` (Integer): Completed cycle counter
- `cycle.time` (Float): Last cycle time in seconds

#### Motor 1 (Blade)
- `m1.rpm` (Integer): Current/target RPM (0-6000)
- `m1.status` (String): Status (IDLE, RUNNING, FAULT)

#### Motor 2 (Fixture)
- `m2.vel` (Float): Current/target velocity mm/s
- `m2.accel` (Float): Acceleration mm/s²
- `m2.status` (String): Status (IDLE, IN_MOTION, AT_S2, AT_S3, FAULT)

#### Motor 3 (Backstop)
- `m3.pos_mm` (String): Position in mm (formatted, e.g., "152.500")
- `m3.pos_in` (String): Position in inches (formatted, e.g., "6.004")
- `m3.vel` (Float): Velocity mm/s
- `m3.status` (String): Status (IDLE, IN_MOTION, AT_TARGET, FAULT)

### Nextion → Pi Commands (Send)

The Nextion sends these commands/setpoints to Pi:

#### Control Commands
- `cmd=START` - Start cycle
- `cmd=STOP` - Stop current cycle
- `cmd=RESET_ALARMS` - Clear latched alarms
- `cmd=HOME_M3` - Home backstop motor
- `cmd=JOG_M2_FWD` - Jog fixture forward (manual mode)
- `cmd=JOG_M2_REV` - Jog fixture reverse (manual mode)
- `cmd=JOG_M3_FWD` - Jog backstop forward
- `cmd=JOG_M3_REV` - Jog backstop reverse
- `cmd=STOP_JOG` - Stop all jog motion

#### Setpoints (Engineering Screen)
- `m1.rpm=<value>` - Set blade RPM (500-6000)
- `m2.vel=<value>` - Set fixture velocity mm/s (10-400)
- `m2.accel=<value>` - Set fixture acceleration mm/s² (100-5000)
- `m3.goto_mm=<value>` - Move backstop to position (mm)
- `m3.goto_in=<value>` - Move backstop to position (inches)
- `m3.vel=<value>` - Set backstop velocity mm/s
- `cycle.dwell=<value>` - Set dwell time (seconds)
- `cycle.air_jet=<value>` - Set air jet duration (seconds)
- `m3.pid.p=<value>` - Set PID P gain
- `m3.pid.i=<value>` - Set PID I gain
- `m3.pid.d=<value>` - Set PID D gain

---

## Page Layouts

### Page 0: Customer Screen (Operator View)

**Purpose**: Simple, read-only operator interface focused on status and cycle control

**Layout**:

1. **Header Bar** (full width, top)
   - Large text: Machine state (e.g., "IDLE", "RUNNING", "COMPLETE")
   - Background color changes with state:
     - IDLE: Green
     - RUNNING: Blue
     - ALARM/ESTOP: Red
     - COMPLETE: Green

2. **Safety Status** (top right corner)
   - Text: "SAFETY: READY" or "SAFETY: NOT READY"
   - Green when READY, red when NOT READY
   - Large, highly visible

3. **Main Status Area** (center)
   - **Cycle Counter**: "Cycles: 142"
   - **Last Cycle Time**: "Last: 8.2 sec"
   - **Backstop Position**: "Position: 6.004 in" (inches, 3 decimals)
   - **Blade Status**: "Blade: 3500 RPM" or "Blade: STOPPED"

4. **Alarm Display** (center, conditional visibility)
   - Large red text box
   - Displays alarm code when present
   - Example: "⚠️ ALARM: TIMEOUT_FWD"
   - Hidden when no alarm

5. **Control Buttons** (bottom)
   - **START** button (green, large)
     - Enabled only when IDLE
     - Sends `cmd=START`
   - **STOP** button (red, medium)
     - Enabled during cycle
     - Sends `cmd=STOP`
   - **RESET ALARMS** button (yellow, appears only when alarm present)
     - Sends `cmd=RESET_ALARMS`
   - **Engineering** button (small, bottom-right corner)
     - Navigates to Engineering Screen (Page 1)

**Variables to Create**:
- `txt_state` - Text object for state display
- `txt_safety` - Text object for safety status
- `txt_alarm` - Text object for alarm (vis=0 when no alarm)
- `num_cycle_count` - Number display for cycles
- `num_cycle_time` - Number display (1 decimal)
- `txt_m3_pos_in` - Text object for position in inches
- `txt_m1_status` - Text object for blade status
- `btn_start` - Button for START
- `btn_stop` - Button for STOP
- `btn_reset` - Button for RESET ALARMS
- `btn_engineering` - Button to switch pages

**Touch Event Code Examples**:

START button (btn_start) Touch Release Event:
```
prints "cmd=START",10
```

STOP button (btn_stop) Touch Release Event:
```
prints "cmd=STOP",10
```

RESET ALARMS button (btn_reset) Touch Release Event:
```
prints "cmd=RESET_ALARMS",10
```

Engineering button (btn_engineering) Touch Release Event:
```
page 1
```

---

### Page 1: Engineering Screen (Setup/Diagnostics)

**Purpose**: Detailed control and diagnostics for setup, tuning, and troubleshooting

**Layout**:

1. **Header Bar**
   - Text: "ENGINEERING MODE"
   - **Customer** button (small, top-right) → returns to Page 0

2. **Tabbed Interface** or **Scrollable Single Page**

   Option A: Single scrollable page with sections
   Option B: Multiple sub-pages with tabs

   **Recommended**: Single page with collapsible sections

3. **Section 1: System Status**
   - State: "FEED_FWD"
   - Safety: "READY"
   - Alarm: "None" or code
   - Cycle count: 142
   - Last cycle time: 8.2s

4. **Section 2: M1 Blade Motor**
   - RPM setpoint: Number input (500-6000)
     - Text: "Blade RPM:"
     - Number box: `num_m1_rpm` (editable)
     - Set button sends `m1.rpm=<value>`
   - Current RPM: Display only
   - Status: Display (IDLE/RUNNING/FAULT)

5. **Section 3: M2 Fixture Motor**
   - Velocity setpoint (mm/s): Number input (10-400)
   - Acceleration setpoint (mm/s²): Number input (100-5000)
   - Status: Display
   - **Jog controls**:
     - JOG FWD button (hold to jog)
     - JOG REV button (hold to jog)
     - Stop button

6. **Section 4: M3 Backstop Motor**
   - **Position Display**:
     - Current position (mm): "152.500 mm"
     - Current position (in): "6.004 in"
   - **Position Command**:
     - Number input (mm): `num_m3_target_mm`
     - GOTO button sends `m3.goto_mm=<value>`
   - **OR**:
     - Number input (in): `num_m3_target_in`
     - GOTO button sends `m3.goto_in=<value>`
   - Velocity setpoint (mm/s): Number input
   - Status: Display
   - **Jog controls**: FWD/REV buttons
   - **HOME button**: Sends `cmd=HOME_M3`

7. **Section 5: Cycle Timing**
   - Dwell time (s): Number input (0.0-10.0)
   - Air jet duration (s): Number input (0.0-5.0)
   - Set button sends values

8. **Section 6: PID Tuning (Advanced)**
   - P gain: Number input (0.0-100.0, 3 decimals)
   - I gain: Number input (0.0-10.0, 3 decimals)
   - D gain: Number input (0.0-10.0, 3 decimals)
   - Set button sends values

**Variables to Create**:
- `txt_eng_state` - Text for state
- `txt_eng_safety` - Text for safety
- `txt_eng_alarm` - Text for alarm
- `num_m1_rpm` - Number input for blade RPM
- `txt_m1_current_rpm` - Display current RPM
- `txt_m1_status` - Display status
- `num_m2_vel` - Number input for fixture velocity
- `num_m2_accel` - Number input for fixture accel
- `txt_m2_status` - Display status
- `btn_m2_jog_fwd` / `btn_m2_jog_rev` - Jog buttons
- `txt_m3_pos_mm` - Display position mm
- `txt_m3_pos_in` - Display position in
- `num_m3_target_mm` - Number input target mm
- `num_m3_target_in` - Number input target in
- `btn_m3_goto` - GOTO button
- `btn_m3_home` - HOME button
- `btn_m3_jog_fwd` / `btn_m3_jog_rev` - Jog buttons
- `num_cycle_dwell` - Number input dwell time
- `num_cycle_air` - Number input air jet time
- `num_pid_p` / `num_pid_i` / `num_pid_d` - PID gains

**Touch Event Code Examples**:

M1 RPM Set button Touch Release Event:
```
prints "m1.rpm=",0
prints num_m1_rpm.val,0
prints 10
```

M3 GOTO button (mm) Touch Release Event:
```
prints "m3.goto_mm=",0
prints num_m3_target_mm.val,0
prints 10
```

M3 HOME button Touch Release Event:
```
prints "cmd=HOME_M3",10
```

M2 JOG FWD button Touch Press Event:
```
prints "cmd=JOG_M2_FWD",10
```

M2 JOG FWD button Touch Release Event:
```
prints "cmd=STOP_JOG",10
```

PID Set button Touch Release Event:
```
prints "m3.pid.p=",0
prints num_pid_p.val,0
prints 10
prints "m3.pid.i=",0
prints num_pid_i.val,0
prints 10
prints "m3.pid.d=",0
prints num_pid_d.val,0
prints 10
```

---

## Receiving Data from Pi (Program.s Event)

The Nextion needs to parse incoming data and update display objects. Use the **Program.s (Serial Data Received)** event in the Nextion Editor.

**Basic Parsing Logic**:

The Pi sends lines like: `state=IDLE\n`

Nextion stores received data in the `systext` variable.

**Program.s Event Code** (pseudocode approach):

```
// Example: Check if received "state=" and extract value
if(systext=="state=IDLE")
{
  txt_state.txt="IDLE"
  txt_state.bco=1024  // Green background
}
if(systext=="state=ALARM")
{
  txt_state.txt="ALARM"
  txt_state.bco=63488  // Red background
}

// For numeric values, use substr or parsing
// Example: m1.rpm=3500
// Need to extract "3500" and set num_m1_rpm.val=3500

// Recommended: Use Nextion's string functions
// Or implement simple state machine in Program.s
```

**Important Notes**:
- Nextion's scripting is limited; complex parsing is difficult
- **Recommended approach**: Keep protocol simple, use discrete messages
- Alternatively: Use Nextion Instruction Set with `txt` objects

**Simpler Alternative**:
Since the Pi pushes specific values, you can use direct Nextion commands from Pi:

**From Pi Python**:
```python
# Instead of: "m1.rpm=3500\n"
# Send Nextion command: "txt_m1_rpm.txt=\"3500\"\xFF\xFF\xFF"
```

This bypasses Nextion parsing entirely. The Pi formats Nextion commands directly.

**Recommendation**: Use this simpler approach if possible. Modify `NextionBridge` Python class to send Nextion commands instead of key=value.

**Modified NextionBridge Approach**:

Update `app/services/nextion_bridge.py` to send Nextion-native commands:

```python
def _send_nextion_command(self, obj_name, property_name, value):
    """Send direct Nextion command."""
    if property_name == 'txt':
        cmd = f'{obj_name}.txt="{value}"'
    else:
        cmd = f'{obj_name}.{property_name}={value}'

    # Nextion requires 3x 0xFF terminator
    self.serial.write((cmd + '\xFF\xFF\xFF').encode('ascii'))
```

This makes Nextion programming much simpler - no parsing needed!

---

## Design Guidelines

### Colors
- **Green**: Normal operation, READY, success
- **Red**: Alarms, faults, ESTOP, NOT READY
- **Blue**: Active cycle, running
- **Yellow**: Warnings, reset buttons
- **Gray**: Disabled buttons

### Fonts
- **Large (32+)**: State display, alarm text
- **Medium (24)**: Main status values
- **Small (16-20)**: Labels, detailed info

### Button Sizes
- **START button**: 150x80 minimum (easy to press)
- **STOP button**: 120x60 (prominent)
- **Jog buttons**: 80x60 (hold to jog)
- **Navigation buttons**: 60x40

### Layout Principles
- **Customer screen**: Minimal, large text, clear status
- **Engineering screen**: Dense information, scrollable if needed
- **Touch targets**: 60x60 minimum for reliable touch
- **Spacing**: 10-20px between objects

---

## Nextion Project Setup

### Display Selection
- **Enhanced series** required (for more memory and features)
- **3.5" (480x320)**: Compact, sufficient for this application
- **5.0" (800x480)**: More space, easier to read
- **7.0" (800x480)**: Largest, best visibility

### Project Settings
1. **Model**: NX4832K035 (3.5" Enhanced) or larger
2. **Orientation**: Landscape
3. **Baudrate**: 115200
4. **Direction**: Send and Receive

### Resources Needed
- Font: Built-in fonts sufficient
- Icons: Optional (green/red circles for indicators)
- Background: Solid colors or simple gradients

---

## Testing the HMI

### Standalone Testing (No Pi)

1. **Simulator in Nextion Editor**:
   - Test button presses
   - Manually send test data via Debug → Simulator
   - Example: Type `txt_state.txt="IDLE"` in User Code

2. **Serial Terminal**:
   - Connect Nextion to PC via USB-TTL adapter
   - Use terminal (PuTTY, minicom) at 115200 baud
   - Manually type test commands:
     ```
     txt_state.txt="RUNNING"
     txt_m1_rpm.txt="3500"
     ```
   - Press buttons, see commands sent back

### Integrated Testing (With Pi)

1. **Connect Nextion to Pi UART** (GPIO14/15)
2. **Run Python application** (see main.py)
3. **Observe status updates** on Nextion (should update at 10 Hz)
4. **Press buttons**, check Python logs for received commands

---

## Nextion Code Examples

### Page 0 (Customer) - Page Preinitialize Event

```
// Initialize page on load
txt_state.txt="INIT"
txt_safety.txt="CHECKING..."
txt_alarm.txt=""
txt_alarm.vis=0  // Hide alarm text
num_cycle_count.val=0
```

### Button Color Changes

START button (btn_start) Touch Press Event:
```
btn_start.bco=1024  // Change to green when pressed
```

START button (btn_start) Touch Release Event:
```
btn_start.bco=2016  // Back to default
prints "cmd=START",10
```

### Conditional Visibility

If alarm exists, show alarm text and reset button.

In Program.s when receiving alarm status:
```
if(systext=="alarm=TIMEOUT_FWD")
{
  txt_alarm.txt="⚠️ TIMEOUT FWD"
  txt_alarm.vis=1
  btn_reset.vis=1
}
if(systext=="alarm=")
{
  txt_alarm.vis=0
  btn_reset.vis=0
}
```

### Number Formatting

For floating-point values (e.g., position), use Nextion's text formatting:

```
// In Program.s when receiving m3.pos_in=6.004
// Extract value and display
txt_m3_pos_in.txt="6.004 in"
```

---

## Complete Nextion Prompt for AI Assistant

Use this prompt if you're asking an AI (or human) to create the Nextion .HMI file:

---

**PROMPT START**

Create a complete Nextion HMI project (.HMI file) for an industrial pleat saw controller with the following specifications:

**Display**: Nextion Enhanced 3.5" (NX4832K035) or 5.0", 115200 baud

**Pages Required**:

1. **Page 0 - Customer Screen** (Operator View):
   - Large state display with color-coded background (green=idle, blue=running, red=alarm)
   - Safety status indicator (green "READY" or red "NOT READY")
   - Cycle counter and last cycle time
   - Backstop position in inches (3 decimals)
   - Blade status (RPM or STOPPED)
   - Conditional alarm display (large red text, hidden when no alarm)
   - START button (green, 150x80) - sends `cmd=START` + newline (ASCII 10)
   - STOP button (red, 120x60) - sends `cmd=STOP` + newline
   - RESET ALARMS button (yellow, visible only when alarm present) - sends `cmd=RESET_ALARMS` + newline
   - Engineering button (small, navigates to Page 1)

2. **Page 1 - Engineering Screen** (Setup/Diagnostics):
   - System status section (state, safety, alarm, cycle stats)
   - M1 Blade: RPM input (500-6000), set button sends `m1.rpm=<value>` + newline
   - M2 Fixture: Velocity and acceleration inputs, jog buttons (hold to jog, release to stop)
   - M3 Backstop: Position display (mm and inches), target input, GOTO/HOME buttons, jog controls
   - Cycle timing: Dwell and air jet duration inputs
   - PID tuning: P, I, D gain inputs with set button
   - Customer button (returns to Page 0)

**Communication Protocol**:
- Nextion receives updates from Pi: Direct Nextion commands like `txt_state.txt="IDLE"\xFF\xFF\xFF`
- Nextion sends commands to Pi: Simple text like `cmd=START\n` (where \n is ASCII 10)
- All Nextion → Pi messages must end with newline (ASCII 10)

**Variables/Objects Naming Convention**:
- Text displays: `txt_<name>` (e.g., `txt_state`, `txt_safety`)
- Number inputs: `num_<name>` (e.g., `num_m1_rpm`)
- Buttons: `btn_<name>` (e.g., `btn_start`, `btn_stop`)

**Touch Events**:
- All buttons that send commands must use `prints "<command>",10` in Touch Release Event
- Jog buttons use Touch Press (start jog) and Touch Release (stop jog)
- Navigation buttons use `page <n>` command

**Color Scheme**:
- Green: Normal/Ready (RGB 1024 or 2016)
- Red: Alarm/Fault (RGB 63488)
- Blue: Running (RGB 31)
- Yellow: Warnings (RGB 65504)
- Gray: Disabled (RGB 50712)

**Design Priority**:
- Customer screen: Large, clear, simple - operator should see state and safety at a glance
- Engineering screen: Detailed controls - can be dense, scrollable if needed
- Touch targets minimum 60x60 pixels
- Use built-in Nextion fonts (no custom fonts required)

**Deliverable**: A complete .HMI file that can be opened in Nextion Editor, compiled to .TFT, and uploaded to the display.

**PROMPT END**

---

## Final Notes

### Nextion Editor Download
- Download from: https://nextion.tech/nextion-editor/
- Use latest stable version
- Free for all displays

### Compilation & Upload
1. Open .HMI file in Nextion Editor
2. Compile (File → Compile) to generate .TFT file
3. Upload via:
   - **microSD card**: Copy .TFT to card, insert in Nextion, power on
   - **Serial upload**: Use Nextion Editor → Upload (slower, via USB-TTL)

### Debugging Tips
1. **Use Debug window** in Nextion Editor simulator
2. **Check serial output** from Nextion (should see command echoes)
3. **Use `print` statements** in Nextion code to debug
4. **Test buttons** before deploying - verify `prints` commands

### Common Pitfalls
1. **Forgetting newline terminator** - Use `,10` (ASCII 10) in `prints`
2. **Wrong baud rate** - Must match Pi (115200)
3. **TX/RX swap** - Connect Nextion TX to Pi RX, Nextion RX to Pi TX
4. **Power issues** - Nextion needs 5V, ~500mA - don't power from Pi GPIO
5. **Case sensitivity** - Object names are case-sensitive

---

## Conclusion

This prompt provides everything needed to create a functional Nextion HMI for the Pleat Saw controller. The HMI will integrate seamlessly with the Python application and provide both a simple operator interface and detailed engineering controls.

**Key Success Factors**:
- Keep Page 0 simple and clear
- Provide detailed controls on Page 1
- Test all buttons before final deployment
- Follow the communication protocol exactly
- Verify TX/RX wiring and baud rate

Good luck with your Nextion HMI development!

---

**Document Control**

**Version**: 1.0
**Date**: 2025-10-21
**Related Documents**:
- `docs/hmi_protocol.md` - Full protocol specification
- `app/services/nextion_bridge.py` - Python implementation
- `PROGRESS.md` - Overall project progress

---

**END OF NEXTION PROMPT**
