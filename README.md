# Pleat Saw Controller v3.1

Industrial pleat-saw machine controller running on Raspberry Pi with RS-485 Modbus RTU communication to ESP32 servo controllers and N4D3E16 I/O module.

## What's New in v3.1

🎉 **Web-Based Monitoring Dashboard** - Access real-time system monitoring and manual control from any web browser!
- Real-time monitoring of all I/O, motors, and system state
- Manual control for commissioning and testing
- Command log for troubleshooting
- Access at: `http://<pi-ip>:5000`
- See [Web Monitoring Guide](docs/web_monitoring_guide.md)

✅ **Fixed Systemd Service** - Service now starts correctly without status=1/FAILURE error

## Architecture

- **Raspberry Pi Master** (Python 3.11): Runs supervisory control, state machine, safety interlocks, and HMI bridge
- **ESP32-A** (Arduino/PlatformIO): Controls blade motor (M1) and fixture motor (M2) via step/dir
- **ESP32-B** (Arduino/PlatformIO): Controls backstop motor (M3) with encoder PID loop
- **N4D3E16 I/O Module**: RS-485 I/O for sensors, buttons, and outputs
- **Nextion HMI**: Touchscreen interface using key=value protocol
- **Web Dashboard** (NEW): Browser-based monitoring and control interface

## Communication

All devices share a single **RS-485 bus** (9600 baud, 8N1, Modbus RTU):
- N4D3E16 I/O module: ID=1
- ESP32-A (blade + fixture): ID=2
- ESP32-B (backstop): ID=3

Nextion connects via dedicated serial port (115200 baud).

## Process Flow

1. **PRECHECK**: Verify IN16 (safety) is READY
2. **START_SPINDLE**: Start blade motor M1
3. **FEED_FWD**: Move fixture forward until Sensor3 (5.0s timeout)
4. **DWELL**: Wait 1.5s
5. **FEED_REV**: Move fixture reverse until Sensor2 (5.0s timeout)
6. **CLAMP**: Activate clamp output
7. **SAW_STOP**: Stop blade motor
8. **AIR_JET**: Pulse air jet (1.0s)
9. **COMPLETE**: Return to IDLE, ready for next cycle

## Safety

- **IN16 = Safety input** (active = READY)
- Category 0 stop if safety drops mid-cycle
- All motors stop immediately
- Outputs set to safe state (clamp OFF, air OFF)
- Manual RESET_ALARMS required after safety restored

## Units

- **Internal/Modbus**: millimeters × 1000 (fixed-point integers)
- **HMI customer display**: inches (3 decimal places)

## Directory Structure

```
pleat_saw/
├── app/                    # Python application
│   ├── main.py            # Entry point
│   ├── services/          # Background services
│   ├── utils/             # Utility modules
│   └── tests/             # Unit tests
├── firmware/              # ESP32 firmware
│   ├── esp32a_axis12/    # Blade + fixture controller
│   └── esp32b_backstop/  # Backstop PID controller
├── config/                # YAML configuration
│   ├── system.yaml       # RS-485, Nextion, safety
│   ├── io_map.yaml       # Input/output assignments
│   └── motion.yaml       # Motion parameters
├── systemd/               # Systemd service files
└── docs/                  # Documentation
```

## Installation

### Quick Install (Recommended)

The easiest way to install the Pleat Saw Controller on a Raspberry Pi is using the one-click installer:

```bash
# Transfer the pleat_saw directory to your Raspberry Pi
# Then run the installer:
cd pleat_saw
sudo bash pleat_saw_install.sh

# If you get "user pi does not exist" error, specify your username:
sudo bash pleat_saw_install.sh yourusername
```

**Note**: The installer auto-detects your username. If you have a custom username (not 'pi'), either specify it as an argument or the installer will prompt you.

See [INSTALLER_USAGE.md](INSTALLER_USAGE.md) for troubleshooting installer issues.

The installer will automatically:
- Install system dependencies (Python 3.11, pip, git)
- Create Python virtual environment
- Install Python packages
- Configure serial port permissions
- Install and enable systemd service
- Run unit tests
- Generate installation summary

After installation completes:
```bash
# Review installation summary
cat /home/pi/pleat_saw/INSTALLATION_INFO.txt

# Edit configuration files
nano /home/pi/pleat_saw/config/system.yaml
nano /home/pi/pleat_saw/config/io_map.yaml
nano /home/pi/pleat_saw/config/motion.yaml

# Start the service
sudo systemctl start pleat-saw

# Check status
sudo systemctl status pleat-saw

# View live logs
sudo journalctl -u pleat-saw -f
```

See [docs/installation_guide.md](docs/installation_guide.md) for detailed installation instructions.

## Web Monitoring Dashboard

After installation, access the web dashboard for commissioning and troubleshooting:

**URL:** `http://<raspberry-pi-ip>:5000`

**Example:** `http://192.168.1.100:5000`

**Features:**
- Real-time display of all inputs (sensors, buttons, safety)
- Real-time display of all outputs (solenoids, lamps)
- Motor status and position for all three axes
- Manual control buttons for testing individual components
- Cycle start/stop and alarm reset
- System statistics and communication counters
- Command console log

**Quick Test:**
```bash
# From the Raspberry Pi
curl http://localhost:5000

# From another computer on the network
# Open web browser to: http://<pi-ip>:5000
```

**Complete Guide:** See [docs/web_monitoring_guide.md](docs/web_monitoring_guide.md)

### Manual Installation

If you prefer manual installation or need to customize the process:

#### Python Application (Raspberry Pi)

```bash
cd pleat_saw/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/

# Run application
python main.py
```

#### ESP32 Firmware

```bash
cd pleat_saw/firmware/esp32a_axis12
pio run -t upload

cd ../esp32b_backstop
pio run -t upload
```

#### Systemd Services

See [systemd/README.md](systemd/README.md) for manual installation instructions.

## Configuration

All configurable parameters live in YAML files under `config/`:

- **system.yaml**: RS-485 ports, baud rates, device IDs, safety behavior
- **io_map.yaml**: Input/output bit assignments for N4D3E16
- **motion.yaml**: Motor speeds, accelerations, timeouts, PID gains

Edit these files to tune machine behavior without modifying code.

## Development

### Running in Dry-Run Mode

For testing without hardware:

```bash
python main.py --dry-run
```

This mocks Modbus communication and simulates sensor responses.

### Tests

```bash
cd app
pytest tests/ -v
```

Unit tests cover:
- Bit manipulation utilities
- Unit conversions (mm ↔ inches)
- State machine transitions
- Timeout handling
- Safety interlocks

## Wiring

See [docs/wiring_rs485.md](docs/wiring_rs485.md) for complete RS-485 bus wiring including:
- Termination resistors (120Ω at each end)
- Bias resistors (master side)
- Connector pinouts
- Cable specifications

## Commissioning

Follow [docs/commissioning_checklist.md](docs/commissioning_checklist.md) for step-by-step bring-up procedure.

## License

Proprietary - Internal use only

## Support

For technical support or questions, contact the controls engineering team.
