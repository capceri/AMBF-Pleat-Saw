# Commissioning Checklist

Step-by-step procedure for bringing up the Pleat Saw controller for the first time.

## Pre-Installation Checks

### Hardware Verification

- [ ] Raspberry Pi 4 (2GB+ RAM) with power supply
- [ ] MicroSD card (16GB+) with Raspberry Pi OS installed
- [ ] USB RS-485 adapter
- [ ] N4D3E16 I/O module with power supply
- [ ] ESP32-A programmed and powered
- [ ] ESP32-B programmed and powered
- [ ] Nextion HMI connected to Pi UART
- [ ] All motor drivers installed and powered
- [ ] Safety circuit wired and functional

### Mechanical Checks

- [ ] All motors mechanically coupled to their loads
- [ ] Blade motor (M1) rotation direction verified
- [ ] Fixture motor (M2) travel limits established
- [ ] Backstop motor (M3) home position defined
- [ ] Encoder properly coupled to backstop axis
- [ ] Sensors (IN2, IN3) installed and aligned
- [ ] Pneumatic clamp and air jet solenoids installed

---

## Phase 1: RS-485 Bus Commissioning

### Step 1: Configure N4D3E16 Module

1. Set slave ID to **1** using DIP switches
2. Set baud rate to **9600** using DIP switches
3. Power on module
4. Verify power LED is lit

### Step 2: Program ESP32 Devices

```bash
cd firmware/esp32a_axis12
pio run -t upload

cd ../esp32b_backstop
pio run -t upload
```

Verify:
- [ ] ESP32-A serial output shows "Modbus RTU slave ID=2"
- [ ] ESP32-B serial output shows "Modbus RTU slave ID=3"

### Step 3: Wire RS-485 Bus

Following [wiring_rs485.md](wiring_rs485.md):

- [ ] Connect all devices in daisy-chain topology
- [ ] Install 120Ω termination at both ends
- [ ] Connect common ground between all devices
- [ ] Connect cable shield at master (Pi) end only

### Step 4: Test Bus Communication

Install mbpoll:
```bash
sudo apt-get install mbpoll
```

Test each device:

```bash
# Test N4D3E16 (should return input register value)
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0xC0 -c 1 /dev/ttyUSB0
```
- [ ] N4D3E16 responds (slave ID 1)

```bash
# Test ESP32-A (should return firmware version 0x0100)
mbpoll -m rtu -b 9600 -P none -a 2 -t 3 -r 0x140 -c 1 /dev/ttyUSB0
```
- [ ] ESP32-A responds (slave ID 2)

```bash
# Test ESP32-B (should return status register)
mbpoll -m rtu -b 9600 -P none -a 3 -t 3 -r 0x205 -c 1 /dev/ttyUSB0
```
- [ ] ESP32-B responds (slave ID 3)

**If any device fails to respond, STOP and troubleshoot RS-485 bus before continuing.**

---

## Phase 2: Software Installation

### Step 1: Run One-Click Installer (Recommended)

The easiest way to install the software is using the automated installer:

```bash
cd pleat_saw
sudo bash pleat_saw_install.sh
```

The installer will:
- Install all system dependencies
- Create Python virtual environment
- Install Python packages
- Configure serial port permissions
- Install systemd service
- Run unit tests
- Generate installation summary

**Wait for installation to complete** (typically 5-10 minutes depending on internet speed).

After installation:
```bash
# Review installation summary
cat /home/pi/pleat_saw/INSTALLATION_INFO.txt

# Verify service is installed but not yet started
sudo systemctl status pleat-saw
```

- [ ] Installer completed successfully
- [ ] All tests passed (or skipped if hardware not connected)
- [ ] Service is installed and enabled

**Skip to Phase 3** if using the one-click installer.

### Step 1 (Alternative): Manual Python Installation

If you prefer manual installation:

