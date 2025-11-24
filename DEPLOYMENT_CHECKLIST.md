# Pleat Saw Controller v3.1 - Deployment Checklist

## Pre-Deployment Validation ✅

### Code Quality
- [x] All Python files pass syntax check (13 files)
- [x] All YAML config files valid (3 files)
- [x] HTML/CSS/JavaScript files created and formatted
- [x] No syntax errors in any source files
- [x] All imports resolve correctly

### Files Complete
- [x] Systemd service file fixed
- [x] Requirements.txt updated with Flask dependencies
- [x] Web monitor service implemented (422 lines)
- [x] Dashboard HTML created (237 lines)
- [x] Dashboard CSS styling (366 lines)
- [x] Dashboard JavaScript client (394 lines)
- [x] Web monitoring guide (850+ lines)
- [x] Update documentation (600+ lines)
- [x] Implementation summary created
- [x] README updated with v3.1 features

### Integration
- [x] Web monitor integrated into main.py
- [x] Web monitor exported in services/__init__.py
- [x] Supervisor enhanced with required methods
- [x] Configuration file updated with web_monitor section
- [x] One-click installer compatible

---

## Deployment Steps

### Step 1: Transfer Files to Raspberry Pi

```bash
# From your development machine
cd "/Users/ceripritch/Documents/Pleat Saw V3/panel_node_rounddb_s3_minui"
scp -r pleat_saw pi@<raspberry-pi-ip>:/home/pi/

# Example:
scp -r pleat_saw pi@192.168.1.100:/home/pi/
```

**Verify:**
```bash
ssh pi@<raspberry-pi-ip>
ls -la /home/pi/pleat_saw
# Should show all directories: app, config, docs, firmware, systemd, etc.
```

---

### Step 2: Run One-Click Installer

```bash
ssh pi@<raspberry-pi-ip>
cd /home/pi/pleat_saw
sudo bash pleat_saw_install.sh
```

**Expected Output:**
- Step 1: System update
- Step 2: Install dependencies
- Step 3: Create directory structure
- Step 4: Copy application files
- Step 5: Setup virtual environment
- Step 6: Install Python packages (including Flask, Flask-SocketIO)
- Step 7: Configure serial permissions
- Step 8: Install systemd service
- Step 9: Set file permissions
- Step 10: Run unit tests (may have warnings, OK if main app loads)
- Step 11: Generate installation summary

**Installation Time:** 5-10 minutes (depending on internet speed)

---

### Step 3: Verify Service Status

```bash
# Check service is running
sudo systemctl status pleat-saw
```

**Expected Output:**
```
● pleat-saw.service - Pleat Saw Controller
     Loaded: loaded (/etc/systemd/system/pleat-saw.service; enabled)
     Active: active (running) since ...
     Main PID: 1234 (python3)
```

**Key Check Points:**
- Status: **active (running)** ✓
- No **status=1/FAILURE** error ✓
- Main PID shows python3 running ✓

**If service fails:**
```bash
# View detailed logs
sudo journalctl -u pleat-saw -n 100

# Common issues:
# - Missing dependencies: Re-run installer
# - Permission errors: Check /var/log/pleat_saw ownership
# - Config errors: Validate YAML files
```

---

### Step 4: Test Web Dashboard Access

#### From Raspberry Pi:
```bash
curl http://localhost:5000
```

**Expected:** HTML content returned (should include "Pleat Saw Controller")

#### From Network Computer:
```bash
# Find Pi IP address
ssh pi@<pi-ip>
hostname -I
# Note the IP address (e.g., 192.168.1.100)
```

**Open web browser to:** `http://<pi-ip>:5000`

**Expected:**
- Dashboard loads with professional styling
- Connection indicator shows green "Connected"
- All panels visible (System Status, Inputs, Outputs, Motors, etc.)
- No 404 or 500 errors

**If dashboard doesn't load:**
```bash
# Check web monitor service
sudo journalctl -u pleat-saw | grep -i "web monitor"

# Verify port is listening
sudo netstat -tuln | grep 5000
# Should show: tcp 0 0 0.0.0.0:5000 ... LISTEN

# Check firewall
sudo ufw status
sudo ufw allow 5000/tcp  # If firewall is active
```

