# Automated Pleat Pack Saw Controller
## Comprehensive System Documentation

**Project:** Industrial Pleat Pack Cutting System
**Client:** American Filter Manufacturing (AFM)
**Version:** 3.4.1
**Date:** November 2025
**Last Updated:** November 13, 2025 (Session 4 - Operator Page Position Fix)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Architecture](#hardware-architecture)
3. [Software Architecture](#software-architecture)
4. [ESP32 Firmware Modules](#esp32-firmware-modules)
5. [Raspberry Pi Controller](#raspberry-pi-controller)
6. [Web Interface](#web-interface)
7. [Configuration](#configuration)
8. [Operation](#operation)
9. [API Documentation](#api-documentation)
10. [Troubleshooting](#troubleshooting)
11. [Recent Changes](#recent-changes)
12. [Development](#development)

---

## System Overview

The Automated Pleat Pack Saw is a distributed control system that automates the cutting of air filter pleat packs to precise dimensions. The system uses a Raspberry Pi 4 as the master controller coordinating multiple ESP32 microcontrollers via Modbus RTU over RS-485.

### Key Features

- **Web-Based HMI**: Three web interfaces (operator, engineering, dashboard) accessible via browser
- **Precision Motor Control**: Calibrated stepper and servo motors for accurate positioning
- **Distributed Control**: Modular ESP32 slaves for motor control and I/O
- **Real-time Monitoring**: Flask + Socket.IO web interface for live system status
- **Safety Integration**: Light curtain and safety relay monitoring
- **Automated Sequencing**: State machine-based cycle control
- **Remote Access**: Web-based engineering dashboard for troubleshooting
- **Parameter Persistence**: Settings retained across page reloads

### System Specifications

- **Master Controller**: Raspberry Pi 4 Model B (4GB RAM)
- **Communication**: Dual RS-485 channels
  - Channel 0: 9600 baud for I/O module
  - Channel 1: 115200 baud for ESP32 motor controllers
- **Motor Types**:
  - M1 (Blade): Stepper motor @ 22,333 pulses/rev
  - M2 (Fixture): Servo stepper @ 750 steps/mm (with ×10 Modbus scaling)
  - M3 (Backstop): Servo with AS5600 encoder feedback on Raspberry Pi I2C (optional)
- **Web Interface**: Port 5000 (operator, engineering, dashboard)
- **Network**: Ethernet (192.168.68.109)
- **Operating System**: Raspberry Pi OS
- **I2C Bus**: /dev/i2c-1 (GPIO2/GPIO3) for AS5600 encoder

### Recent Updates (November 2025)

- **Operator Page Position Display**: Fixed "ACTUAL" display to show M3 encoder position (v3.4.1)
- **AS5600 Encoder Migration**: Moved from ESP32B I2C to Raspberry Pi I2C to eliminate RS-485 interference
- **Encoder Reader Service**: New Python service reads AS5600 via Pi I2C bus (/dev/i2c-1) with multi-turn tracking
- **Nextion HMI Removed**: Physical Nextion display no longer part of project, all references disabled
- **Three Web Interfaces**: Operator (touchscreen), Engineering (diagnostics), Dashboard (commissioning)
- **Motor Calibration**: M1 and M2 motors fully calibrated and tested
- **Parameter Persistence**: Dashboard settings now persist across page reloads
- **M2 Motion Control**: Multiple stop commands eliminate residual servo movement

---

## Hardware Architecture

### System Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                     Raspberry Pi 4 Master                        │
│                  IP: 192.168.68.109:5000                        │
│                                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  State Machine │  │ Web Monitor  │  │  Modbus Manager │    │
│  │   Supervisor   │  │ Flask+Socket │  │   (pymodbus)    │    │
│  └────────────────┘  └──────────────┘  └─────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Encoder Reader (AS5600 via I2C /dev/i2c-1)            │  │
│  │  GPIO2 (SDA) / GPIO3 (SCL) → AS5600 Magnetic Encoder   │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────┬──────────────────────┬─────────────────────────────┘
            │                      │
            │ RS-485 Ch0           │ RS-485 Ch1
            │ 9600 baud            │ 115200 baud
            │ /dev/ttyUSB0         │ /dev/ttyUSB1
            │                      │
            │                      │
    ┌───────┴─────┐       ┌────────┴────────────────┐
    │             │       │                         │
┌───┴───┐    ┌───┴───┐  ┌────┴────┐  ┌─────────┐
│Slave 1│    │Slave 1│  │ Slave 2 │  │ Slave 3 │
│I/O    │    │I/O    │  │ ESP32A  │  │ ESP32B  │
│Module │    │Module │  │ M1, M2  │  │   M3    │
└───────┘    └───────┘  └─────────┘  └─────────┘
   9600         9600       115200       115200
```

### Hardware Components

#### Master Controller

**Raspberry Pi 4 Model B**
- **CPU**: Broadcom BCM2711, Quad-core Cortex-A72 @ 1.5GHz
- **RAM**: 4GB LPDDR4
- **Storage**: 32GB microSD card
- **Interfaces**:
  - USB for RS-485 adapters (2 channels)
  - HDMI for web browser display (optional)
  - Ethernet for network access (192.168.68.109)
  - GPIO I2C Bus: /dev/i2c-1 (GPIO2=SDA, GPIO3=SCL) for AS5600 encoder

**RS-485 Adapters**
- Channel 0: I/O module communication (9600 baud) → /dev/ttyUSB0
- Channel 1: ESP32 motor controllers (115200 baud) → /dev/ttyUSB1

#### ESP32 Motor Controllers

**ESP32A - M1 Blade & M2 Fixture**
- **Chip**: ESP32-D0WD-V3
- **Modbus Slave ID**: 2
- **Baud Rate**: 115200
- **MAC Address**: 80:f3:da:4b:a3:ec
- **Firmware**: `/firmware/esp32a_axis12/src/main.cpp`
- **Functions**:
  - M1 Blade Motor: Step generation via MCPWM (22,333 pulses/rev)
  - M2 Fixture Motor: Step generation via MCPWM (750 steps/mm)
  - Calibrated for accurate RPM and velocity control

**M1 Blade Motor Configuration:**
```cpp
#define M1_PULSES_PER_REV   22333     // Calibrated: 1000 RPM → 1000 RPM actual
#define M1_DIR_CW           false     // Direction reversed
#define MAX_FREQ_HZ         375000.0  // Maximum step frequency
```

**M2 Fixture Motor Configuration:**
```cpp
#define M2_PULSES_PER_REV   5000      // Servo: 5000 pulses/rev
#define M2_DIR_FWD          false     // Direction reversed
#define M2_STEPS_PER_MM     750.0     // 5000 × 1.5 gear / 10mm leadscrew
// Modbus scaling: ×10 (not ×1000) to avoid 16-bit overflow
// Max velocity: 6553.5 mm/s (65535 / 10)
```

**ESP32B - M3 Backstop**
- **Chip**: ESP32-D0WD-V3
- **Modbus Slave ID**: 3
- **Baud Rate**: 115200
- **MAC Address**: 84:1f:e8:28:39:40
- **Firmware**: `/firmware/esp32b_backstop/src/main.cpp`
- **Functions**:
  - M3 Backstop Motor: Step generation via MCPWM
  - **Note**: AS5600 encoder moved to Raspberry Pi I2C (no longer on ESP32B)
  - ESP32B firmware retains encoder code but is not used in production

**AS5600 Encoder Auto-Detection (Legacy - Not Used):**
```cpp
// NOTE: This code is retained in ESP32B firmware but not used in production.
// AS5600 encoder now reads from Raspberry Pi I2C instead (see encoder_reader.py).

#define ENCODER_READ_INTERVAL_MS  100  // Poll every 100ms
#define I2C_TIMEOUT_MS            1    // Fast-fail timeout
bool encoder_detected;                  // Set at startup

// Startup detection prevents I2C errors from blocking Modbus
if (encoder_detected) {
    updateEncoderPosition();  // Only poll if hardware present
}
```

#### Motor Drivers (External)

**M1 - Blade Motor**
- **Type**: Stepper motor + external driver
- **Max Speed**: 1000 RPM (calibrated)
- **Control**: Step/Direction from ESP32A

**M2 - Fixture Motor**
- **Type**: Servo stepper + external driver
- **Max Speed**: 400 mm/s (approx)
- **Resolution**: 750 steps/mm
- **Control**: Step/Direction from ESP32A
- **Sensors**: S2 (home), S3 (forward limit)
- **Special**: Multiple stop commands (5× over 0.5s) to eliminate residual motion

**M3 - Backstop Motor**
- **Type**: Servo stepper with encoder feedback
- **Encoder**: AS5600 12-bit magnetic encoder on Raspberry Pi I2C
- **Resolution**: 0.00122 mm/count (4096 counts/rev, 5mm leadscrew)
- **Control**: Step/Direction from ESP32B
- **Position Feedback**: Python service reads AS5600 via Pi I2C (/dev/i2c-1)
- **Multi-turn Tracking**: Software accumulates encoder counts across full rotations

---

## Software Architecture

### Application Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Browser Interface                     │
│          (Operator / Engineering / Dashboard)                │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/WebSocket (Port 5000)
┌───────────────────────────┴─────────────────────────────────┐
│                     Flask Application                        │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │  Web Routes      │  │  Socket.IO     │  │  Templates  │ │
│  │  /               │  │  Real-time     │  │  operator   │ │
│  │  /engineering    │  │  Updates       │  │  engineering│ │
│  │  /dashboard      │  │  (10 Hz)       │  │  dashboard  │ │
│  │  /api/*          │  │                │  │             │ │
│  └──────────────────┘  └────────────────┘  └─────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │ Function Calls
┌───────────────────────────┴─────────────────────────────────┐
│                   Application Services                       │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │  Supervisor      │  │  AxisGateway   │  │  IOPoller   │ │
│  │  State Machine   │  │  Motor Control │  │  Inputs/    │ │
│  │  (50 Hz)         │  │  Abstraction   │  │  Outputs    │ │
│  │                  │  │                │  │  (50 Hz)    │ │
│  └──────────────────┘  └────────────────┘  └─────────────┘ │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  EncoderReader - AS5600 via Pi I2C (10 Hz polling) │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ Modbus RTU Commands
┌───────────────────────────┴─────────────────────────────────┐
│                   Hardware Abstraction                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ModbusMaster (pymodbus)                             │  │
│  │  Channel 0: /dev/ttyUSB0 @ 9600 baud (I/O)          │  │
│  │  Channel 1: /dev/ttyUSB1 @ 115200 baud (Motors)     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Software Components

#### 1. Supervisor (`app/services/supervisor.py`)

State machine controlling the overall system:

**States:**
- **INIT**: Initial state, system initialization
- **IDLE**: Ready, waiting for start command
- **PRECHECK**: Verify safety and home position
- **START_SPINDLE**: Start M1 blade motor
- **FEED_FWD**: M2 feeds forward to S3 sensor
- **DWELL**: Pause at cut position
- **FEED_REV**: M2 returns to S2 home sensor
- **CLAMP**: Activate clamp output
- **SAW_STOP**: Stop M1 blade motor
- **AIR_JET**: Pulse air jet to clear debris
- **COMPLETE**: Cycle finished, return to IDLE
- **ALARM**: Fault condition
- **ESTOP**: Emergency stop
- **PAUSE**: Light curtain blocked
- **MANUAL_HOME_M2**: Manual homing of M2 to S2 sensor (supervisor monitors sensor and stops)

**Key Features:**
- **Nextion HMI Disabled**: `_update_hmi()` checks for `self.hmi is None` and skips updates
- **M2 Residual Motion Fix**: Sends 5 stop commands over 0.5s in COMPLETE state
- **Parameter Methods**: `set_m1_rpm()`, `set_m2_fwd_velocity()`, `set_m2_rev_velocity()`, `manual_home_m2()`
- **Parameter Persistence**: Runtime parameters saved to `config/runtime_params.yaml` and loaded on startup
- **M2 Home Button**: Dashboard M2 section - homes at 30% auto reverse speed with sensor monitoring

#### 2. AxisGateway (`app/services/axis_gateway.py`)

Motor control abstraction layer:

**M1 Blade Control:**
```python
def m1_start(self, rpm: int, ramp_ms: int = 1000) -> bool
def m1_stop(self) -> bool
def m1_get_status(self) -> dict
```

**M2 Fixture Control:**
```python
def m2_set_velocity(self, vel_mm_s: float, accel_mm_s2: float) -> bool
    # Uses ×10 scaling: vel_modbus = int(round(vel_mm_s * 10.0))
def m2_feed_forward(self) -> bool
def m2_feed_reverse(self) -> bool
def m2_stop(self) -> bool
```

**M3 Backstop Control:**
```python
def m3_goto(self, position_mm: float) -> bool
def m3_home(self) -> bool
def m3_stop(self) -> bool
def m3_get_position(self) -> float
```

#### 3. WebMonitor (`app/services/web_monitor.py`)

Flask application providing web interfaces:

**Routes:**
- `/` → `operator.html` (touchscreen-optimized interface)
- `/engineering` → `engineering.html` (full diagnostics)
- `/dashboard` → `dashboard.html` (commissioning dashboard)
- `/api/status` → System status JSON
- `/api/command` → POST commands
- `/api/engineering_params` → GET current parameters (for persistence)
- `/api/diagnostics` → Hardware connection status

**Socket.IO Events:**
- `connect` → Client connection acknowledgment
- `update` → Real-time status broadcast (10 Hz)
- `command` → Execute command from client

**Nextion Disabled:**
- Connection checking disabled
- Statistics broadcasting disabled
- Status shows "Disabled" in diagnostics
- Log callback registration commented out

#### 4. IOPoller (`app/services/io_poller.py`)

Digital I/O management:

**Inputs:**
- `start`: Start button (IN1)
- `sensor2`: Home limit (IN2)
- `sensor3`: Forward limit (IN3)
- `light_curtain`: Safety interlock (IN15)
- `safety`: E-stop circuit (IN16)

**Outputs:**
- `clamp`: Clamp solenoid (CH1)
- `air_jet`: Air jet valve (CH2)
- `green_solid`: Tower light solid (CH3)
- `green_flash`: Tower light flash (CH4)

**Features:**
- Input override for diagnostics
- 50 Hz polling rate
- Change detection and logging

#### 5. EncoderReader (`app/services/encoder_reader.py`)

AS5600 magnetic encoder reader via Raspberry Pi I2C:

**Key Features:**
- **I2C Communication**: Reads AS5600 12-bit encoder via /dev/i2c-1 (smbus2 library)
- **Multi-turn Tracking**: Accumulates encoder counts across full rotations with wrap-around detection
- **Background Thread**: Continuous polling at 100ms intervals (10 Hz)
- **Auto-detection**: Checks for AS5600 at startup, logs if not found
- **Position Calculation**: Converts raw angle to linear position in mm

**Hardware Configuration:**
```python
AS5600_ADDR = 0x36           # I2C address
RAW_ANGLE_REG = 0x0C         # 12-bit raw angle register (0-4095)
COUNTS_PER_REV = 4096        # 12-bit resolution
MM_PER_REV = 5.0             # Lead screw: 5mm per revolution
MM_PER_COUNT = 0.00122       # ~0.00122 mm/count
```

**Multi-turn Tracking Algorithm:**
```python
def _update_position(self):
    raw = self._read_raw_angle()  # 0-4095

    # Calculate delta with wrap-around handling
    delta = raw - self.prev_raw_angle
    if delta > 2048:
        delta -= 4096  # Wrapped backward
    elif delta < -2048:
        delta += 4096  # Wrapped forward

    # Accumulate counts (multi-turn tracking)
    self.accum_counts += delta
    self.prev_raw_angle = raw

    # Convert to mm
    self.position_mm = float(self.accum_counts) * self.MM_PER_COUNT
```

**Public Methods:**
```python
def start(self) -> None
    # Start background reading thread

def stop(self) -> None
    # Stop background thread

def is_detected(self) -> bool
    # Returns True if AS5600 detected at startup

def get_position_mm(self) -> float
    # Returns current position in mm (thread-safe)

def reset_position(self) -> None
    # Reset accumulated counts to zero
```

**Integration with AxisGateway:**
- AxisGateway instantiates EncoderReader on startup
- `m3_get_position()` method reads from encoder_reader instead of ESP32B Modbus
- Complete electrical isolation from RS-485 interference

**Why Migration from ESP32B?**
- **RS-485 Interference**: ESP32B RS-485 differential signals corrupted I2C communication
- **Reliable Detection**: Pi I2C detection more stable at startup
- **No Modbus Dependency**: Encoder reading independent of ESP32B communication
- **Proven Solution**: Completely eliminated encoder detection issues

---

## ESP32 Firmware Modules

### ESP32A - M1 Blade & M2 Fixture

**File**: `/firmware/esp32a_axis12/src/main.cpp`

**M1 Blade Motor:**
- Uses MCPWM Unit 0, Timer 0, Operator A
- Step pin: GPIO controlled by MCPWM
- Direction pin: Direct GPIO control
- Frequency range: 1-375,000 Hz
- Calibrated: 1000 RPM commanded = 1000 RPM actual

**M2 Fixture Motor:**
- Uses MCPWM Unit 0, Timer 1, Operator A
- Step pin: GPIO controlled by MCPWM
- Direction pin: Direct GPIO control
- Resolution: 750 steps/mm
- Modbus velocity scaling: ×10 (prevents 16-bit overflow)

**Modbus Registers:**

**M1 Blade:**
- HREG 0: RPM (0-1000)
- HREG 1: Ramp time (ms)
- COIL 0: Enable (1=run, 0=stop)
- COIL 1: Direction (1=CW, 0=CCW)
- ISTS 0: Running status
- ISTS 1: Fault status
- ISTS 2: Ready status

**M2 Fixture:**
- HREG 10-11: Velocity (mm/s × 10, int32)
- HREG 12-13: Acceleration (mm/s², int32)
- COIL 10: Feed forward
- COIL 11: Feed reverse
- COIL 12: Stop
- ISTS 10: In motion
- ISTS 11: Fault

### ESP32B - M3 Backstop with Encoder

**File**: `/firmware/esp32b_backstop/src/main.cpp`

**M3 Motor:**
- Uses MCPWM for step generation
- PID control for closed-loop positioning (when encoder present)
- Open-loop mode when encoder not detected

**AS5600 Encoder:**
- I2C Address: 0x36
- Resolution: 12-bit (4096 counts/rev)
- Pulley: 15 teeth × 10mm pitch = 150mm circumference
- Linear resolution: 0.0366mm per count = 0.00144 in/count
- Auto-detection: Checks at startup, disables polling if not found

**Startup Detection Logic:**
```cpp
void setupEncoder() {
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(400000);
    Wire.setTimeout(I2C_TIMEOUT_MS);

    Wire.beginTransmission(AS5600_ADDR);
    Wire.write(AS5600_RAW_ANGLE_REG);
    uint8_t error = Wire.endTransmission(false);

    if (error == 0 && Wire.requestFrom(AS5600_ADDR, 2) == 2) {
        m3.encoder_detected = true;
    } else {
        m3.encoder_detected = false;
        // Modbus remains stable even without encoder
    }
}
```

**Modbus Registers:**

**M3 Position Control:**
- HREG 20-21: Target position (mm × 100, int32)
- HREG 22-23: Current position (mm × 100, int32)
- HREG 24: Velocity (mm/s)
- COIL 20: Go to position
- COIL 21: Home
- COIL 22: Stop
- ISTS 20: In motion
- ISTS 21: At target
- ISTS 22: Homed
- ISTS 23: Fault

**Encoder Registers (when detected):**
- IREG 0-1: Raw angle (int32)
- IREG 2-3: Accumulated counts (int32)
- IREG 4-5: Position (mm × 1000, int32)
- COIL 30: Reset position

---

## Raspberry Pi Controller

### Operating System

**OS**: Raspberry Pi OS (64-bit, Debian-based)
**Python**: 3.11.x
**User**: `ambf1`
**Password**: `1978`
**Location**: `/home/ambf1/pleat_saw`
**Service**: `pleat-saw.service` (systemd)

### Directory Structure

```
/home/ambf1/pleat_saw/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Application entry point
│   ├── services/
│   │   ├── __init__.py
│   │   ├── supervisor.py           # State machine
│   │   ├── axis_gateway.py         # Motor control
│   │   ├── encoder_reader.py       # AS5600 encoder via Pi I2C
│   │   ├── io_poller.py            # Digital I/O
│   │   ├── modbus_master.py        # Modbus RTU master
│   │   ├── nextion_bridge.py       # DISABLED (not used)
│   │   └── web_monitor.py          # Flask web server
│   ├── utils/
│   │   └── config.py               # Configuration loader
│   └── web/
│       ├── static/
│       │   ├── css/
│       │   │   └── dashboard.css
│       │   ├── js/
│       │   │   └── dashboard.js
│       │   └── images/
│       │       └── afm_logo.png
│       └── templates/
│           ├── operator.html       # Touchscreen interface
│           ├── engineering.html    # Full diagnostics
│           └── dashboard.html      # Commissioning
├── config/
│   ├── config.yaml                 # Main configuration
│   └── io_map.yaml                 # I/O definitions
├── firmware/
│   ├── esp32a_axis12/              # ESP32A firmware
│   └── esp32b_backstop/            # ESP32B firmware
├── logs/
│   └── pleat_saw.log
├── venv/                            # Python virtual environment
├── requirements.txt
├── COMPREHENSIVE_README.md          # This file
└── README.md                        # Quick start guide
```

### Python Dependencies

**Core Libraries** (`requirements.txt`):
```
Flask==2.3.2                 # Web framework
flask-socketio==5.3.4        # Real-time WebSocket
python-socketio==5.9.0       # Socket.IO server
pymodbus==3.3.2              # Modbus RTU/TCP library
pyserial==3.5                # Serial port communication
PyYAML==6.0                  # Configuration files
smbus2==0.4.2                # I2C communication for AS5600 encoder
```

### Systemd Service

**File**: `/etc/systemd/system/pleat-saw.service`

```ini
[Unit]
Description=Pleat Saw Controller
After=network.target

[Service]
Type=simple
User=ambf1
WorkingDirectory=/home/ambf1/pleat_saw
Environment="PATH=/home/ambf1/pleat_saw/venv/bin"
ExecStart=/home/ambf1/pleat_saw/venv/bin/python /home/ambf1/pleat_saw/app/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Commands**:
```bash
# Start service
sudo systemctl start pleat-saw

# Stop service
sudo systemctl stop pleat-saw

# Restart service
sudo systemctl restart pleat-saw

# View logs
sudo journalctl -u pleat-saw -f
```

### Main Application Entry

**File**: `/home/ambf1/pleat_saw/app/main.py`

**Key Changes:**
```python
# Nextion HMI disabled (line 157-178)
logger.info("Nextion HMI disabled - not part of project")
self.hmi = None

# HMI callbacks disabled (line 195-207)
# All self.hmi.register_callback() calls commented out

# HMI start disabled (line 260-262)
# self.hmi.start() commented out

# HMI stop disabled (line 285-288)
# self.hmi.stop() and disconnect() commented out
```

---

## Web Interface

### Overview

Three web pages accessible via browser on port **5000**:

1. **Operator Interface** - Touchscreen-optimized for production use
2. **Engineering Dashboard** - Full diagnostics (duplicate of dashboard)
3. **Dashboard** - Commissioning and detailed system view

All pages use the same Flask server and Socket.IO for real-time updates.

### 1. Operator Interface

**URL**: `http://192.168.68.109:5000/`
**File**: `/app/web/templates/operator.html`

**Design**: Touchscreen-optimized with large buttons and clear displays

**Layout**:
```
┌───────────────────────────────────────────────────────┐
│        Automated Pleat Pack Saw                       │
├───────────────────────────────────────────────────────┤
│  ┌─────────────┐          ┌─────────────┐            │
│  │   TARGET    │          │   ACTUAL    │            │
│  │             │          │             │            │
│  │   12.5      │          │   12.3      │  [READY]   │
│  └─────────────┘          └─────────────┘            │
│                                                       │
│              ┌────────────┐                           │
│              │            │              [OK]         │
│              │     GO     │                           │
│              │            │                           │
│              └────────────┘                           │
│                                                       │
│    ┌─────────┐                   ┌─────────┐         │
│    │   ENG   │                   │  home   │         │
│    └─────────┘                   └─────────┘         │
├───────────────────────────────────────────────────────┤
│              [AFM Logo]                               │
└───────────────────────────────────────────────────────┘
```

**Features**:
- **TARGET Display**: Click to open numeric keypad, set cut length (inches)
- **ACTUAL Display**: Real-time position from motors/encoder
- **GO Button**: Start cutting cycle (350×200px, green gradient)
- **OK Button**: Alternative start button (120×80px, gray)
- **Status Message**: Current state (READY, RUNNING, ERROR, etc.) with color coding
- **ENG Button**: Navigate to dashboard page (not engineering)
- **home Button**: Send homing command to backstop
- **Numeric Keypad**: Overlay with 0-9, decimal, clear (⌫), enter (ENT)

**Color Scheme**:
- Background: Gold/yellow gradient (#c9b037 → #9c8929)
- Displays: Bright yellow (#ffed4e) with black text
- GO Button: Green gradient (#4ade80 → #22c55e)
- Black borders and text for high contrast
- Status colors: Green (ready), Red (error), Blue (running), Amber (other)

**JavaScript Functionality**:
```javascript
// Socket.IO connection for real-time updates
socket.on('update', (data) => {
    actualDisplay.textContent = data.motors.axis1.position;
    targetDisplay.textContent = data.config.target;
    statusMessage.textContent = data.state;
});

// Command API
function sendCommand(command, params) {
    fetch('/api/command', {
        method: 'POST',
        body: JSON.stringify({ command, ...params })
    });
}

// ENG button navigation (line 395)
engButton.addEventListener('click', () => {
    window.location.href = '/dashboard';  // Goes to dashboard, not engineering
});
```

**Touch Optimization**:
- No hover states
- Large tap targets (minimum 80×80px)
- `touch-action: manipulation`
- `-webkit-tap-highlight-color: transparent`
- `user-select: none` on interactive elements

### 2. Engineering Dashboard

**URL**: `http://192.168.68.109:5000/engineering`
**File**: `/app/web/templates/engineering.html`

**Note**: Currently identical to dashboard page. Reserved for future use.

### 3. Dashboard (Commissioning)

**URL**: `http://192.168.68.109:5000/dashboard`
**File**: `/app/web/templates/dashboard.html`

**Purpose**: Full diagnostic and commissioning interface

**Sections**:

1. **System Status**
   - State (IDLE, RUNNING, etc.)
   - Safety status (READY/NOT_READY)
   - Light curtain status (OK/BLOCKED)
   - System paused indicator
   - Current alarm
   - Cycle count
   - Uptime

2. **Hardware Connection Status** (diagnostics panel)
   - Modbus RS-485 connection status
   - Nextion HMI: Shows "Disabled" (not part of project)
   - Init errors display
   - Troubleshooting hints

3. **Digital Inputs** (with override controls)
   - Start button (IN1)
   - Sensor 2 / Home (IN2)
   - Sensor 3 / Forward (IN3)
   - Light curtain (IN15)
   - Safety (IN16)
   - **Force ON/OFF buttons** for diagnostic testing
   - **Clear All Overrides** button
   - Warning: "Input overrides are for diagnostic purposes only"

4. **Digital Outputs** (with manual toggle)
   - Clamp (CH1)
   - Air jet (CH2)
   - Green solid light (CH3)
   - Green flash light (CH4)
   - Toggle buttons for each output

5. **Motor Controls**

   **M1 - Blade Motor:**
   - Running, Fault, Ready indicators
   - RPM input (5-3500)
   - Start / Stop buttons
   - Pulses input (1-200,000) with Jog Pulses button
   - **Auto Cycle RPM**: Separate setting for automatic cycles
   - Apply to Auto button (stores RPM for cycles)

   **M2 - Fixture Motor:**
   - In Motion, At S2, At S3, Fault indicators
   - Velocity input (10-400 mm/s)
   - Feed FWD (continuous), Feed REV (continuous), Stop buttons
   - Pulses input with Jog + / Jog - buttons
   - Timeout FWD and Timeout REV inputs
   - **Auto Cycle FWD Vel**: Setting for automatic forward velocity
   - **Auto Cycle REV Vel**: Setting for automatic reverse velocity
   - Apply FWD / Apply REV buttons

   **M3 - Backstop Motor:**
   - Position display (mm)
   - In Motion, At Target, Homed, Fault indicators
   - Target position input (0-1000 mm)
   - Go To, Home, Stop buttons

6. **Cycle Control**
   - Start Cycle button (green)
   - Emergency Stop button (red)
   - Reset Alarms button (amber)

7. **System Statistics**
   - Modbus reads, writes, errors
   - I/O polls, changes
   - Total alarms

8. **Nextion Communications** (HIDDEN - commented out)
   - Section removed as Nextion no longer used

9. **Command Log**
   - Real-time event log
   - Shows user actions and system events

**Key Styling**:
- Dark theme: Background #1a202c, panels #2d3748
- Color-coded indicators: Green (on/ok), Red (off/fault), Amber (warning)
- Monospace font for numeric displays
- Responsive grid layout
- Scrollable console log

**Features**:
- **Real-time Updates**: Socket.IO streaming at 10 Hz
- **Parameter Persistence**: Values fetched from `/api/engineering_params` on load
- **Input Overrides**: Force sensor states for testing (bypasses hardware)
- **Manual Motor Control**: Individual axis testing and calibration
- **Return Button**: "← Return to Operator View" in header (goes to `/`)

**JavaScript Functions**:
```javascript
// Fetch parameters on page load (line 454-485)
function fetchEngineeringParams() {
    fetch('/api/engineering_params')
        .then(response => response.json())
        .then(data => {
            document.getElementById('m1-auto-rpm').value = data.m1_rpm;
            document.getElementById('m2-auto-vel-fwd').value = data.m2_vel_fwd_mm_s;
            document.getElementById('m2-auto-vel-rev').value = data.m2_vel_rev_mm_s;
            // ... populate all fields
        });
}

// Update M1 auto RPM
function updateM1AutoRpm() {
    const rpm = parseInt(document.getElementById('m1-auto-rpm').value);
    sendCommand('set_m1_rpm', { rpm: rpm });
}

// Toggle input override
function toggleInputOverride(name) {
    // Cycles: undefined → true → false → undefined
    // Sends to /api/command with 'set_input_override'
}
```

### Web Interface Features (All Pages)

**Socket.IO Real-Time Updates:**
- **Frequency**: 10 Hz (100ms interval)
- **Event**: `update`
- **Data**: System status, motors, inputs, outputs
- **Auto-reconnect**: Built-in reconnection logic

**REST API Endpoints:**

```
GET /                          → operator.html
GET /engineering               → engineering.html
GET /dashboard                 → dashboard.html
GET /api/status                → System status JSON
GET /api/engineering_params    → Current parameter values
GET /api/diagnostics           → Hardware connection status
POST /api/command              → Execute command
```

**Command API Examples:**
```javascript
// Start cycle
fetch('/api/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command: 'start_cycle' })
});

// Set M1 RPM
fetch('/api/command', {
    method: 'POST',
    body: JSON.stringify({
        command: 'set_m1_rpm',
        params: { rpm: 700 }
    })
});

// Set target length
fetch('/api/command', {
    method: 'POST',
    body: JSON.stringify({
        command: 'set_target',
        target: 12.5
    })
});
```

---

## Configuration

### Configuration Files

**Main Config**: `/home/ambf1/pleat_saw/config/config.yaml`

```yaml
system:
  rs485_io:
    port: /dev/ttyUSB0
    baud: 9600
    timeout_s: 0.5
    retry_count: 3
    ids:
      io: 1

  rs485_motors:
    port: /dev/ttyUSB1
    baud: 115200
    timeout_s: 0.5
    retry_count: 3
    ids:
      esp32a: 2
      esp32b: 3

  services:
    io_poller:
      enabled: true
      poll_rate_hz: 50.0

    axis_gateway:
      enabled: true
      heartbeat_check_s: 2.0

    supervisor:
      enabled: true
      loop_rate_hz: 50.0

    nextion_bridge:
      enabled: false  # DISABLED

    web_monitor:
      enabled: true
      host: 0.0.0.0
      port: 5000
      update_rate_hz: 10.0

motion:
  m1_blade:
    rpm_min: 5
    rpm_max: 1000
    rpm_default: 700
    ramp_ms: 1000
    timeout_start_s: 10.0

  m2_fixture:
    speed_mm_s_min: 10.0
    speed_mm_s_max: 400.0
    default_speed_mm_s: 120.0
    default_accel_mm_s2: 500.0
    timeout_fwd_s: 20.0
    timeout_rev_s: 20.0

  m3_backstop:
    max_position_mm: 1000.0
    home_velocity_mm_s: 50.0
    goto_velocity_mm_s: 200.0

  cycle:
    dwell_after_s3_s: 0.5
    air_jet_s: 1.0
    saw_spindown_s: 3.0
    clamp_confirm_s: 0.1
```

**I/O Map**: `/home/ambf1/pleat_saw/config/io_map.yaml`

```yaml
inputs:
  start:
    address: 0
    description: Start button (IN1)

  sensor2:
    address: 1
    description: Home limit sensor (IN2)

  sensor3:
    address: 2
    description: Forward limit sensor (IN3)

  light_curtain:
    address: 15
    description: Light curtain OK signal (IN15)

  safety:
    address: 16
    description: Safety relay OK signal (IN16)

outputs:
  clamp:
    address: 0
    description: Clamp solenoid (CH1)

  air_jet:
    address: 1
    description: Air jet valve (CH2)

  green_solid:
    address: 2
    description: Tower light green solid (CH3)

  green_flash:
    address: 3
    description: Tower light green flash (CH4)
```

### Parameter Adjustment

**Via Operator Interface:**
1. Tap "TARGET" display
2. Numeric keypad appears
3. Enter cut length (inches)
4. Tap "ENT"
5. Value stored and cycle ready

**Via Dashboard:**

**M1 Blade RPM:**
1. Navigate to dashboard: `http://192.168.68.109:5000/dashboard`
2. M1 panel → "Auto Cycle RPM" input
3. Enter RPM (5-1000)
4. Click "Apply to Auto"
5. Value persists across reloads

**M2 Fixture Velocities:**
1. Dashboard → M2 panel
2. "Auto Cycle FWD Vel" input → Enter mm/s (10-400)
3. Click "Apply FWD"
4. "Auto Cycle REV Vel" input → Enter mm/s (10-400)
5. Click "Apply REV"
6. Values persist across reloads

**M2 Timeouts:**
1. Dashboard → M2 panel
2. "Timeout FWD (s)" input → Enter seconds (1-60)
3. "Timeout REV (s)" input → Enter seconds (1-60)
4. Values automatically saved

**Via Config File** (requires service restart):
```bash
ssh ambf1@192.168.68.109
sudo nano ~/pleat_saw/config/config.yaml
# Edit values
sudo systemctl restart pleat-saw
```

---

## Operation

### Normal Operation

1. **Power On**:
   - Turn on 24V power supply for motors and I/O
   - Pi boots automatically (30-60 seconds)
   - Service starts: `pleat-saw.service`
   - Web interface available at `http://192.168.68.109:5000/`

2. **Access Operator Interface**:
   - Open browser to `http://192.168.68.109:5000/`
   - Touchscreen or mouse/keyboard
   - System initializes to IDLE state

3. **Set Target Length**:
   - Tap "TARGET" display
   - Numeric keypad appears
   - Enter cut length (e.g., "12.5" inches)
   - Tap "ENT"
   - Status changes to "READY"

4. **Run Cutting Cycle**:
   - Ensure material loaded
   - Ensure light curtain clear
   - Safety relay active
   - Press "GO" or "OK" button
   - Status changes to "RUNNING"
   - Cycle sequence:
     1. Precheck (safety, home position)
     2. Start blade motor
     3. Feed forward to S3 sensor
     4. Dwell (0.5s)
     5. Feed reverse to S2 sensor
     6. Activate clamp
     7. Stop blade motor (3s spindown)
     8. Air jet (1s)
     9. Release clamp
     10. Return to READY

5. **Monitor Progress**:
   - "ACTUAL" display shows position
   - Status message shows current step
   - Status colors indicate state
   - Cycle counter increments

6. **Repeat Cycles**:
   - System returns to "READY"
   - Press "GO" for next cycle
   - Target persists between cycles

### Engineering Mode (Dashboard)

1. **Navigate from Operator**:
   - Tap "ENG" button on operator page
   - Opens dashboard at `/dashboard`

2. **Diagnostic Features**:
   - View all sensor states (live updates)
   - Manual motor control (test each axis)
   - Force sensor inputs (bypass hardware)
   - View Modbus statistics
   - Monitor command log
   - Check hardware connections

3. **Manual Motor Testing**:

   **M1 Blade:**
   - Set RPM (5-1000)
   - Click "Start" (motor runs continuously)
   - Click "Stop" (motor stops)
   - Jog pulses (step motor specified pulses)

   **M2 Fixture:**
   - Set velocity (10-400 mm/s)
   - Click "Feed FWD" (continuous forward)
   - Click "Feed REV" (continuous reverse)
   - Click "Stop" (immediate stop)
   - Jog + / Jog - (step specified pulses)

   **M3 Backstop:**
   - Set target position (0-1000 mm)
   - Click "Go To" (move to position)
   - Click "Home" (return to home)
   - Click "Stop" (immediate stop)

4. **Input Override Testing**:
   - Click "Force ON" button next to sensor
   - Sensor state forced (overrides hardware)
   - Use for cycle testing without physical sensors
   - Click "Clear All Overrides" to restore normal operation
   - **Warning**: Only for diagnostic purposes!

5. **Return to Operator**:
   - Click "← Return to Operator View" in header
   - Returns to operator interface

### Emergency Stop

**Physical E-Stop:**
- Press e-stop button on machine
- Cuts power to motors via safety relay
- Pi remains running
- Web interface remains accessible
- Reset e-stop to restore power
- System transitions to ESTOP state
- Click "Reset Alarms" on dashboard to recover

**Software Stop:**
- Dashboard → "Emergency Stop" button
- Sends stop commands to all motors via Modbus
- Transitions to ALARM state
- Motors coast to stop
- Click "Reset Alarms" to recover

### Troubleshooting During Operation

**"ALARM" State:**
- Check status message for alarm code
- Common alarms:
  - `PRECHECK_SAFETY_NOT_READY`: E-stop or safety relay not active
  - `PRECHECK_M2_NOT_HOME`: Fixture not at home position (S2)
  - `TIMEOUT_FWD`: Forward feed exceeded timeout (20s default)
  - `TIMEOUT_REV`: Reverse feed exceeded timeout (20s default)
  - `TIMEOUT_BLADE_START`: Blade motor did not start (10s)
- Solution:
  - Resolve underlying issue
  - Dashboard → "Reset Alarms"
  - System returns to IDLE

**"PAUSE" State:**
- Light curtain blocked
- Motors stopped, outputs preserved
- Restore light curtain (clear obstruction)
- System automatically resumes to previous state

**Incorrect Motor Movement:**
- Dashboard → Manual motor control
- Test each motor individually
- Check direction (should match labeled arrows)
- Check speed (matches input value)
- If incorrect:
  - M1: Check `M1_DIR_CW` setting in ESP32A firmware
  - M2: Check `M2_DIR_FWD` setting in ESP32A firmware
  - M3: Check direction setting in ESP32B firmware

**No Encoder Reading (M3):**
- AS5600 encoder connected to Raspberry Pi I2C (/dev/i2c-1)
- EncoderReader service auto-detects AS5600 at startup
- If not detected, check logs: `sudo journalctl -u pleat-saw | grep AS5600`
- Common issues:
  - Wrong I2C wiring (should be GPIO2=SDA, GPIO3=SCL on Pi)
  - Magnet not in range of AS5600 sensor (0.5-3mm distance)
  - I2C bus not enabled on Pi (`sudo raspi-config` → Interface Options → I2C)
  - AS5600 power supply issue (should be 3.3V from Pi)
- Test I2C manually: `i2cdetect -y 1` (should show device at 0x36)
- System operates normally even without encoder (open-loop mode)

---

## API Documentation

### REST Endpoints

#### GET /api/status

Returns current system status.

**Response**:
```json
{
  "system": {
    "state": "IDLE",
    "safety": "READY",
    "light_curtain": "OK",
    "paused": "RUNNING",
    "alarm": null,
    "cycle_count": 42,
    "uptime": 3600.5,
    "timestamp": 1699900000.0
  },
  "inputs": {
    "inputs": {
      "start": false,
      "sensor2": true,
      "sensor3": false,
      "light_curtain": true,
      "safety": true
    },
    "timestamp": 1699900000.0
  },
  "outputs": {
    "outputs": {
      "clamp": false,
      "air_jet": false,
      "green_solid": true,
      "green_flash": false
    },
    "timestamp": 1699900000.0
  },
  "motors": {
    "m1_blade": {
      "running": false,
      "fault": false,
      "ready": true,
      "rpm": 0
    },
    "m2_fixture": {
      "in_motion": false,
      "at_s2": true,
      "at_s3": false,
      "fault": false
    },
    "m3_backstop": {
      "position_mm": 123.4,
      "in_motion": false,
      "at_target": true,
      "homed": true,
      "fault": false
    },
    "timestamp": 1699900000.0
  }
}
```

#### GET /api/engineering_params

Returns current engineering parameters (for dashboard persistence).

**Response**:
```json
{
  "m1_rpm": 700,
  "m2_vel_fwd_mm_s": 120.0,
  "m2_vel_rev_mm_s": 120.0,
  "m2_fwd_timeout": 20.0,
  "m2_rev_timeout": 20.0
}
```

#### GET /api/diagnostics

Returns hardware connection status and initialization errors.

**Response**:
```json
{
  "init_errors": [],
  "connections": {
    "modbus": {
      "connected": true,
      "status": "Connected",
      "description": "RS-485 Modbus RTU (I/O and Motors)",
      "device": "/dev/ttyUSB1"
    },
    "nextion": {
      "connected": false,
      "status": "Disabled",
      "description": "Nextion HMI Display (not part of project)"
    }
  },
  "services_status": {
    "io_poller": true,
    "axis_gateway": true,
    "supervisor": true,
    "web_monitor": true
  },
  "timestamp": 1699900000.0
}
```

#### POST /api/command

Execute command.

**Request Body**:
```json
{
  "command": "start_cycle"
}
```

**Commands**:

**Cycle Control:**
- `start_cycle`: Start cutting cycle
- `stop_cycle`: Emergency stop all motors
- `reset_alarms`: Clear alarm state

**Motor Control:**
- `m1_start`: Start blade motor
  ```json
  { "command": "m1_start", "params": { "rpm": 700 } }
  ```
- `m1_stop`: Stop blade motor

- `m2_jog_forward`: Jog fixture forward
  ```json
  { "command": "m2_jog_forward", "params": { "vel": 50 } }
  ```
- `m2_jog_reverse`: Jog fixture reverse
- `m2_stop`: Stop fixture motor

- `m3_goto`: Move backstop to position
  ```json
  { "command": "m3_goto", "params": { "position": 123.4 } }
  ```
- `m3_home`: Home backstop motor
- `m3_stop`: Stop backstop motor

**Parameter Setting:**
- `set_m1_rpm`: Set blade RPM for auto cycles
  ```json
  { "command": "set_m1_rpm", "params": { "rpm": 700 } }
  ```
- `set_m2_fwd_velocity`: Set fixture forward velocity
  ```json
  { "command": "set_m2_fwd_velocity", "params": { "vel": 120 } }
  ```
- `set_m2_rev_velocity`: Set fixture reverse velocity
- `set_target`: Set cut length
  ```json
  { "command": "set_target", "target": 12.5 }
  ```

**I/O Control:**
- `set_output`: Set digital output
  ```json
  { "command": "set_output", "params": { "name": "clamp", "state": true } }
  ```
- `set_input_override`: Force input state (diagnostic)
  ```json
  { "command": "set_input_override", "params": { "name": "sensor2", "state": true } }
  ```
  - `state: null` to disable override
- `clear_input_overrides`: Clear all input overrides

**Response**:
```json
{
  "success": true,
  "message": "Cycle started"
}
```

### Socket.IO Events

#### Event: `connect`

Client connects to server.

**Server Response**: Connection acknowledgment

#### Event: `update`

Real-time system status (emitted by server every 100ms).

**Data**: Same structure as `/api/status`

**Client Example**:
```javascript
const socket = io();

socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('update', (data) => {
    console.log('System state:', data.system.state);
    console.log('M1 running:', data.motors.m1_blade.running);
    console.log('M2 position:', data.motors.m2_fixture.at_s2);

    // Update UI elements
    document.getElementById('actual-display').textContent =
        data.motors.m3_backstop.position_mm.toFixed(1);
});
```

---

## Troubleshooting

### Common Issues

#### 1. Cannot Access Web Interface

**Symptoms**:
- Browser shows "Connection refused" or timeout
- Cannot reach `http://192.168.68.109:5000/`

**Checks**:
```bash
# SSH to Pi
ssh ambf1@192.168.68.109

# Check service status
sudo systemctl status pleat-saw

# Check port
sudo netstat -tulpn | grep 5000

# Test locally
curl http://localhost:5000/
```

**Solutions**:
- Restart service: `sudo systemctl restart pleat-saw`
- Check logs: `sudo journalctl -u pleat-saw -f`
- Verify network: `ping 192.168.68.109`
- Check firewall: `sudo ufw status`

#### 2. Modbus Communication Errors

**Symptoms**:
- Dashboard shows "Modbus: Disconnected"
- Motor commands have no effect
- Sensor readings show "ERROR"
- Logs show "No Response received from the remote slave"

**Checks**:
```bash
# Verify USB adapter
ls -la /dev/ttyUSB*
# Should show: /dev/ttyUSB0 and /dev/ttyUSB1

# Check permissions
groups ambf1
# Should include: dialout

# View recent errors
sudo journalctl -u pleat-saw -n 50 | grep -i modbus
```

**Solutions**:
- Reconnect USB RS-485 adapters
- Add user to dialout: `sudo usermod -a -G dialout ambf1`
- Check RS-485 wiring (A, B, GND)
- Verify ESP32s powered and programmed
- Check baud rate matches (9600 for I/O, 115200 for motors)
- Verify terminating resistors (120Ω at each end)

#### 3. Motor Not Moving / Incorrect Direction

**Symptoms**:
- Motor command sent but no movement
- Motor moves opposite direction
- Speed much too fast or slow

**M1 Blade Checks**:
- Dashboard → M1 panel → Verify "Ready" indicator green
- Check external driver power LED
- Verify step/direction wiring to driver
- Test with manual control: Dashboard → M1 Start

**M1 Calibration**:
- Current setting: 22,333 pulses/rev
- Test: Set 1000 RPM, measure actual RPM with tachometer
- Should be 1:1 ratio (1000 commanded = 1000 actual)
- If incorrect, adjust `M1_PULSES_PER_REV` in ESP32A firmware

**M2 Fixture Checks**:
- Verify "At S2" indicator (should be green at home)
- Check S2 sensor wiring and LED
- Test direction: Dashboard → M2 "Feed FWD" → should move away from S2
- Test speed: Set 100 mm/s, measure actual speed
- Should move approximately 100 mm in 1 second

**M2 Calibration**:
- Current setting: 750 steps/mm (5000 pulses/rev, 1.5:1 gear, 10mm leadscrew)
- Modbus scaling: ×10 (not ×1000)
- If speed incorrect, verify `M2_STEPS_PER_MM` calculation
- If overflow errors, verify Modbus scaling is ×10

**M3 Backstop Checks**:
- Dashboard → M3 panel → Check "Position" reading
- If encoder not detected, will show "Encoder: Not detected" in logs
- System operates normally without encoder (open-loop mode)
- Test with manual control: Dashboard → M3 "Go To" → Enter position → Click

**Direction Fixes**:
- M1: Edit `/firmware/esp32a_axis12/src/main.cpp` → Change `M1_DIR_CW`
- M2: Edit `/firmware/esp32a_axis12/src/main.cpp` → Change `M2_DIR_FWD`
- M3: Edit `/firmware/esp32b_backstop/src/main.cpp` → Change direction constant
- Reflash ESP32 via USB

#### 4. Cycle Stuck in State / Timeout Alarms

**Symptoms**:
- Status shows "TIMEOUT_FWD" or "TIMEOUT_REV"
- Cycle hangs in "FEED_FWD" or "FEED_REV"
- Never reaches S2 or S3 sensor

**Checks**:
- Dashboard → Digital Inputs → Verify sensor states
- S2 sensor should be ON when M2 at home position
- S3 sensor should be ON when M2 at forward position
- Check sensor wiring and LED indicators
- Verify sensor mounting and trigger distance

**Timeout Adjustment**:
- Dashboard → M2 panel → "Timeout FWD (s)" → Increase if needed (default 20s)
- Dashboard → M2 panel → "Timeout REV (s)" → Increase if needed (default 20s)
- Values saved automatically

**Sensor Override Testing**:
- Dashboard → Digital Inputs → Click "Force ON" next to sensor
- Run cycle to test if issue is sensor or mechanical
- **Remember to clear overrides before production use!**

**Solutions**:
- Slow down M2 velocity: Dashboard → M2 Auto Cycle Vel → Lower value
- Increase timeouts to allow more travel time
- Check mechanical binding or obstructions
- Verify sensor alignment and functionality
- Clean sensor lenses (optical sensors)

#### 5. M2 Residual Movement After Cycle

**Symptoms**:
- M2 motor continues moving slightly after cycle complete
- "Creep" or "drift" after stop command

**Explanation**:
- Servo motor has momentum and internal control loop
- Single stop command may not fully halt motion

**Solution (Already Implemented)**:
- Supervisor sends 5 stop commands over 0.5 seconds in COMPLETE state
- File: `/app/services/supervisor.py` lines 522-527
- If still present, increase stop command count or duration

**Manual Testing**:
- Dashboard → M2 panel → Click "Stop" multiple times rapidly
- Observe if motor stops more quickly with multiple commands

#### 6. Dashboard Parameters Reset on Page Reload

**Symptoms**:
- Set M1 RPM, reload page, value returns to default
- M2 velocities reset after browser refresh

**Solution (Already Implemented)**:
- Dashboard now fetches parameters from `/api/engineering_params` on load
- File: `/app/web/static/js/dashboard.js` lines 454-485
- Values stored in Supervisor instance and persisted
- If still resetting, verify JavaScript console for fetch errors

**Verification**:
1. Dashboard → M1 Auto RPM → Enter 800 → Apply
2. Reload page (Ctrl+R)
3. Verify M1 Auto RPM shows 800 (not default 700)
4. If shows 700, check browser console for errors

#### 7. Nextion References Still Present

**Symptoms**:
- Logs mention "Nextion" initialization
- Dashboard shows Nextion statistics
- Error connecting to Nextion serial port

**Solution (Already Implemented)**:
- Nextion disabled in `main.py` line 158
- HMI set to `None`, callbacks commented out
- WebMonitor shows "Disabled" status
- Dashboard Nextion section commented out

**Verification**:
```bash
sudo journalctl -u pleat-saw | grep -i nextion
# Should show: "Nextion HMI disabled - not part of project"
# Should NOT show: "Initializing Nextion bridge" or "Nextion connected"
```

### Diagnostic Commands

**View Service Logs**:
```bash
# Real-time log streaming
sudo journalctl -u pleat-saw -f

# Last 100 lines
sudo journalctl -u pleat-saw -n 100

# Since specific time
sudo journalctl -u pleat-saw --since "10 minutes ago"

# Filter by keyword
sudo journalctl -u pleat-saw | grep -i ERROR
```

**Test Modbus Communication**:
```bash
# Install pymodbus-repl if not present
pip install pymodbus-repl

# Connect to channel 1 (motors)
pymodbus-repl -c serial -m rtu -b 115200 -p /dev/ttyUSB1

# Read ESP32A status (slave 2)
> client.read_input_registers address=0 count=4 slave=2

# Read ESP32B status (slave 3)
> client.read_input_registers address=0 count=4 slave=3
```

**Check USB Devices**:
```bash
# List USB serial devices
ls -la /dev/ttyUSB*

# Check device info
udevadm info /dev/ttyUSB0
udevadm info /dev/ttyUSB1

# Monitor USB events
sudo dmesg -w
# Unplug/replug USB adapter to see messages
```

**Network Diagnostics**:
```bash
# Test connectivity from Mac
ping 192.168.68.109

# Test web server
curl http://192.168.68.109:5000/

# Check open ports
nmap 192.168.68.109
```

---

## Recent Changes

### November 13, 2025 - Session 4 Summary: Operator Page Position Display Fix

#### Problem: Encoder Position Not Displaying on Operator Page

**Issue**: After migrating the AS5600 encoder to Raspberry Pi I2C (Session 3), the M3 backstop position was correctly displaying in the engineering dashboard M3 window, but the "ACTUAL" display on the operator page remained at "--.-" and did not update.

**Root Cause**: The operator page JavaScript was reading from the wrong data path in the Socket.IO update messages.

**Code Analysis**:
- Operator page (`operator.html` line 349-352) was looking for: `data.motors.axis1.position`
- Correct data path is: `data.motors.m3_backstop.position_mm`
- This is the same path used successfully by the dashboard page

**Solution**:
- Updated `app/web/templates/operator.html` line 348-352
- Changed Socket.IO update handler to read from correct path
- Now matches the data structure documented in API documentation

**Changes Made**:
```javascript
// Before (incorrect):
if (data.motors && data.motors.axis1) {
    const position = data.motors.axis1.position || 0;
    actualDisplay.textContent = position.toFixed(1);
}

// After (correct):
if (data.motors && data.motors.m3_backstop) {
    const position = data.motors.m3_backstop.position_mm || 0;
    actualDisplay.textContent = position.toFixed(1);
}
```

**Result**:
- ✓ Operator page "ACTUAL" display now shows M3 encoder position in real-time
- ✓ Position updates at 10 Hz via Socket.IO (same as dashboard)
- ✓ Consistent data path across all web interfaces
- ✓ AS5600 encoder position from Raspberry Pi I2C displays correctly on all pages

**Files Modified**:
- `app/web/templates/operator.html` (line 348-352)

**Testing**:
- Deployed to Raspberry Pi at 192.168.68.109
- Service restarted successfully
- Operator page verified at http://192.168.68.109:5000/
- Position matches dashboard display

---

### November 13, 2025 - Session 3 Summary: AS5600 Encoder Migration to Raspberry Pi I2C

#### Problem: RS-485 Interference with ESP32B I2C

**Initial Issue**: AS5600 magnetic encoder worked perfectly when ESP32B connected via USB, but failed to detect when connected to RS-485 bus. Position readings remained stuck at 0.0 mm during production operation.

**Root Cause Discovery**:
- ESP32B firmware v2.0 had AS5600 I2C support (Nov 12 binary)
- USB-only test: AS5600 detected perfectly (angles: 1780, 1785, 1786)
- RS-485 connection: AS5600 not detected, position = 0.0 mm
- Isolated test (RS-485 TX/RX disconnected): AS5600 detected again!
- **Conclusion**: RS-485 differential signaling (high voltage) corrupted I2C communication (low voltage) on same ESP32

#### Failed Solution Attempt: Firmware v2.1 with Interference Mitigation

**Changes Made to ESP32B Firmware**:
- Increased I2C timeout: 1ms → 50ms
- Reduced I2C clock: 400kHz → 100kHz (standard mode)
- Added retry logic: 3 attempts with delays
- Enhanced error handling

**Result**: Failed - encoder_detected flag set false at startup and never retried, so encoder remained disabled even if interference was reduced.

#### Successful Solution: Migration to Raspberry Pi I2C

**User's Brilliant Suggestion**: "Are we able to move the I2C connection for the encoder onto the raspberry pi instead. this could remove the conflict if possible?"

**Implementation**:

1. **Created New Python Service**: `/home/ambf1/pleat_saw/app/services/encoder_reader.py`
   - AS5600EncoderReader class with background threading
   - I2C communication via smbus2 library
   - Multi-turn tracking with wrap-around detection
   - 100ms polling interval (10 Hz)
   - Auto-detection at startup

2. **Modified AxisGateway**: `/home/ambf1/pleat_saw/app/services/axis_gateway.py`
   - Instantiates EncoderReader on startup
   - Modified `m3_get_position()` to read from encoder_reader instead of ESP32B Modbus
   - Complete electrical isolation from RS-485

3. **Hardware Wiring**:
   - AS5600 VCC → Pi 3.3V (Pin 1 or 17)
   - AS5600 GND → Pi GND
   - AS5600 SDA → Pi GPIO2 (Pin 3) → /dev/i2c-1
   - AS5600 SCL → Pi GPIO3 (Pin 5) → /dev/i2c-1

**Testing Results**:
- AS5600 detected successfully at address 0x36
- Initial angle reading: 1993
- Real-time position tracking working: -0.022mm, 0.017mm, 0.272mm, etc.
- 17 unique position readings captured over test period
- Position range during test: 14.8633 mm → 16.4832 mm
- **✓✓✓ SUCCESS! Complete resolution of interference issue**

**Benefits of Pi I2C Solution**:
- Complete electrical isolation from RS-485 bus
- Reliable detection at startup (no interference)
- Independent of ESP32B Modbus communication
- Multi-turn tracking handled in Python (easy to debug)
- No firmware changes needed for future encoder updates

**Files Created/Modified**:
- **NEW**: `/home/ambf1/pleat_saw/app/services/encoder_reader.py` (185 lines)
- **Modified**: `/home/ambf1/pleat_saw/app/services/axis_gateway.py` (m3_get_position method)
- **Documentation**: Updated COMPREHENSIVE_README.md with migration details

**Technical Details**:
- I2C Bus: /dev/i2c-1 (Raspberry Pi GPIO2/GPIO3)
- AS5600 Address: 0x36
- Resolution: 12-bit (4096 counts/rev)
- Linear Resolution: 0.00122 mm/count (5mm leadscrew)
- Multi-turn Algorithm: Delta calculation with wrap-around handling (±2048 threshold)
- Thread-safe: Lock-protected position reads

---

### November 13, 2025 - Session 2 Summary

#### 1. M2 Fixture Motor Homing Feature

**Issue**: M2 motor needed manual homing capability to return to S2 sensor after incomplete cycles

**Changes Made**:
- `app/services/supervisor.py`:
  - Added new state: `MANUAL_HOME_M2` to State enum
  - Added state handler: `_state_manual_home_m2()` - monitors S2 sensor and stops motor when detected
  - Added public method: `manual_home_m2()` - triggers supervised homing sequence at 30% of auto reverse speed
  - Added `MANUAL_HOME_M2` to pauseable states for light curtain safety
  - Homing includes timeout protection (uses m2_rev_timeout setting)

- `app/services/axis_gateway.py`:
  - Updated `m2_home()` to accept velocity and acceleration parameters
  - Sets velocity before sending reverse command to ESP32A

- `app/services/web_monitor.py`:
  - Updated `m2_home` command handler to call `supervisor.manual_home_m2()` instead of direct motor control
  - Supervisor now monitors S2 sensor via I/O poller and stops motor automatically

- `app/web/templates/dashboard.html`:
  - Added "Home" button to M2 - Fixture Motor section (next to Stop button)

- `app/web/static/js/dashboard.js`:
  - Added `homeM2()` function to send home command to API

**Result**:
- M2 motor homes at 30% of auto reverse speed (36 mm/s default)
- Supervisor monitors S2 sensor and stops motor when triggered
- Fixes issue where motor would run continuously without stopping at sensor
- Sensors (S2, S3) are on I/O module (separate RS-485 channel), not accessible to ESP32A
- Safe operation with timeout and light curtain pause support

#### 2. M3 Home Button Moved from Operator Page

**Issue**: M3 home button not needed on production operator interface

**Changes Made**:
- `app/web/templates/operator.html`:
  - Removed "home" button from bottom navigation buttons
  - Removed `homeButton` constant declaration
  - Removed event listener for home button

**Result**:
- Operator page cleaner with only ENG button at bottom
- M3 home functionality still available in dashboard (engineering view)
- Simplifies operator interface for production use

#### 3. M2 Jog Speed Auto-Calculation

**Issue**: M2 jog speeds were too slow (default 10 mm/s)

**Changes Made**:
- `app/web/templates/dashboard.html`:
  - Changed default M2 jog velocity input from 10 to 60 mm/s

- `app/web/static/js/dashboard.js`:
  - Added `setupTimeoutEventListeners()` function
  - Jog velocity automatically calculated as 50% of average auto cycle speeds on page load
  - Formula: `jogSpeed = (m2_vel_fwd_mm_s + m2_vel_rev_mm_s) / 2 * 0.5`

**Result**:
- M2 jog operations now default to 50% of auto speeds (60 mm/s with default 120 mm/s auto speed)
- M2 home operations at 30% of auto reverse speed (36 mm/s default)
- Users can still manually adjust jog speed in dashboard

#### 4. Parameter Persistence Across Power Cycles

**Issue**: Engineering parameter changes (RPM, velocities, timeouts) reset to config defaults after Pi reboot

**Changes Made**:
- `app/services/supervisor.py`:
  - Added imports: `yaml` and `os` for file operations
  - Added constant: `RUNTIME_PARAMS_FILE = 'config/runtime_params.yaml'`
  - Added `_save_runtime_params()` method: Saves parameters to YAML file
  - Added `_load_runtime_params()` method: Loads parameters from file on startup
  - Updated all setter methods to call `_save_runtime_params()` after changes:
    - `set_m1_rpm()` - M1 blade RPM
    - `set_m2_fwd_velocity()` - M2 forward velocity
    - `set_m2_rev_velocity()` - M2 reverse velocity
    - `set_m2_fwd_timeout()` - NEW: M2 forward timeout setter
    - `set_m2_rev_timeout()` - NEW: M2 reverse timeout setter
  - Updated `__init__()`: Calls `_load_runtime_params()` after loading config defaults

- `app/services/web_monitor.py`:
  - Added `set_m2_fwd_timeout` command handler
  - Added `set_m2_rev_timeout` command handler

- `app/web/static/js/dashboard.js`:
  - Added `setupTimeoutEventListeners()` function
  - Timeout inputs now auto-save on change (blur event)
  - Called in DOMContentLoaded initialization

**Saved Parameters**:
- M1 Blade RPM (5-1000)
- M2 Forward Velocity (10-400 mm/s)
- M2 Reverse Velocity (10-400 mm/s)
- M2 Forward Timeout (1-120 seconds)
- M2 Reverse Timeout (1-120 seconds)

**File Location**: `/home/ambf1/pleat_saw/app/config/runtime_params.yaml`

**Result**:
- All engineering parameters persist across service restarts, Pi reboots, and power cycles
- Dashboard loads saved values on page load
- Changes automatically saved when updated via dashboard
- Falls back to config.yaml defaults if runtime_params.yaml doesn't exist
- Logs show "Runtime parameters loaded successfully" with individual parameter values

### November 13, 2025 - Session 1 Summary

#### 1. Nextion HMI Removal

**Issue**: Physical Nextion display no longer part of project, but references still in code

**Changes Made**:
- `app/main.py`:
  - Line 158: Set `self.hmi = None`, disabled initialization
  - Lines 195-207: Commented out HMI callback registrations
  - Lines 260-262: Commented out HMI start command
  - Lines 285-288: Commented out HMI stop/disconnect

- `app/services/supervisor.py`:
  - Lines 598-600: Added `if self.hmi is None: return` check in `_update_hmi()`

- `app/services/web_monitor.py`:
  - Lines 186-192: Disabled Nextion connection checking
  - Lines 198-202: Set Nextion status to "Disabled" in diagnostics
  - Lines 542-546: Commented out Nextion statistics broadcasting
  - Lines 584-586: Commented out Nextion log callback registration

- `app/web/templates/dashboard.html`:
  - Lines 73-79: Commented out Nextion HMI connection item
  - Lines 338-361: Commented out entire "Nextion Communications Monitor" section

**Result**: System operates without Nextion dependencies, logs show "Nextion HMI disabled"

#### 2. Web Interface Restoration

**Issue**: Operator and engineering pages missing from project

**Changes Made**:
- Copied `operator.html` from backup to `/app/web/templates/`
- Copied `engineering.html` from backup to `/app/web/templates/`
- Updated `app/services/web_monitor.py` routes:
  - Line 95-98: Changed `/` route to serve `operator.html`
  - Line 100-103: Added `/engineering` route for `engineering.html`
  - Line 105-108: Added `/dashboard` route for `dashboard.html`

**Result**: Three web pages now accessible:
- `/` → Operator interface (touchscreen-optimized)
- `/engineering` → Engineering diagnostics
- `/dashboard` → Commissioning dashboard

#### 3. Operator Page Navigation Fix

**Issue**: ENG button was pointing to engineering page (duplicate of dashboard)

**Changes Made**:
- `app/web/templates/operator.html`:
  - Line 395: Changed `window.location.href = '/engineering'` to `'/dashboard'`

**Result**: ENG button now navigates to dashboard with all diagnostic features

### November 11, 2025 - Previous Session Summary

#### Motor Calibration and Bug Fixes

**M1 Blade Motor**:
- Issue: RPM mismatch (1005 commanded → 36 actual)
- Fix: Changed `M1_PULSES_PER_REV` from 800 to 22,333
- Result: 1000 RPM commanded = 1000 RPM actual (1:1 ratio)

**M2 Fixture Motor**:
- Issue 1: Wrong direction
- Fix 1: Changed `M2_DIR_FWD` to `false`
- Issue 2: 50× too slow, 16-bit Modbus overflow
- Fix 2: Changed Modbus scaling from ×1000 to ×10 in `axis_gateway.py` and ESP32A firmware
- Issue 3: Incorrect steps/mm calculation
- Fix 3: Set `M2_STEPS_PER_MM = 750` (5000 × 1.5 / 10)
- Result: Motor direction correct, speed accurate, no overflow

**ESP32B AS5600 Encoder**:
- Issue: I2C errors blocking Modbus communication
- Fix: Added startup detection, disable I2C polling if encoder not found
- Code: `encoder_detected` flag, conditional polling in main loop
- Result: Modbus stable even when encoder hardware absent

**Dashboard Parameter Persistence**:
- Issue: Values reset to defaults on page reload
- Fix: Created `/api/engineering_params` endpoint, fetch on page load
- Code: `fetchEngineeringParams()` in `dashboard.js`
- Result: M1 RPM, M2 velocities, timeouts persist across reloads

**M2 Residual Motion**:
- Issue: Servo continues moving slightly after cycle complete
- Fix: Send 5 stop commands over 0.5 seconds in `_state_complete()`
- Code: `supervisor.py` lines 522-527
- Result: Residual motion eliminated

**Dashboard Navigation Button**:
- Issue: Return button removed after engineering changes
- Fix: Added "← Return to Operator View" button in header
- Code: `dashboard.html` lines 21-23
- Result: Easy navigation back to operator interface

---

## Development

### Local Development Environment

**Mac Setup**:
```bash
cd /Users/ceripritch/Documents/Pleat\ Saw\ V3/panel_node_rounddb_s3_minui/pleat_saw
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Mock Mode** (testing without hardware):
- Not currently implemented
- Would require mock Modbus responses in `modbus_master.py`

### Code Style

- **Language**: Python 3.11+
- **Style**: PEP 8
- **Docstrings**: Google style
- **Type Hints**: Encouraged but not required
- **Logging**: Standard Python logging module

### Deployment to Pi

**Manual Deployment**:
```bash
# Stop service
ssh ambf1@192.168.68.109 "sudo systemctl stop pleat-saw"

# Copy files
scp -r app ambf1@192.168.68.109:~/pleat_saw/
scp -r config ambf1@192.168.68.109:~/pleat_saw/
scp requirements.txt ambf1@192.168.68.109:~/pleat_saw/

# Install dependencies (if changed)
ssh ambf1@192.168.68.109 "cd ~/pleat_saw && source venv/bin/activate && pip install -r requirements.txt"

# Start service
ssh ambf1@192.168.68.109 "sudo systemctl start pleat-saw"

# View logs
ssh ambf1@192.168.68.109 "sudo journalctl -u pleat-saw -f"
```

**Deployment Script** (if available):
```bash
./scripts/deploy_to_pi.sh
```

### ESP32 Firmware Updates

**Flashing via USB**:
1. Connect ESP32 to Mac via USB
2. Open PlatformIO or Arduino IDE
3. Select port (e.g., `/dev/cu.usbserial-xxx`)
4. Upload firmware
5. Disconnect USB
6. Reconnect to RS-485 bus

**ESP32A (M1, M2)**:
```bash
cd firmware/esp32a_axis12
pio run --target upload --upload-port /dev/cu.usbserial-xxx
```

**ESP32B (M3)**:
```bash
cd firmware/esp32b_backstop
pio run --target upload --upload-port /dev/cu.usbserial-xxx
```

**Via esptool on Pi**:
```bash
# Reset and read chip ID
python3 ~/pleat_saw/firmware/esptool/esptool.py --chip esp32 --port /dev/ttyUSB0 --after hard_reset chip_id

# Upload firmware
python3 ~/pleat_saw/firmware/esptool/esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x1000 firmware.bin
```

### Version Control

**Not Currently Under Git**

To initialize:
```bash
cd /home/ambf1/pleat_saw
git init
git add .
git commit -m "Initial commit - Version 3.2"
```

### Testing

**Manual Testing**:
- Operator interface: Start cycle, verify completion
- Dashboard: Test each motor individually
- Input overrides: Force sensor states, verify behavior
- Parameter persistence: Change values, reload page, verify retained

**Unit Tests**: Not currently implemented

**Integration Tests**: Not currently implemented

---

## File Structure

### Current Project Directory

```
/home/ambf1/pleat_saw/
├── app/
│   ├── __init__.py
│   ├── main.py                         # Application entry (Nextion disabled)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── supervisor.py               # State machine (M2 stop fix, HMI None check)
│   │   ├── axis_gateway.py             # Motor control (M2 ×10 scaling, Pi encoder)
│   │   ├── encoder_reader.py           # AS5600 encoder via Pi I2C (NEW in v3.4)
│   │   ├── io_poller.py                # Digital I/O
│   │   ├── modbus_master.py            # Modbus RTU master
│   │   ├── nextion_bridge.py           # DISABLED (not imported/used)
│   │   └── web_monitor.py              # Flask web (3 routes, Nextion disabled)
│   ├── utils/
│   │   ├── __init__.py
│   │   └── config.py                   # Configuration loader
│   └── web/
│       ├── static/
│       │   ├── css/
│       │   │   └── dashboard.css
│       │   ├── js/
│       │   │   └── dashboard.js        # fetchEngineeringParams()
│       │   └── images/
│       │       └── afm_logo.png
│       └── templates/
│           ├── operator.html           # Touchscreen UI (ENG → /dashboard)
│           ├── engineering.html        # Diagnostics page
│           └── dashboard.html          # Commissioning (Nextion hidden)
├── config/
│   ├── config.yaml                     # Main configuration
│   └── io_map.yaml                     # I/O definitions
├── firmware/
│   ├── esp32a_axis12/
│   │   ├── platformio.ini
│   │   └── src/
│   │       └── main.cpp                # M1: 22,333 pulses, M2: 750 steps/mm, ×10 scaling
│   ├── esp32b_backstop/
│   │   ├── platformio.ini
│   │   └── src/
│   │       └── main.cpp                # M3 with AS5600 auto-detection
│   └── esptool/
│       └── esptool.py
├── logs/
│   └── pleat_saw.log
├── venv/                                # Python virtual environment
├── requirements.txt
├── COMPREHENSIVE_README.md              # This file (updated Nov 13, 2025 - Session 4)
└── README.md                            # Quick start guide
```

### Backup Location

```
/Users/ceripritch/Documents/pleat_saw_backups/
└── pleat_saw_backup_20251111_113319/   # Last backup (before Nextion removal)
    ├── pi_project/                      # Previous Pi code
    └── local_dev/                       # Development version with ESP32 firmware
```

---

## Appendix

### Modbus Register Map

#### ESP32A (Slave 2) - M1 Blade & M2 Fixture

**M1 Blade Registers:**
| Type | Address | Size | Description |
|------|---------|------|-------------|
| HREG | 0 | uint16 | RPM (0-1000) |
| HREG | 1 | uint16 | Ramp time (ms) |
| COIL | 0 | bool | Enable (1=run) |
| COIL | 1 | bool | Direction (1=CW) |
| ISTS | 0 | bool | Running status |
| ISTS | 1 | bool | Fault status |
| ISTS | 2 | bool | Ready status |

**M2 Fixture Registers:**
| Type | Address | Size | Description |
|------|---------|------|-------------|
| HREG | 10-11 | int32 | Velocity (mm/s × 10) |
| HREG | 12-13 | int32 | Acceleration (mm/s²) |
| COIL | 10 | bool | Feed forward |
| COIL | 11 | bool | Feed reverse |
| COIL | 12 | bool | Stop |
| ISTS | 10 | bool | In motion |
| ISTS | 11 | bool | At S2 (home) |
| ISTS | 12 | bool | At S3 (forward) |
| ISTS | 13 | bool | Fault |

#### ESP32B (Slave 3) - M3 Backstop

**M3 Position Control:**
| Type | Address | Size | Description |
|------|---------|------|-------------|
| HREG | 20-21 | int32 | Target position (mm × 100) |
| HREG | 22-23 | int32 | Current position (mm × 100) |
| HREG | 24 | uint16 | Velocity (mm/s) |
| COIL | 20 | bool | Go to position |
| COIL | 21 | bool | Home |
| COIL | 22 | bool | Stop |
| ISTS | 20 | bool | In motion |
| ISTS | 21 | bool | At target |
| ISTS | 22 | bool | Homed |
| ISTS | 23 | bool | Fault |

**Encoder Registers (when detected):**
| Type | Address | Size | Description |
|------|---------|------|-------------|
| IREG | 0-1 | int32 | Raw angle (0-4095) |
| IREG | 2-3 | int32 | Accumulated counts |
| IREG | 4-5 | int32 | Position (mm × 1000) |
| COIL | 30 | bool | Reset position |

### Pin Assignments

**Raspberry Pi**:
- USB 2.0 Port 1: RS-485 adapter Ch0 → /dev/ttyUSB0 (I/O, 9600 baud)
- USB 2.0 Port 2: RS-485 adapter Ch1 → /dev/ttyUSB1 (Motors, 115200 baud)
- Ethernet: 192.168.68.109
- GPIO2 (Pin 3): I2C SDA → AS5600 encoder
- GPIO3 (Pin 5): I2C SCL → AS5600 encoder
- 3.3V (Pin 1 or 17): AS5600 VCC
- GND: AS5600 GND

**ESP32A (80:f3:da:4b:a3:ec)**:
- GPIO16: RS-485 RX
- GPIO17: RS-485 TX
- M1 Blade: MCPWM Unit 0, Timer 0
- M2 Fixture: MCPWM Unit 0, Timer 1

**ESP32B (84:1f:e8:28:39:40)**:
- GPIO16: RS-485 RX
- GPIO17: RS-485 TX
- GPIO21: I2C SDA (not used - AS5600 moved to Pi)
- GPIO22: I2C SCL (not used - AS5600 moved to Pi)
- M3 Backstop: MCPWM Unit 0, Timer 0

### Wiring Diagrams

**RS-485 Bus (Dual Channel)**:
```
Channel 0 (I/O):
Pi USB /dev/ttyUSB0 → RS-485 Adapter → I/O Module(s)
Baud: 9600

Channel 1 (Motors):
Pi USB /dev/ttyUSB1 → RS-485 Adapter → ESP32A + ESP32B
Baud: 115200

120Ω terminator at each end of each bus
```

**Motor Driver Connections** (typical):
```
ESP32 Step Pin → Optoisolator → Driver STEP+
ESP32 Dir Pin  → Optoisolator → Driver DIR+
24V DC → Driver Power
Driver → Motor (A+, A-, B+, B-)
```

**AS5600 Encoder (Raspberry Pi I2C)**:
```
AS5600 VCC → Raspberry Pi 3.3V (Pin 1 or 17)
AS5600 GND → Raspberry Pi GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
AS5600 SDA → Raspberry Pi GPIO2 (Pin 3) → /dev/i2c-1
AS5600 SCL → Raspberry Pi GPIO3 (Pin 5) → /dev/i2c-1
Magnet: Diametrically magnetized, centered over sensor
Distance: 0.5-3mm from sensor face
I2C Address: 0x36 (default, not configurable)

Note: AS5600 previously connected to ESP32B but moved to Pi I2C
to eliminate RS-485 interference issues.
```

---

## Revision History

| Date | Version | Description |
|------|---------|-------------|
| 2025-11-13 | 3.4.1 | Fixed operator page "ACTUAL" display - corrected data path from data.motors.axis1.position to data.motors.m3_backstop.position_mm to show M3 encoder position. |
| 2025-11-13 | 3.4 | AS5600 encoder migrated from ESP32B I2C to Raspberry Pi I2C to eliminate RS-485 interference. New encoder_reader.py service with multi-turn tracking. |
| 2025-11-13 | 3.3 | M2 manual homing with sensor monitoring, parameter persistence across reboots, M2 jog speed auto-calculation, M3 home moved to dashboard only |
| 2025-11-13 | 3.2 | Nextion HMI removed, web interface restored (operator/engineering/dashboard), comprehensive documentation update |
| 2025-11-11 | 3.1 | Motor calibration (M1, M2), ESP32B encoder detection, parameter persistence, M2 residual motion fix |
| 2025-11 | 3.0 | Web HMI replaces Nextion, services-based architecture, Flask web monitor |
| 2025-10 | 2.0 | Modbus RTU implementation with ESP32 slaves |
| 2025-09 | 1.0 | Initial monolithic controller |

---

## Contact & Support

**Project Location**:
- Mac: `/Users/ceripritch/Documents/Pleat Saw V3/panel_node_rounddb_s3_minui/pleat_saw`
- Pi: `/home/ambf1/pleat_saw`

**Network Access**:
- Raspberry Pi: `ambf1@192.168.68.109` (password: 1978)
- Web Interface: `http://192.168.68.109:5000/`
  - Operator: `http://192.168.68.109:5000/`
  - Engineering: `http://192.168.68.109:5000/engineering`
  - Dashboard: `http://192.168.68.109:5000/dashboard`

**Backup Location**: `/Users/ceripritch/Documents/pleat_saw_backups/`

**Documentation**:
- This file: `COMPREHENSIVE_README.md` (updated November 13, 2025 - Session 4: Operator Page Position Fix)
- Quick start: `README.md`
- Session summaries: Check backup directory for previous session notes

**Hardware**:
- ESP32A MAC: `80:f3:da:4b:a3:ec` (M1 Blade, M2 Fixture)
- ESP32B MAC: `84:1f:e8:28:39:40` (M3 Backstop motor control)
- AS5600 Encoder: Connected to Raspberry Pi I2C (/dev/i2c-1, GPIO2/GPIO3)

---

**END OF COMPREHENSIVE DOCUMENTATION**
**Last Updated: November 13, 2025 (Session 4 - Operator Page Position Fix)**
**Version: 3.4.1**
