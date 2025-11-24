# Supervisor State Machine

Complete documentation of the supervisor state machine that controls the pleat saw process flow.

## State Diagram

```
      [INIT]
         |
         v
      [IDLE] <--------+
         |            |
    (Start button)   |
         |            |
         v            |
   [PRECHECK]        |
         |            |
    (Safety OK)      |
         |            |
         v            |
 [START_SPINDLE]     |
         |            |
   (Blade running)   |
         |            |
         v            |
    [FEED_FWD]       |
         |            |
   (Sensor3 hit)     |
         |            |
         v            |
     [DWELL]         |
         |            |
  (Dwell complete)   |
         |            |
         v            |
    [FEED_REV]       |
         |            |
   (Sensor2 hit)     |
         |            |
         v            |
     [CLAMP]         |
         |            |
  (Clamp confirmed)  |
         |            |
         v            |
    [SAW_STOP]       |
         |            |
   (Blade stopped)   |
         |            |
         v            |
    [AIR_JET]        |
         |            |
  (Air jet complete) |
         |            |
         v            |
    [COMPLETE]-------+
         |
         |
    (ANY STATE)
         |
   (Safety drop)
         |
         v
     [ESTOP]
         |
   (Safety OK + Reset)
         |
         v
      [IDLE]


    (ANY STATE except IDLE)
         |
      (Alarm condition)
         |
         v
      [ALARM]
         |
   (RESET_ALARMS)
         |
         v
      [IDLE]
```

## States

### INIT

**Entry**: System power-on

**Actions**:
- Initialize all outputs to safe state
- Set clamp OFF, air jet OFF, lamps OFF

**Exit**: Automatic transition to IDLE

**Duration**: Instantaneous

---

### IDLE

**Description**: Ready state, waiting for start command

**Entry Actions**:
- Green solid lamp ON
- Green flash lamp OFF
- Release clamp (if engaged)

**Conditions**:
- Safety input (IN16) must be READY
- No alarms latched

**Exit Trigger**:
- Start button (IN1) pressed

**Next State**: PRECHECK

**HMI Display**: "IDLE / READY"

---

### PRECHECK

**Description**: Pre-cycle safety verification

**Checks**:
1. Safety input (IN16) = READY
2. No alarms latched
3. No motor faults

**Success**: Transition to START_SPINDLE

**Failure**: Transition to ALARM with code:
- `PRECHECK_SAFETY_NOT_READY`
- `PRECHECK_ALARM_LATCHED`
- `PRECHECK_MOTOR_FAULT`

**Duration**: < 100ms (single scan)

---

### START_SPINDLE

**Description**: Start blade motor (M1)

**Entry Actions**:
- Send M1_CMD=RUN
- Set M1_RPM from config
- Set M1_RAMP_MS from config

**Wait For**:
- M1_STATUS.RUNNING = true

**Timeout**: 3.0 seconds (configurable)

**Success**: Transition to FEED_FWD

**Failure**: Transition to ALARM with code `TIMEOUT_BLADE_START`

**HMI Display**: "STARTING BLADE"

---

### FEED_FWD

**Description**: Feed fixture forward until Sensor3

**Entry Actions**:
- Set M2 velocity and acceleration
- Send M2_CMD=FWD_UNTIL_S3
- Start green flash lamp (2 Hz blink)

**Wait For**:
- Sensor3 (IN3) = active

**On Success**:
- Send M2_CMD=STOP
- Transition to DWELL

**Timeout**: 5.0 seconds (configurable via `motion.m2_fixture.timeout_fwd_s`)

**On Timeout**:
- Send M2_CMD=STOP
- Transition to ALARM with code `TIMEOUT_FWD`

**HMI Display**: "FEEDING FORWARD"

---

### DWELL

**Description**: Pause at forward position

**Duration**: 1.5 seconds (configurable via `motion.cycle.dwell_after_s3_s`)

**Actions**:
- Wait for configured duration
- No motion

**Exit**: Automatic after dwell time

**Next State**: FEED_REV

**HMI Display**: "DWELL"

---

### FEED_REV

**Description**: Feed fixture reverse until Sensor2

**Entry Actions**:
- Send M2_CMD=REV_UNTIL_S2

**Wait For**:
- Sensor2 (IN2) = active

**On Success**:
- Send M2_CMD=STOP
- Transition to CLAMP

**Timeout**: 5.0 seconds (configurable via `motion.m2_fixture.timeout_rev_s`)

**On Timeout**:
- Send M2_CMD=STOP
- Transition to ALARM with code `TIMEOUT_REV`

**HMI Display**: "FEEDING REVERSE"

---

### CLAMP

**Description**: Activate pneumatic clamp

**Entry Actions**:
- Set output CH1 (clamp) = ON

**Duration**: 0.1 seconds (configurable confirmation delay)

**Exit**: Automatic after confirmation