---

### Step 5: Test Real-Time Updates

1. **Open Dashboard** in web browser
2. **Observe Connection Status**
   - Green dot = Connected (WebSocket working)
   - Red dot = Disconnected (check browser console)

3. **Test Input Monitoring**
   - Physically activate Sensor2 (IN2)
   - Observe "Sensor2 / Home" indicator changes to ON
   - Should update within ~100ms (10 Hz rate)

4. **Check Console Log**
   - Bottom panel should show timestamped messages
   - Look for connection confirmation messages

**If real-time updates not working:**
- Check browser console (F12 → Console)
- Look for WebSocket errors
- Verify Flask-SocketIO installed: `/home/pi/pleat_saw/venv/bin/pip list | grep -i socket`

---

### Step 6: Test Manual Control (Safety First!)

⚠️ **WARNING:** Only test with safety circuit OK and machine in safe state

#### Test Output Control:
1. Click "Toggle" button for **Green Solid** (CH3)
2. Verify:
   - Indicator changes to ON (green)
   - Physical lamp illuminates (if connected)
   - Console shows: "Sent command: set_output"

#### Test Motor Control (M1 Blade):
**ENSURE BLADE IS DISCONNECTED OR GUARDED**

1. Set RPM to **500** (minimum)
2. Click **"Start"**
3. Verify:
   - "Running" indicator turns ON
   - Console shows: "Sent command: m1_start"
   - Motor spins (if connected and safe)
4. Click **"Stop"**
5. Verify:
   - "Running" indicator turns OFF
   - Motor stops

#### Test System Statistics:
1. Observe **System Statistics** panel
2. Counters should increment:
   - Modbus Reads increasing
   - Modbus Writes increasing
   - I/O Polls increasing rapidly (100 Hz)

**If controls don't work:**
- Check command log for errors
- Verify supervisor service running
- Check Modbus communication to hardware

---

### Step 7: Configuration Verification

```bash
# View installed configuration
cat /home/pi/pleat_saw/config/system.yaml | grep -A 6 "web_monitor:"
```

**Expected:**
```yaml
web_monitor:
  enabled: true
  port: 5000
  host: 0.0.0.0
  update_rate_hz: 10
  require_auth: false
  debug: false
```

**Optional Configuration Changes:**

#### Change Port (if 5000 conflicts):
```bash
nano /home/pi/pleat_saw/config/system.yaml
# Change: port: 5000 → port: 8080
sudo systemctl restart pleat-saw
```

#### Restrict to Local Access Only:
```bash
nano /home/pi/pleat_saw/config/system.yaml
# Change: host: 0.0.0.0 → host: 127.0.0.1
sudo systemctl restart pleat-saw
# Now only accessible via SSH tunnel
```

#### Adjust Update Rate:
```bash
# For slower updates (lower CPU usage):
update_rate_hz: 5

# For faster updates (higher responsiveness):
update_rate_hz: 20

sudo systemctl restart pleat-saw
```

---

### Step 8: Hardware Integration Test

**Prerequisites:**
- RS-485 bus wired and terminated
- ESP32-A and ESP32-B programmed and powered
- N4D3E16 configured and powered
- Safety circuit wired and functional

#### Test I/O Module (N4D3E16):
1. Open dashboard
2. Check **System Statistics → Modbus Errors**
   - Should be 0 or very low count
   - High errors = wiring/termination issue

3. Activate **Start Button** (IN1)
   - Dashboard should show "Start" input ON

4. Activate **Sensor2** (IN2)
   - Dashboard should show "Sensor2" input ON

5. Toggle **Clamp** output (CH1)
   - Solenoid should actuate
   - Dashboard indicator should match

#### Test ESP32-A (Blade + Fixture):
1. Set M1 RPM to **1000**
2. Click "Start"
3. Verify:
   - Running indicator ON
   - Statistics: Modbus Reads/Writes increasing
   - Motor spins smoothly

