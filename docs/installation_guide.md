# Installation Guide

Complete guide for installing the Pleat Saw Controller on a Raspberry Pi.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Installation (Recommended)](#quick-installation-recommended)
3. [Manual Installation](#manual-installation)
4. [Post-Installation Configuration](#post-installation-configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Updating](#updating)
8. [Uninstallation](#uninstallation)

---

## Prerequisites

### Hardware Requirements

- **Raspberry Pi 4** (2GB RAM minimum, 4GB recommended)
- **MicroSD Card** (16GB minimum, 32GB recommended, Class 10 or better)
- **Power Supply** (Official Raspberry Pi 5V/3A USB-C recommended)
- **USB RS-485 Adapter** (CP2102, FT232, or similar)
- **Ethernet or WiFi** connection for downloading packages
- **Keyboard and Monitor** (for initial setup) or SSH access

### Hardware to be Connected

- **N4D3E16 I/O Module** (slave ID 1)
- **ESP32-A Controller** (slave ID 2, programmed with blade/fixture firmware)
- **ESP32-B Controller** (slave ID 3, programmed with backstop firmware)
- **Nextion HMI** (connected to Pi UART)
- **RS-485 bus** properly wired with termination resistors

### Software Requirements

- **Raspberry Pi OS** Bookworm (64-bit recommended) or later
- Internet connection for package downloads
- Root/sudo access

### Skill Requirements

- Basic Linux command-line knowledge
- Ability to SSH to Raspberry Pi
- Basic understanding of serial communication

---

## Quick Installation (Recommended)

The one-click installer automates the entire installation process.

### Step 1: Prepare Raspberry Pi

1. Flash Raspberry Pi OS to microSD card using Raspberry Pi Imager
2. Boot the Pi and complete initial setup
3. Enable SSH (if using headless):
   ```bash
   sudo raspi-config
   # Interface Options → SSH → Enable
   ```
4. Update system:
   ```bash
   sudo apt-get update
   sudo apt-get upgrade -y
   ```

### Step 2: Transfer Installation Files

From your development machine:

```bash
# Copy pleat_saw directory to Raspberry Pi
scp -r pleat_saw pi@raspberrypi.local:/tmp/

# Or use USB drive:
# 1. Copy pleat_saw folder to USB drive
# 2. On Pi: sudo mount /dev/sda1 /mnt
# 3. On Pi: cp -r /mnt/pleat_saw /tmp/
```

### Step 3: Run the Installer

SSH to the Raspberry Pi and run:

```bash
ssh pi@raspberrypi.local
cd /tmp/pleat_saw
sudo bash pleat_saw_install.sh
```

The installer will:
- Update system packages
- Install Python 3.11 and development tools
- Create directory structure at `/home/pi/pleat_saw`
- Copy application files
- Create Python virtual environment
- Install Python dependencies
- Configure serial port permissions (add user to dialout group)
- Create udev rules for serial devices
- Install and enable systemd service
- Set proper file permissions
- Run unit tests
- Generate installation summary

**Installation takes 5-10 minutes** depending on internet speed.

### Step 4: Review Installation

After installer completes:

```bash
# Review installation summary
cat /home/pi/pleat_saw/INSTALLATION_INFO.txt

# Verify service is installed
sudo systemctl status pleat-saw

# Check installed packages
/home/pi/pleat_saw/venv/bin/pip list
```

**Expected output:**
- Service shows as "loaded" and "enabled"
- Service is inactive (not yet started)
- Python packages include: pymodbus, pyserial, pyyaml, pytest

### Step 5: Log Out and Back In

Group membership changes require re-login:

```bash
exit  # Exit SSH session
ssh pi@raspberrypi.local  # Log back in

# Verify dialout group membership
groups | grep dialout  # Should show "dialout"
```

**Skip to [Post-Installation Configuration](#post-installation-configuration).**

---

## Manual Installation

If you need to customize the installation or the automated installer doesn't work:

### Step 1: System Preparation

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    build-essential \
    libffi-dev \
    libssl-dev
```

### Step 2: Create Directory Structure

```bash
# Create installation directory
sudo mkdir -p /home/pi/pleat_saw
sudo chown pi:pi /home/pi/pleat_saw

# Create subdirectories
mkdir -p /home/pi/pleat_saw/app
mkdir -p /home/pi/pleat_saw/app/services
mkdir -p /home/pi/pleat_saw/app/utils
mkdir -p /home/pi/pleat_saw/app/tests
mkdir -p /home/pi/pleat_saw/config
mkdir -p /home/pi/pleat_saw/logs
mkdir -p /home/pi/pleat_saw/data
```

### Step 3: Copy Application Files

```bash
# Copy from source (adjust path as needed)
cp -r /tmp/pleat_saw/app/* /home/pi/pleat_saw/app/
cp -r /tmp/pleat_saw/config/* /home/pi/pleat_saw/config/
cp /tmp/pleat_saw/requirements.txt /home/pi/pleat_saw/
cp -r /tmp/pleat_saw/docs /home/pi/pleat_saw/
cp -r /tmp/pleat_saw/systemd /home/pi/pleat_saw/
```

### Step 4: Python Virtual Environment

```bash
cd /home/pi/pleat_saw

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(pymodbus|pyserial|pyyaml|pytest)"
```

### Step 5: Configure Serial Permissions

```bash
# Add user to dialout group
sudo usermod -a -G dialout pi

# Create udev rules
sudo nano /etc/udev/rules.d/99-pleatsaw-serial.rules
```

Add this content:

```
# Pleat Saw Controller - Serial Port Rules
# RS-485 Modbus devices
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", GROUP="dialout"

# Nextion HMI
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="dialout"
```

Reload udev:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Step 6: Install Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/pleat-saw.service
```

Add this content:

```ini
[Unit]
Description=Pleat Saw Controller
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/pleat_saw/app
ExecStart=/home/pi/pleat_saw/venv/bin/python /home/pi/pleat_saw/app/main.py
Restart=always
RestartSec=10

# Environment
Environment=PYTHONUNBUFFERED=1

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable pleat-saw.service
```

### Step 7: Run Tests

```bash
cd /home/pi/pleat_saw
source venv/bin/activate
pytest app/tests/ -v
```

**Expected:** All tests pass (or skip if hardware not connected).

### Step 8: Log Out and Back In

```bash
exit  # Log out
ssh pi@raspberrypi.local  # Log back in

# Verify group membership
groups | grep dialout
```

---

## Post-Installation Configuration

Before starting the service, configure it for your hardware:

### Step 1: Configure RS-485 Serial Port

Edit system configuration:

```bash
nano /home/pi/pleat_saw/config/system.yaml
```

Find the `rs485` section and set the correct serial port:

```yaml
rs485:
  port: "/dev/ttyUSB0"  # Adjust to match your RS-485 adapter
  baud: 9600
  parity: "N"
  stopbits: 1
  bytesize: 8
  timeout: 0.1
```

**Finding your RS-485 port:**

```bash
# List USB serial devices
ls -l /dev/ttyUSB* /dev/ttyACM*

# Or use dmesg
dmesg | grep tty

# Or check with lsusb
lsusb
```

Common ports:
- `/dev/ttyUSB0` - Most USB-to-serial adapters
- `/dev/ttyACM0` - Some Arduino-based adapters
- `/dev/ttyAMA0` - Pi UART (if using)

### Step 2: Configure Nextion HMI Port

In the same `system.yaml` file:

```yaml
nextion:
  port: "/dev/ttyS0"     # Adjust for your setup
  baud: 115200
  timeout: 0.5
  update_rate: 10        # Hz
```

Common Nextion ports:
- `/dev/ttyS0` - Pi GPIO UART (pins 8/10)
- `/dev/ttyUSB1` - If using USB-to-serial adapter
- `/dev/ttyAMA0` - Pi UART0 (if available)

**If using GPIO UART:**

```bash
# Enable UART in config
sudo raspi-config
# Interface Options → Serial Port
# Login shell: No
# Serial hardware: Yes

# Reboot
sudo reboot
```

### Step 3: Configure I/O Mapping

Edit I/O mapping:

```bash
nano /home/pi/pleat_saw/config/io_map.yaml
```

Verify inputs and outputs match your wiring:

```yaml
inputs:
  start_button: 1      # IN1
  sensor2: 2           # IN2 (fixture reverse limit)
  sensor3: 3           # IN3 (fixture forward limit)
  safety_relay: 16     # IN16 (safety circuit)

outputs:
  clamp: 1             # CH1 (pneumatic clamp)
  air_jet: 2           # CH2 (air jet solenoid)
  lamp_green: 3        # CH3 (status lamp)
  lamp_red: 4          # CH4 (status lamp)
```

### Step 4: Configure Motion Parameters

Edit motion settings:

```bash
nano /home/pi/pleat_saw/config/motion.yaml
```

**IMPORTANT:** These are placeholder values. Tune during commissioning!

```yaml
m1_blade:
  rpm_min: 0
  rpm_max: 1500
  rpm_nominal: 1200
  ramp_time_ms: 2000
  timeout_s: 10.0

m2_fixture:
  velocity_min_mm_s: 10.0
  velocity_max_mm_s: 200.0
  velocity_nominal_mm_s: 100.0
  accel_mm_s2: 500.0
  timeout_s: 5.0

m3_backstop:
  steps_per_mm: 160
  soft_limit_min_mm: 0.0
  soft_limit_max_mm: 1000.0
  home_velocity_mm_s: 10.0
  max_velocity_mm_s: 100.0
  max_accel_mm_s2: 500.0
  pid_kp: 1.0
  pid_ki: 0.1
  pid_kd: 0.01
  position_tolerance_mm: 0.5
```

### Step 5: Verify Modbus Device IDs

Ensure ESP32 devices and N4D3E16 are configured correctly:

```yaml
# In system.yaml
devices:
  io_module:
    id: 1         # N4D3E16 slave ID
    name: "N4D3E16 I/O Module"

  esp32a:
    id: 2         # ESP32-A slave ID
    name: "Blade + Fixture Controller"

  esp32b:
    id: 3         # ESP32-B slave ID
    name: "Backstop Controller"
```

---

## Verification

### Step 1: Test Configuration

Run in dry-run mode (no hardware required):

```bash
cd /home/pi/pleat_saw
source venv/bin/activate
python app/main.py --dry-run
```

**Expected output:**
```
[INFO] Pleat Saw Controller starting...
[INFO] Configuration loaded
[INFO] DRY RUN MODE - No hardware communication
[INFO] Services started
```

Press Ctrl+C to exit.

### Step 2: Test Serial Ports

```bash
# Check RS-485 port exists
ls -l /dev/ttyUSB0

# Check permissions
groups | grep dialout

# Test with minicom (if installed)
minicom -D /dev/ttyUSB0 -b 9600
```

### Step 3: Test Modbus Communication

Install mbpoll for testing:

```bash
sudo apt-get install mbpoll
```

Test each device:

```bash
# Test N4D3E16 (should return input register)
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0xC0 -c 1 /dev/ttyUSB0

# Test ESP32-A (should return firmware version)
mbpoll -m rtu -b 9600 -P none -a 2 -t 3 -r 0x140 -c 1 /dev/ttyUSB0

# Test ESP32-B (should return status)
mbpoll -m rtu -b 9600 -P none -a 3 -t 3 -r 0x205 -c 1 /dev/ttyUSB0
```

**If devices respond:** RS-485 bus is working correctly.

**If no response:** Check wiring, termination resistors, device IDs, and baud rates.

### Step 4: Start the Service

```bash
sudo systemctl start pleat-saw
```

### Step 5: Check Service Status

```bash
# Check status
sudo systemctl status pleat-saw

# View logs
sudo journalctl -u pleat-saw -f
```

**Expected status:** Active (running)

**Expected logs:**
```
[INFO] Pleat Saw Controller starting...
[INFO] Configuration loaded from /home/pi/pleat_saw/config
[INFO] Modbus master initialized on /dev/ttyUSB0
[INFO] IO poller started
[INFO] Axis gateway initialized
[INFO] Nextion bridge started
[INFO] Supervisor started
[INFO] All services running
```

### Step 6: Test Basic Operation

With hardware connected and service running:

1. Check HMI displays status
2. Press start button on HMI or input panel
3. Observe state transitions in logs
4. Verify motors respond to commands

---

## Troubleshooting

### Service Won't Start

**Symptom:** `sudo systemctl start pleat-saw` fails

**Check:**

```bash
# View detailed error
sudo journalctl -u pleat-saw -n 50

# Test manually
cd /home/pi/pleat_saw
source venv/bin/activate
python app/main.py
```

**Common causes:**
- Missing Python packages: `pip install -r requirements.txt`
- Wrong serial port path: Check `config/system.yaml`
- Permission denied: Check `groups | grep dialout`
- Config file syntax error: Validate YAML files

### Serial Port Not Found

**Symptom:** Error: `/dev/ttyUSB0: No such file or directory`

**Check:**

```bash
# List all serial devices
ls -l /dev/tty*

# Check USB devices
lsusb

# Check kernel messages
dmesg | grep tty
```

**Fix:**
- Update port in `config/system.yaml`
- Check USB adapter is connected
- Try different USB port
- Check USB adapter driver loaded

### Permission Denied on Serial Port

**Symptom:** Error: `Permission denied: '/dev/ttyUSB0'`

**Fix:**

```bash
# Add user to dialout group
sudo usermod -a -G dialout pi

# Log out and back in
exit
ssh pi@raspberrypi.local

# Verify
groups | grep dialout

# If still fails, check udev rules
ls -l /etc/udev/rules.d/99-pleatsaw-serial.rules
```

### Modbus Communication Failures

**Symptom:** Timeout errors, no response from devices

**Check:**

```bash
# Test with mbpoll
mbpoll -m rtu -b 9600 -P none -a 1 -t 3 -r 0xC0 -c 1 /dev/ttyUSB0
```

**Common causes:**
- Wrong baud rate (ESP32 defaults to 9600)
- Wrong device ID (N4D3E16=1, ESP32-A=2, ESP32-B=3)
- Missing termination resistors (120Ω at both ends)
- Bus wiring incorrect (A to A, B to B)
- Ground not connected between devices
- Bus too long (max 1200m at 9600 baud)

### Python Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'pymodbus'`

**Fix:**

```bash
cd /home/pi/pleat_saw
source venv/bin/activate
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(pymodbus|pyserial|pyyaml)"
```

### HMI Not Responding

**Symptom:** Nextion displays nothing or shows "no serial data"

**Check:**

1. Verify Nextion port in `config/system.yaml`
2. Check baud rate matches HMI program (default 115200)
3. Test with screen: `screen /dev/ttyS0 115200`
4. Check GPIO UART is enabled: `sudo raspi-config`
5. Verify wiring: TX→RX, RX→TX, GND→GND

### High CPU Usage

**Symptom:** Service uses 100% CPU

**Causes:**
- Polling rates too high
- Modbus errors causing retries
- Tight loop in state machine

**Fix:**

```bash
# Check logs for errors
sudo journalctl -u pleat-saw -f

# Adjust polling rates in config/system.yaml
nano /home/pi/pleat_saw/config/system.yaml
```

Reduce update rates:

```yaml
nextion:
  update_rate: 5  # Reduce from 10 Hz

io_polling:
  rate_hz: 50     # Reduce from 100 Hz
```

---

## Updating

To update the application after installation:

### Method 1: Update from Git

If you're using git:

```bash
# Stop service
sudo systemctl stop pleat-saw

# Update code
cd /home/pi/pleat_saw
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl start pleat-saw
```

### Method 2: Manual File Copy

```bash
# Stop service
sudo systemctl stop pleat-saw

# Backup current installation
cp -r /home/pi/pleat_saw /home/pi/pleat_saw.backup.$(date +%Y%m%d)

# Copy new files (from USB or scp)
# Be careful not to overwrite config files!
cp -r /tmp/pleat_saw_new/app/* /home/pi/pleat_saw/app/

# Update dependencies if requirements.txt changed
cd /home/pi/pleat_saw
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl start pleat-saw

# Check status
sudo systemctl status pleat-saw
```

### Preserving Configuration During Updates

**Important:** Don't overwrite your config files!

```bash
# Backup config before updating
cp -r /home/pi/pleat_saw/config /home/pi/pleat_saw_config_backup

# After update, restore config
cp -r /home/pi/pleat_saw_config_backup/* /home/pi/pleat_saw/config/
```

---

## Uninstallation

To completely remove the Pleat Saw Controller:

```bash
# Stop and disable service
sudo systemctl stop pleat-saw
sudo systemctl disable pleat-saw

# Remove service file
sudo rm /etc/systemd/system/pleat-saw.service

# Reload systemd
sudo systemctl daemon-reload

# Remove application directory
sudo rm -rf /home/pi/pleat_saw

# Remove udev rules (optional)
sudo rm /etc/udev/rules.d/99-pleatsaw-serial.rules
sudo udevadm control --reload-rules

# Remove user from dialout group (optional)
sudo deluser pi dialout

# Remove installed packages (optional, may affect other software)
# sudo apt-get remove python3-pip python3-venv
```

---

## Next Steps

After successful installation:

1. **Read the commissioning checklist:** [commissioning_checklist.md](commissioning_checklist.md)
2. **Follow bring-up procedure:** Phase-by-phase hardware testing
3. **Tune motion parameters:** Adjust speeds, accelerations, PID gains
4. **Program Nextion HMI:** See [NEXTION_PROMPT.md](../NEXTION_PROMPT.md)
5. **Upload ESP32 firmware:** See firmware/ directory
6. **Test safety interlocks:** Verify emergency stop behavior
7. **Run production cycles:** Monitor and optimize

---

## Support

For technical support:

- Check logs: `sudo journalctl -u pleat-saw -f`
- Review documentation in `docs/` directory
- Check wiring: [docs/wiring_rs485.md](wiring_rs485.md)
- Test Modbus: [docs/n4d3e16_modbus.md](n4d3e16_modbus.md)
- Understand state machine: [docs/state_machine.md](state_machine.md)

Contact the controls engineering team for additional assistance.