**Next State**: SAW_STOP

**HMI Display**: "CLAMPING"

---

### SAW_STOP

**Description**: Stop blade motor

**Entry Actions**:
- Send M1_CMD=STOP

**Duration**: 0.5 seconds (configurable spindown time via `motion.cycle.saw_spindown_s`)

**Purpose**: Allow blade to decelerate safely

**Exit**: Automatic after spindown

**Next State**: AIR_JET

**HMI Display**: "STOPPING BLADE"

---

### AIR_JET

**Description**: Pulse air jet solenoid

**Entry Actions**:
- Set output CH2 (air jet) = ON

**Duration**: 1.0 seconds (configurable via `motion.cycle.air_jet_s`)

**Exit Actions**:
- Set output CH2 (air jet) = OFF

**Exit**: Automatic after pulse duration

**Next State**: COMPLETE

**HMI Display**: "AIR JET"

---

### COMPLETE

**Description**: Cycle finished successfully

**Entry Actions**:
- Release clamp (CH1 = OFF)
- Green solid lamp ON
- Green flash lamp OFF
- Increment cycle counter

**Duration**: Instantaneous

**Exit**: Automatic

**Next State**: IDLE

**HMI Display**: "CYCLE COMPLETE"

---

### ALARM

**Description**: Alarm condition (non-safety)

**Entry Actions**:
- Stop all motors immediately
- Set all outputs to safe state
- Latch alarm code
- Green solid OFF
- Green flash OFF

**Common Alarm Codes**:
- `TIMEOUT_FWD` - Fixture forward timeout
- `TIMEOUT_REV` - Fixture reverse timeout
- `TIMEOUT_BLADE_START` - Blade start timeout
- `PRECHECK_SAFETY_NOT_READY` - Safety not ready at precheck
- `PRECHECK_ALARM_LATCHED` - Attempted start with alarm latched
- `MOTOR_FAULT` - Motor fault status bit set

**Exit Trigger**:
- HMI command: `RESET_ALARMS`
- Conditions: Safety must be OK

**Next State**: IDLE

**HMI Display**: "ALARM: [code]"

---

### ESTOP

**Description**: Emergency stop (Category 0)

**Entry Trigger**:
- Safety input (IN16) drops to NOT READY during any active state

**Entry Actions**:
- **Immediate stop** of all motors (no deceleration)
- Set all outputs to safe state:
  - Clamp OFF
  - Air jet OFF
  - Green solid OFF
  - Green flash OFF
- Latch alarm code: `SAFETY_ESTOP`
- Increment ESTOP counter

**Exit Conditions**:
1. Safety input restored to READY
2. HMI command: `RESET_ALARMS`

**Next State**: IDLE

**HMI Display**: "EMERGENCY STOP"

## Safety Interlocks

### Global Safety Check

**Frequency**: Every state machine loop (50 Hz)

**Watchdog**: 1.0 second timeout (configurable)

**Input**: IN16 (Safety input)
- Active (logic 1) = READY
- Inactive (logic 0) = NOT READY

### Safety Drop Behavior

If safety input drops during any state **except IDLE**:

1. **Immediate Actions** (Category 0 Stop):
   - M1_CMD = STOP (blade motor)
   - M2_CMD = STOP (fixture motor)
   - M3_CMD = STOP (backstop motor)
   - All outputs to safe state

2. **State Transition**:
   - Any state → ESTOP

3. **Latch Alarm**:
   - Code: `SAFETY_ESTOP`
   - Requires manual reset

### Reset Procedure

After ESTOP or ALARM:

1. **Verify**:
   - Safety input = READY
   - All faults cleared
   - Machine in safe state

2. **Command**:
   - HMI button: "RESET ALARMS"
   - Or HMI command: `cmd=RESET_ALARMS`

3. **Result**:
   - Alarm cleared
   - State → IDLE
   - Ready for new cycle

## Lamps

### Green Solid (CH3)

- **ON**: IDLE, COMPLETE (ready states)
- **OFF**: During cycle, alarms

### Green Flash (CH4)

- **BLINK** (2 Hz): During active cycle (PRECHECK → AIR_JET)
- **OFF**: IDLE, ALARM, ESTOP

## Configuration

All timing parameters are configurable via `config/motion.yaml`:

```yaml
m1_blade:
  timeout_start_s: 3.0

m2_fixture:
  timeout_fwd_s: 5.0
  timeout_rev_s: 5.0

cycle:
  dwell_after_s3_s: 1.5
  air_jet_s: 1.0
  saw_spindown_s: 0.5
  clamp_confirm_s: 0.1

safety:
  watchdog_timeout_s: 1.0
```

## Statistics

The supervisor tracks:

- `cycles_complete`: Total successful cycles
- `alarms_total`: Total alarm events
- `estops_total`: Total emergency stops

Access via supervisor API or HMI.