4. Set M2 Vel to **50 mm/s**
5. Click "Jog FWD"
6. Verify:
   - In Motion indicator ON
   - Fixture moves forward
   - Can stop with "Stop" button

#### Test ESP32-B (Backstop):
1. Click **"Home"**
2. Verify:
   - Homed indicator turns ON
   - Position reads ~0.000 mm

3. Set Target to **10.0 mm**
4. Click **"Go To"**
5. Verify:
   - In Motion indicator ON during move
   - At Target turns ON when complete
   - Position reads ~10.000 mm (±0.010)

**If hardware communication fails:**
```bash
# Check Modbus statistics
# High error count = wiring/termination issue

# View detailed logs
sudo journalctl -u pleat-saw -f

# Check RS-485 connections:
# - Termination resistors (120Ω at both ends)
# - A/B wiring correct (not swapped)
# - Ground reference connected
```

---

### Step 9: Safety Interlock Test ⚠️ CRITICAL

**This is a required safety test - Do not skip!**

1. **Verify Safety Input Ready**
   - Dashboard shows: Safety = READY (green)
   - System state: IDLE

2. **Start Manual Motor Movement**
   - Jog M2 forward slowly

3. **Trigger Safety Circuit**
   - Press E-STOP button or open safety door
   - **IMMEDIATELY verify:**
     - All motors STOP
     - Dashboard shows: Safety = NOT_READY (red)
     - System state: ESTOP or ALARM
     - All outputs go to safe state (clamp OFF)

4. **Restore and Reset**
   - Close safety circuit
   - Dashboard should show: Safety = READY
   - Click **"Reset Alarms"**
   - System should return to IDLE

**If safety interlock fails:**
- **DO NOT PROCEED**
- Check IN16 wiring
- Verify safety circuit functionality
- Review logs for safety violations
- Contact engineering support

---

### Step 10: Automatic Cycle Test

**Prerequisites:**
- All hardware tests passed
- Safety interlock verified
- Sensors aligned and functional

#### Dry Run (No Blade):
1. Disable or disconnect blade motor
2. Dashboard: Click **"Start Cycle"**
3. Observe state progression:
   - IDLE → PRECHECK
   - PRECHECK → START_SPINDLE
   - START_SPINDLE → FEED_FWD
   - FEED_FWD → DWELL (when S3 triggers)
   - DWELL → FEED_REV
   - FEED_REV → CLAMP (when S2 triggers)
   - CLAMP → SAW_STOP
   - SAW_STOP → AIR_JET
   - AIR_JET → COMPLETE
   - COMPLETE → IDLE

4. Watch console log for timing
5. Verify cycle completes without alarms

**Common Issues:**
- **TIMEOUT_FWD alarm**: Sensor3 not triggering or misaligned
- **TIMEOUT_REV alarm**: Sensor2 not triggering or misaligned
- **PRECHECK fails**: Safety not READY or previous alarm not reset

---

### Step 11: Document Configuration

```bash
# Save final configuration
cd /home/pi/pleat_saw
cat config/system.yaml > ~/pleat_saw_config_backup.yaml
cat config/io_map.yaml >> ~/pleat_saw_config_backup.yaml
cat config/motion.yaml >> ~/pleat_saw_config_backup.yaml

# Save installation info
cat INSTALLATION_INFO.txt

# Note web dashboard URL
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
```

**Record:**
- Dashboard URL: ___________________________
- Pi IP Address: ___________________________
- Installation Date: ___________________________
- Configuration Changes: ___________________________
- Calibration Values: ___________________________

---

### Step 12: Enable Auto-Start

```bash
# Service should already be enabled by installer
# Verify:
sudo systemctl is-enabled pleat-saw
# Should output: enabled

# If not enabled:
sudo systemctl enable pleat-saw

# Test reboot
sudo reboot

# After reboot, verify service starts automatically:
sudo systemctl status pleat-saw
# Should show: active (running)

# Verify dashboard accessible
# Open browser to: http://<pi-ip>:5000
```

---

## Post-Deployment Checklist