```bash
cd pleat_saw/app
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

Verify installation:
```bash
python3 -c "import pymodbus, serial, yaml; print('OK')"
```
- [ ] All imports successful

### Step 2: Configure System

Edit configuration files:

```bash
nano ../config/system.yaml
```

Verify:
- [ ] RS-485 port: `/dev/ttyUSB0` (or your adapter's path)
- [ ] Nextion port: `/dev/ttyAMA0`
- [ ] Device IDs: io=1, esp32a=2, esp32b=3

```bash
nano ../config/io_map.yaml
```

Verify:
- [ ] Input mappings match your sensors
- [ ] Output mappings match your solenoids/lamps

```bash
nano ../config/motion.yaml
```

Adjust:
- [ ] M1 RPM range (500-6000)
- [ ] M2 speeds and accelerations
- [ ] M3 steps_per_mm (measure and calibrate)
- [ ] Cycle timing (dwell, air jet, etc.)

### Step 3: Test Dry Run

Run application in dry-run mode (mocked Modbus):

```bash
python3 main.py --dry-run
```

Verify:
- [ ] Application starts without errors
- [ ] Logs show "DRY RUN MODE"
- [ ] Services initialize successfully
- [ ] Can exit cleanly with Ctrl+C

---

## Phase 3: I/O Verification

### Step 1: Test Inputs

Run application (NOT dry-run):

```bash
python3 main.py
```

Open another terminal and monitor logs:
```bash
tail -f /var/log/pleat_saw/pleat_saw.log
```

Manually activate each input and verify detection:
- [ ] IN1 (Start button) - logs show input change
- [ ] IN2 (Sensor2) - logs show input change
- [ ] IN3 (Sensor3) - logs show input change
- [ ] IN16 (Safety) - logs show input change

**CRITICAL**: Verify safety input (IN16) logic:
- Active (circuit complete) = READY
- Inactive (circuit open) = NOT READY

Test safety interlock:
- [ ] With IN16 active, supervisor state = IDLE
- [ ] When IN16 goes inactive, supervisor enters ESTOP

### Step 2: Test Outputs

In Python, manually control outputs:

```python
from services import IOPoller, ModbusMaster

modbus = ModbusMaster('/dev/ttyUSB0', 9600)
modbus.connect()

io = IOPoller(modbus, 1, input_map, output_map, 10.0)

# Test each output
io.set_output('green_solid', True)   # Should turn on green solid lamp
io.set_output('green_flash', True)   # Should turn on green flash lamp
io.set_output('clamp', True)         # Should activate clamp
io.set_output('air_jet', True)       # Should activate air jet
```

Verify:
- [ ] CH1 (Clamp) operates correctly
- [ ] CH2 (Air Jet) operates correctly
- [ ] CH3 (Green Solid) lights up
- [ ] CH4 (Green Flash) lights up

Turn all outputs OFF before continuing.

---

## Phase 4: Motor Commissioning

### Step 1: Test M1 Blade Motor (No Load)

**SAFETY**: Ensure blade is NOT installed for initial testing.

```python
from services import AxisGateway, ModbusMaster

modbus = ModbusMaster('/dev/ttyUSB0', 9600)
modbus.connect()

axis = AxisGateway(modbus, 2, 3)

# Start blade at low RPM
axis.m1_start(rpm=1000, ramp_ms=500)

# Wait a few seconds, observe motor

# Stop
axis.m1_stop()
```

Verify:
- [ ] Motor rotates in correct direction
- [ ] No unusual noise or vibration
- [ ] Can start and stop smoothly
- [ ] RPM increases when commanded higher

Test at target RPM:
- [ ] Motor runs at 3500 RPM (or your target)

### Step 2: Test M2 Fixture Motor

**SAFETY**: Ensure fixture travel area is clear.

```python
# Set velocity
axis.m2_set_velocity(vel_mm_s=50.0, accel_mm_s2=1000.0)

# Jog forward slowly
axis.m2_jog_forward(vel_mm_s=50.0)

# Observe motor, then stop
axis.m2_stop()

# Jog reverse
axis.m2_jog_reverse(vel_mm_s=50.0)

