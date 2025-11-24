# Systemd Service Installation

This directory contains systemd service files for running the Pleat Saw controller as a system service on Raspberry Pi.

## Quick Installation (Recommended)

The easiest way to install the service is using the one-click installer:

```bash
# Copy pleat_saw directory to Raspberry Pi
scp -r pleat_saw pi@raspberrypi.local:/tmp/

# SSH to Raspberry Pi
ssh pi@raspberrypi.local

# Run installer
cd /tmp/pleat_saw
sudo bash pleat_saw_install.sh
```

The installer automatically handles:
- System dependencies installation
- Python virtual environment setup
- Package installation
- Serial port permissions
- Systemd service installation and enablement
- Directory structure creation
- Permission configuration

After installation completes, the service is installed and enabled but not yet started. Configure it first, then start it.

See [docs/installation_guide.md](../docs/installation_guide.md) for detailed installation instructions.

## Manual Installation

If you prefer manual installation or need to customize the process:

### 1. Copy repository to Raspberry Pi

```bash
# From your development machine
scp -r pleat_saw pi@raspberrypi.local:/home/pi/
```

### 2. Install Python dependencies

```bash
ssh pi@raspberrypi.local
cd /home/pi/pleat_saw/app
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### 3. Configure serial port permissions

The Pi user needs access to serial ports for RS-485 and Nextion communication.

```bash
# Add user to dialout group
sudo usermod -a -G dialout pi

# Create udev rules for consistent device naming
sudo nano /etc/udev/rules.d/99-pleat-saw.rules
```

Add the following content:

```
# RS-485 USB adapter (adjust idVendor/idProduct for your adapter)
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="ttyUSB_RS485", MODE="0666"

# Nextion HMI on Pi UART0
KERNEL=="ttyAMA0", SYMLINK+="ttyNEXTION", MODE="0666"
```

Reload udev rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4. Install systemd service

```bash
# Copy service file to systemd directory
sudo cp /home/pi/pleat_saw/systemd/pleat-saw.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable pleat-saw.service

# Start service now
sudo systemctl start pleat-saw.service
```

## Service Management

### Check service status

```bash
sudo systemctl status pleat-saw.service
```

### View logs

```bash
# View recent logs
sudo journalctl -u pleat-saw.service -n 100

# Follow logs in real-time
sudo journalctl -u pleat-saw.service -f

# View logs since boot
sudo journalctl -u pleat-saw.service -b
```

### Stop service

```bash
sudo systemctl stop pleat-saw.service
```

### Restart service

```bash
sudo systemctl restart pleat-saw.service
```

### Disable auto-start

```bash
sudo systemctl disable pleat-saw.service
```

## Troubleshooting

### Service fails to start

1. Check Python dependencies are installed:
   ```bash
   cd /home/pi/pleat_saw/app
   python3 -c "import pymodbus, pyserial, yaml"
   ```

2. Check serial port permissions:
   ```bash
   ls -l /dev/ttyUSB0 /dev/ttyAMA0
   groups pi  # Should include 'dialout'
   ```

3. Check configuration files exist:
   ```bash
   ls -l /home/pi/pleat_saw/config/*.yaml
   ```

4. Test application manually:
   ```bash
   cd /home/pi/pleat_saw/app
   python3 main.py --dry-run
   ```

### Serial port not found

If `/dev/ttyUSB0` doesn't exist:
- Check USB RS-485 adapter is connected: `lsusb`
- Check kernel loaded driver: `dmesg | grep tty`
- Try `/dev/ttyUSB1` or `/dev/ttyACM0` depending on your adapter

### Permission denied errors

```bash
# Re-add user to dialout group
sudo usermod -a -G dialout pi

# Log out and back in for group changes to take effect
# Or reboot: sudo reboot
```

## Configuration

Edit configuration files before starting the service:

```bash
nano /home/pi/pleat_saw/config/system.yaml
nano /home/pi/pleat_saw/config/io_map.yaml
nano /home/pi/pleat_saw/config/motion.yaml
```

After editing, restart the service:

```bash
sudo systemctl restart pleat-saw.service
```

## Updating

To update the application:

```bash
# Stop service
sudo systemctl stop pleat-saw.service

# Update code
cd /home/pi/pleat_saw
git pull  # If using git
# Or copy updated files via scp

# Restart service
sudo systemctl start pleat-saw.service
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop pleat-saw.service
sudo systemctl disable pleat-saw.service

# Remove service file
sudo rm /etc/systemd/system/pleat-saw.service

# Reload systemd
sudo systemctl daemon-reload
```