### ✅ Service Health
- [ ] Systemd service shows "active (running)"
- [ ] No "status=1/FAILURE" error
- [ ] Service starts automatically on boot
- [ ] No critical errors in logs

### ✅ Web Dashboard
- [ ] Dashboard accessible at http://<pi-ip>:5000
- [ ] Connection indicator shows green "Connected"
- [ ] All panels load correctly
- [ ] Real-time updates working (10 Hz)
- [ ] Console log shows messages

### ✅ Manual Control
- [ ] Output toggle buttons work
- [ ] Motor start/stop commands work
- [ ] Position commands work (M3)
- [ ] Commands appear in console log
- [ ] Physical outputs respond

### ✅ Hardware Communication
- [ ] Modbus error count is low (<1%)
- [ ] All inputs respond in real-time
- [ ] All outputs actuate correctly
- [ ] Motor status updates correctly
- [ ] Position readings accurate (M3)

### ✅ Safety Systems
- [ ] Safety input monitored continuously
- [ ] Emergency stop triggers immediately
- [ ] All motors stop on E-STOP
- [ ] Outputs go to safe state
- [ ] Manual reset required after E-STOP
- [ ] Cycle cannot start with safety NOT_READY

### ✅ Automatic Cycle
- [ ] Dry run cycle completes successfully
- [ ] All states execute in order
- [ ] Sensors trigger correctly
- [ ] Timing matches configuration
- [ ] Cycle count increments
- [ ] No timeout alarms

### ✅ Documentation
- [ ] Configuration backed up
- [ ] Dashboard URL documented
- [ ] Calibration values recorded
- [ ] Installation info saved
- [ ] Commissioning notes made

---

## Troubleshooting Quick Reference

### Service Won't Start
```bash
sudo journalctl -u pleat-saw -n 100
# Look for Python import errors or missing dependencies
# Solution: Re-run installer
```

### Dashboard 404 Error
```bash
# Check web directory exists
ls -la /home/pi/pleat_saw/app/web/
# Should show: templates/ and static/ directories
```

### WebSocket Disconnected
```bash
# Check Flask-SocketIO installed
/home/pi/pleat_saw/venv/bin/pip list | grep -i socketio
# Should show: Flask-SocketIO and python-socketio
```

### High Modbus Errors
```bash
# Check RS-485 wiring
# Verify termination resistors (120Ω)
# Check baud rate matches (9600)
# Ensure all devices powered
```

### Safety Not Responding
```bash
# Check IN16 wiring (bit 15 in register 0x00C0)
# Verify safety logic: active = READY
# Test with multimeter: safety OK should be HIGH on input
```

---

## Support Resources

### Documentation
- **Web Monitoring Guide:** `/home/pi/pleat_saw/docs/web_monitoring_guide.md`
- **Update Documentation:** `/home/pi/pleat_saw/UPDATES_V3.1.md`
- **Implementation Summary:** `/home/pi/pleat_saw/IMPLEMENTATION_SUMMARY.md`
- **Installation Guide:** `/home/pi/pleat_saw/docs/installation_guide.md`
- **Commissioning Checklist:** `/home/pi/pleat_saw/docs/commissioning_checklist.md`

### Commands
```bash
# View logs
sudo journalctl -u pleat-saw -f

# Restart service
sudo systemctl restart pleat-saw

# Check status
sudo systemctl status pleat-saw

# Edit configuration
nano /home/pi/pleat_saw/config/system.yaml

# Test Python imports
/home/pi/pleat_saw/venv/bin/python3 -c "from services import WebMonitor; print('OK')"
```

### Contact
- Controls Engineering Team
- Technical Support: [contact info]
- Emergency: [contact info]

---

## Sign-Off

**Installation Completed By:** ___________________________

**Date:** ___________________________

**Dashboard URL:** ___________________________

**All Tests Passed:** [ ] Yes  [ ] No

**Notes:** ___________________________
___________________________
___________________________

**Signature:** ___________________________

---

**Deployment Status: READY FOR FIELD INSTALLATION**

**Version:** 3.1
**Date:** 2025-10-22
**Status:** All validation complete, one-click installer ready