# Stop
axis.m2_stop()
```

Verify:
- [ ] Motor rotates in both directions
- [ ] Forward direction moves toward Sensor3
- [ ] Reverse direction moves toward Sensor2
- [ ] Speed is reasonable (50 mm/s)

Test sensor-based moves:
```python
# Feed forward until Sensor3
axis.m2_feed_forward()

# Monitor IN3 input - should stop when sensor is reached
# If timeout, manually send stop command
```

Verify:
- [ ] Motor stops when Sensor3 is reached
- [ ] No overshoot or collision

Repeat for reverse direction:
- [ ] Motor stops when Sensor2 is reached

### Step 3: Test M3 Backstop Motor

**SAFETY**: Ensure backstop travel area is clear.

```python
# Home backstop (sets current position as zero)
axis.m3_home()

# Wait for homing to complete
import time
time.sleep(2)

# Get current position
pos = axis.m3_get_position()
print(f"Position: {pos} mm")

# Move to target position (small move for initial test)
axis.m3_goto(target_mm=10.0, vel_mm_s=20.0, accel_mm_s2=500.0)

# Monitor status
while True:
    status = axis.m3_get_status()
    pos = axis.m3_get_position()
    print(f"Status: {status}, Pos: {pos} mm")
    if status['at_target']:
        break
    time.sleep(0.1)
```

Verify:
- [ ] Motor moves to target position
- [ ] PID loop converges (in_motion → at_target)
- [ ] Position reported via Modbus
- [ ] Encoder counts incrementing correctly

Calibrate steps_per_mm:
1. Command move of known distance (e.g., 100 mm)
2. Measure actual travel
3. Calculate: `actual_steps_per_mm = (commanded_mm / actual_mm) * current_steps_per_mm`
4. Update `config/motion.yaml` with measured value

- [ ] M3 steps_per_mm calibrated and verified

---

## Phase 5: Nextion HMI Integration

### Step 1: Connect Nextion

- [ ] Connect Nextion TX to Pi RX (GPIO15)
- [ ] Connect Nextion RX to Pi TX (GPIO14)
- [ ] Connect Nextion GND to Pi GND
- [ ] Power Nextion from 5V supply (NOT Pi)

### Step 2: Enable Pi UART

```bash
sudo raspi-config
# Interface Options → Serial Port
# "Would you like a login shell accessible over serial?" → No
# "Would you like the serial port hardware enabled?" → Yes

# Edit /boot/config.txt
sudo nano /boot/config.txt

# Add line:
dtoverlay=uart0

# Reboot
sudo reboot
```

### Step 3: Test Serial Communication

```bash
# Install minicom
sudo apt-get install minicom

# Open Nextion port
minicom -D /dev/ttyAMA0 -b 115200

# Type test message and press Enter
state=IDLE

# Should see response from Nextion (if programmed)
```

- [ ] Serial communication working

### Step 4: Program Nextion

Referring to [hmi_protocol.md](hmi_protocol.md):

1. Create Nextion project with required pages and objects
2. Configure button touch events to send commands
3. Upload .tft file to Nextion via microSD or serial upload

- [ ] Nextion displays properly
- [ ] Buttons send commands
- [ ] Status updates from Pi appear on screen

---

## Phase 6: Full System Test

### Step 1: Run Application as Service

Install systemd service (see [systemd/README.md](../systemd/README.md)):

```bash
sudo cp systemd/pleat-saw.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pleat-saw.service
sudo systemctl start pleat-saw.service
```

Check status:
```bash
sudo systemctl status pleat-saw.service
```

- [ ] Service starts without errors
- [ ] Logs show all services initialized
- [ ] HMI displays "IDLE / READY"

### Step 2: Safety Interlock Test

**CRITICAL SAFETY TEST**

1. Ensure IN16 (safety input) is ACTIVE (READY)
2. Verify supervisor state = IDLE
3. **Manually trigger IN16 to go inactive** (open safety circuit)
4. Immediately verify:
   - [ ] All motors stop
   - [ ] Outputs go to safe state (clamp OFF, air OFF)
   - [ ] Supervisor enters ESTOP
   - [ ] HMI displays "EMERGENCY STOP"

5. Restore IN16 to active
6. Send RESET_ALARMS from HMI
7. Verify:
   - [ ] Supervisor returns to IDLE
   - [ ] System ready for operation

**DO NOT PROCEED if safety interlock does not work correctly.**

### Step 3: Manual Cycle Test (No Blade)

**SAFETY**: Perform first cycle test **without blade installed**.

1. Verify safety input READY
2. Press START button (IN1 or HMI)
3. Observe full cycle:
   - [ ] Blade motor starts (no blade installed, just motor)
   - [ ] Fixture feeds forward to Sensor3
   - [ ] Dwell delay occurs
   - [ ] Fixture reverses to Sensor2
   - [ ] Clamp activates
   - [ ] "Blade" stops (motor stops)
   - [ ] Air jet pulses
   - [ ] Cycle completes, returns to IDLE

4. Check logs for any errors or warnings

- [ ] Complete cycle runs successfully without blade

### Step 4: Production Test (With Blade)

**SAFETY**: Ensure all guards and safety devices are in place.

**WARNING**: Blade will be spinning. Ensure area is clear.

1. Install blade on M1 motor
2. Set target RPM (e.g., 3500)
3. Verify all safety guards in place
4. Run test cycle with material
5. Observe:
   - [ ] Blade reaches target RPM before feeding
   - [ ] Fixture feeds material smoothly
   - [ ] Cut completes at forward position
   - [ ] Material retracts to home
   - [ ] Clamp holds during blade stop
   - [ ] Air jet clears debris
   - [ ] Cycle time reasonable

6. Run multiple cycles to verify consistency:
   - [ ] 10 consecutive cycles complete successfully
   - [ ] No alarms or faults
   - [ ] Cut quality acceptable

---

## Phase 7: Tuning and Optimization

### Step 1: Adjust Cycle Timing

Edit `config/motion.yaml` and tune:

- [ ] `dwell_after_s3_s` - Adjust for your material
- [ ] `air_jet_s` - Adjust for debris clearance
- [ ] `saw_spindown_s` - Verify blade stops safely

### Step 2: Adjust Motion Parameters

- [ ] M1 RPM - Set to optimal blade speed for material
- [ ] M2 feed speed - Balance cycle time vs. smooth operation
- [ ] M2 acceleration - Avoid shock loading
- [ ] Timeouts - Set 20-50% above typical cycle time

### Step 3: Tune M3 PID (If Using Backstop)

If backstop moves during cycle:

1. Start with P-only control: `P=1.0, I=0.0, D=0.0`
2. Increase P until oscillation
3. Reduce P by 50%
4. Add I term if steady-state error
5. Add D term if overshoot

- [ ] M3 PID tuned for fast, stable settling

### Step 4: Set Production Parameters

- [ ] M1 RPM finalized
- [ ] M2 speeds finalized
- [ ] Cycle timing optimized
- [ ] Timeout values set with margin
- [ ] Backstop positions defined (if used)

---

## Phase 8: Documentation and Handoff

### Step 1: Record Configuration

Document final configuration:
- [ ] Save copy of all YAML files
- [ ] Note M3 steps_per_mm calibration
- [ ] Record typical cycle time
- [ ] Note any custom modifications

### Step 2: Create Operator Instructions

- [ ] Startup procedure
- [ ] Normal operation
- [ ] Shutdown procedure
- [ ] Alarm reset procedure
- [ ] Emergency stop procedure

### Step 3: Create Maintenance Schedule

- [ ] Encoder cleaning/inspection interval
- [ ] Sensor alignment check interval
- [ ] Log file rotation/archival
- [ ] Backup procedure

### Step 4: Training

- [ ] Train operators on normal operation
- [ ] Train operators on alarm handling
- [ ] Train maintenance staff on troubleshooting
- [ ] Train engineers on configuration changes

---

## Sign-Off

- [ ] All commissioning steps completed
- [ ] All tests passed
- [ ] Safety interlocks verified
- [ ] Documentation complete
- [ ] Training complete

**Commissioned by**: ___________________________

**Date**: ___________________________

**Signature**: ___________________________
