/**
 * ESP32B Firmware v9.1 - USB Serial Motor Controller with Interrupt-Based Encoder
 *
 * Features closed-loop position control using simple interrupt encoder feedback
 *
 * Hardware:
 * - Motor M3: STEP=GPIO27, DIR=GPIO14
 * - Quadrature Encoder: A=GPIO32, B=GPIO33 (400 PPR, interrupt-based)
 * - USB Serial: 115200 baud
 * - Pulley: 15 teeth × 10mm pitch = 150mm/rev
 *
 * Commands:
 * - g<position>  : Go to position in inches (e.g., "g12.5")
 * - h            : Home (reset encoder position to 0)
 * - s            : Stop motor
 * - v<velocity>  : Set velocity in inches/sec (e.g., "v2.0")
 * - r            : Reset encoder position to 0
 * - ?            : Query status (position, velocity, encoder)
 *
 * Automatic Status Updates (10 Hz):
 * - POS <inches> <velocity> <encoder_counts> <motor_steps>
 *
 * Responses:
 * - AT_TARGET <position>    : Movement complete
 * - MOVING <current> <target> : Currently moving
 * - STOPPED <position>      : Motor stopped
 * - HOMED                   : Position reset to 0
 * - VELOCITY <vel>          : Velocity set
 * - ENCODER_RESET           : Encoder counts reset
 * - STATUS ...              : Full status report
 */

#include <Arduino.h>

// ========== Hardware Pin Definitions ==========
#define M3_STEP_PIN     27
#define M3_DIR_PIN      14

// Quadrature Encoder (400 PPR) - Interrupt-based
#define ENC_A_PIN       32  // Encoder Channel A (interrupt)
#define ENC_B_PIN       33  // Encoder Channel B (sampled)

// Reset button (active-LOW to GND, matches original sketch)
#define RESET_PIN       36
#define RESET_DEBOUNCE_MS 50

// ========== Mechanical Constants ==========
#define PITCH_MM        10.0f   // T10 belt pitch
#define TEETH           15      // 15T pulley
#define CIRC_MM         (PITCH_MM * TEETH)  // 150.0 mm/rev

// Calibration scale based on measured travel error (35.5 in command, 0.188 in short)
#define CALIBRATION_SCALE 1.005324f

// Interrupt-based encoder: 400 PPR, 4x quadrature counting (calibrated)
#define ENCODER_PPR     400.0f
#define COUNTS_PER_REV  (ENCODER_PPR * 4.0f * CALIBRATION_SCALE)
#define MM_PER_COUNT    (CIRC_MM / COUNTS_PER_REV)  // ~0.0933 mm/count
#define IN_PER_COUNT    (MM_PER_COUNT / 25.4f)      // ~0.00367 inches per count

// Motor step calibration (calibrated)
#define STEPS_PER_REV   6400.0f  // Driver pulses per motor revolution
#define STEPS_PER_MM    ((STEPS_PER_REV * CALIBRATION_SCALE) / CIRC_MM)
#define STEPS_PER_IN    (STEPS_PER_MM * 25.4f)

// Control parameters
#define DEFAULT_VELOCITY_IPS    0.0492f    // ~1.25 mm/s = ~500 steps/sec
#define POSITION_TOLERANCE_IN   (0.2f / 25.4f)  // ±0.2 mm tolerance ≈ 0.0079 in
#define MAX_POSITION_ERROR_IN   0.200f  // Maximum error before alarm
#define CORRECTION_SETTLE_MS    50      // Delay between correction cycles (ms)
#define CORRECTION_VELOCITY_SCALE 0.10f // Corrections at 10% of commanded speed
#define MIN_CORRECTION_VEL_IPS  0.005f  // Minimum correction speed (~0.125 mm/s)

// EMA smoothing for velocity
#define VEL_ALPHA       0.30f

// Status update rate
#define STATUS_UPDATE_MS  100  // 10 Hz

// ========== Timer ==========
hw_timer_t * timer = NULL;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// ========== Interrupt-Based Encoder State ==========
struct {
    bool detected;
    volatile long counts;         // Raw encoder counts (modified by ISR)
    volatile uint8_t last_ab;     // Last A/B state for quadrature decode
    int32_t last_counts;          // Last reading for delta calculation
    int32_t last_delta_counts;    // Delta since last velocity update

    float position_in;      // Current position in inches
    float velocity_ips;     // Instantaneous velocity (in/s)
    float velocity_ema_ips; // Smoothed velocity (in/s)
    uint32_t last_vel_ms;
} encoder;

// ========== Motor State ==========
struct {
    volatile int32_t target_steps;
    volatile int32_t current_steps;
    float velocity_ips;
    float base_velocity_ips;

    volatile bool in_motion;
    volatile bool direction;  // true = forward, false = reverse
    volatile bool step_pin_state;

    uint32_t step_interval_us;
    volatile uint32_t pulse_counter;

    bool motion_complete_flag;

    // Closed-loop control
    float target_position_in;
    bool closed_loop_enabled;
} motor;

// Reset button state (mirrors working sketch behavior)
struct {
    bool last_level;
    bool triggered;
    uint32_t last_edge_ms;
} reset_button;

// ========== Timing ==========
uint32_t last_status_ms = 0;

// ========== Helpers ==========
void syncMotorStepsWithEncoder() {
    if (!encoder.detected) {
        return;
    }
    int32_t synced_steps = (int32_t)(encoder.position_in * STEPS_PER_IN);
    portENTER_CRITICAL(&timerMux);
    motor.current_steps = synced_steps;
    portEXIT_CRITICAL(&timerMux);
}

// ========== Function Prototypes ==========
void IRAM_ATTR onTimer();
void IRAM_ATTR handleEncoderChange();  // Quadrature interrupt handler
void processSerialCommand();
void updateEncoder();
bool initInterruptEncoder();
int32_t readEncoderCount();
void resetEncoderCount();
void gotoPosition(float position_in);
void home();
void stop();
void setVelocity(float vel_ips);
void resetEncoder();
void queryStatus();
void sendResponse(const char* msg);
void sendStatusUpdate();
void updateTimerFrequency();
void closedLoopCorrection();
void updateResetButton();

// ========== Timer ISR ==========
void IRAM_ATTR onTimer() {
    portENTER_CRITICAL_ISR(&timerMux);

    if (motor.in_motion) {
        int32_t error_steps = motor.target_steps - motor.current_steps;

        // Check if at target (in open-loop step count)
        if (abs(error_steps) <= (int32_t)(POSITION_TOLERANCE_IN * STEPS_PER_IN)) {
            motor.in_motion = false;
            motor.motion_complete_flag = true;
            digitalWrite(M3_STEP_PIN, LOW);
            portEXIT_CRITICAL_ISR(&timerMux);
            return;
        }

        // Generate step pulse (state machine)
        if (!motor.step_pin_state) {
            digitalWrite(M3_STEP_PIN, HIGH);
            motor.step_pin_state = true;
            motor.pulse_counter = 0;
        } else {
            motor.pulse_counter++;
            if (motor.pulse_counter >= 1) {
                digitalWrite(M3_STEP_PIN, LOW);
                motor.step_pin_state = false;

                // Update step counter
                if (motor.direction) {
                    motor.current_steps++;
                } else {
                    motor.current_steps--;
                }
            }
        }
    }

    portEXIT_CRITICAL_ISR(&timerMux);
}

// ========== Quadrature Encoder Handler (4x) ==========
static const int8_t quad_table[16] = {
    0, -1,  1,  0,
    1,  0,  0, -1,
   -1,  0,  0,  1,
    0,  1, -1,  0
};

void IRAM_ATTR handleEncoderChange() {
    uint8_t a = (uint8_t)digitalRead(ENC_A_PIN);
    uint8_t b = (uint8_t)digitalRead(ENC_B_PIN);
    uint8_t curr = (a << 1) | b;
    uint8_t idx = (encoder.last_ab << 2) | curr;
    encoder.counts += quad_table[idx];
    encoder.last_ab = curr;
}

// ========== Interrupt Encoder Functions ==========
bool initInterruptEncoder() {
    // Configure GPIO pins with pullups (matching working script)
    pinMode(ENC_A_PIN, INPUT_PULLUP);
    pinMode(ENC_B_PIN, INPUT_PULLUP);

    // Attach interrupts to both channels for 4x quadrature decoding
    attachInterrupt(digitalPinToInterrupt(ENC_A_PIN), handleEncoderChange, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_B_PIN), handleEncoderChange, CHANGE);

    Serial.println("Interrupt-based Encoder: DETECTED");
    Serial.printf("Resolution: %.0f counts/rev (4x quadrature)\n", COUNTS_PER_REV);

    return true;
}

int32_t readEncoderCount() {
    // Thread-safe read of encoder counts
    noInterrupts();
    long count = encoder.counts;
    interrupts();

    return (int32_t)count;
}

void resetEncoderCount() {
    noInterrupts();
    encoder.counts = 0;
    interrupts();

    encoder.last_counts = 0;
}

void updateEncoder() {
    if (!encoder.detected) return;

    uint32_t now = millis();

    // Read current count (thread-safe)
    int32_t current_count = readEncoderCount();

    // Calculate delta for velocity
    int32_t delta = current_count - encoder.last_counts;
    encoder.last_counts = current_count;
    encoder.last_delta_counts = delta;

    // Calculate position in inches
    encoder.position_in = (float)current_count * IN_PER_COUNT;

    // Calculate velocity (in/s) with EMA smoothing
    if (now != encoder.last_vel_ms) {
        float dt = (now - encoder.last_vel_ms) / 1000.0f;
        encoder.last_vel_ms = now;

        if (dt > 0.0f) {
            encoder.velocity_ips = (float)encoder.last_delta_counts * IN_PER_COUNT / dt;
            encoder.velocity_ema_ips = (VEL_ALPHA * encoder.velocity_ips) +
                                      ((1.0f - VEL_ALPHA) * encoder.velocity_ema_ips);
        }
    }
}

void resetEncoder() {
    resetEncoderCount();
    encoder.velocity_ips = 0.0f;
    encoder.velocity_ema_ips = 0.0f;
    encoder.position_in = 0.0f;
    sendResponse("ENCODER_RESET");
}

// ========== Reset Button Handling ==========
void updateResetButton() {
    uint32_t now = millis();
    bool level = digitalRead(RESET_PIN);  // HIGH idle, LOW pressed

    if (level != reset_button.last_level) {
        reset_button.last_edge_ms = now;
        reset_button.last_level = level;
        if (level == HIGH) {
            reset_button.triggered = false;  // Ready for next press
        }
    }

    if (!reset_button.triggered &&
        level == LOW &&
        (now - reset_button.last_edge_ms) > RESET_DEBOUNCE_MS) {
        resetEncoder();
        reset_button.triggered = true;
    }
}

// ========== Setup ==========
void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n\n========================================");
    Serial.println("ESP32B Firmware v9.1 - Interrupt Encoder");
    Serial.println("========================================");

    // Configure GPIO
    pinMode(M3_STEP_PIN, OUTPUT);
    pinMode(M3_DIR_PIN, OUTPUT);
    digitalWrite(M3_STEP_PIN, LOW);
    digitalWrite(M3_DIR_PIN, LOW);

    // Initialize interrupt-based encoder (pins configured inside init function)
    encoder.detected = initInterruptEncoder();
    if (!encoder.detected) {
        Serial.println("Interrupt Encoder: INIT FAILED (open-loop mode)");
    }

    // Initialize encoder state
    encoder.counts = 0;
    encoder.last_counts = 0;
    encoder.last_delta_counts = 0;
    encoder.last_ab = ((uint8_t)digitalRead(ENC_A_PIN) << 1) | (uint8_t)digitalRead(ENC_B_PIN);
    encoder.position_in = 0.0f;
    encoder.velocity_ips = 0.0f;
    encoder.velocity_ema_ips = 0.0f;
    encoder.last_vel_ms = millis();

    // Initialize motor state
    motor.target_steps = 0;
    motor.current_steps = 0;
    motor.velocity_ips = DEFAULT_VELOCITY_IPS;
    motor.base_velocity_ips = DEFAULT_VELOCITY_IPS;
    motor.in_motion = false;
    motor.direction = true;
    motor.step_pin_state = false;
    motor.pulse_counter = 0;
    motor.motion_complete_flag = false;
    motor.target_position_in = 0.0f;
    motor.closed_loop_enabled = encoder.detected;

    // Reset button configuration
    pinMode(RESET_PIN, INPUT_PULLUP);
    reset_button.last_level = digitalRead(RESET_PIN);
    reset_button.triggered = false;
    reset_button.last_edge_ms = millis();

    // Setup hardware timer
    timer = timerBegin(0, 80, true);
    timerAttachInterrupt(timer, &onTimer, true);
    updateTimerFrequency();
    timerAlarmEnable(timer);

    Serial.printf("Pulley: %dT × %.1fmm = %.1fmm/rev\n", TEETH, PITCH_MM, CIRC_MM);
    Serial.printf("Resolution: %.5f in/count\n", IN_PER_COUNT);
    Serial.printf("Motor: %.1f steps/mm, %.1f steps/in\n", STEPS_PER_MM, STEPS_PER_IN);
    Serial.printf("Default velocity: %.2f in/s\n", motor.velocity_ips);
    Serial.printf("Closed-loop: %s\n", motor.closed_loop_enabled ? "ENABLED" : "DISABLED");
    Serial.println("========================================");
    Serial.println("Commands: g<pos>, h, s, v<vel>, r, ?");
    Serial.println("========================================\n");
    Serial.println("READY");
}

// ========== Main Loop ==========
void loop() {
    uint32_t now = millis();

    // Update encoder reading
    updateEncoder();
    updateResetButton();

    // Check for motion completion
    if (motor.motion_complete_flag) {
        motor.motion_complete_flag = false;

        // Perform closed-loop correction if enabled
        if (motor.closed_loop_enabled) {
            closedLoopCorrection();
        } else {
            float pos_in = motor.current_steps / STEPS_PER_IN;
            char msg[64];
            snprintf(msg, sizeof(msg), "AT_TARGET %.3f", pos_in);
            sendResponse(msg);
        }
    }

    // Send periodic status updates (10 Hz)
    if (now - last_status_ms >= STATUS_UPDATE_MS) {
        last_status_ms = now;
        sendStatusUpdate();
    }

    // Process serial commands
    processSerialCommand();

    delay(2);
}

// ========== Closed-Loop Position Correction ==========
void closedLoopCorrection() {
    if (CORRECTION_SETTLE_MS > 0) {
        delay(CORRECTION_SETTLE_MS);
    }

    // Read actual position from encoder
    float actual_pos = encoder.position_in;
    float error_in = motor.target_position_in - actual_pos;

    // Check if within tolerance
    if (fabs(error_in) <= POSITION_TOLERANCE_IN) {
        char msg[64];
        snprintf(msg, sizeof(msg), "AT_TARGET %.3f (error: %.4f in)", actual_pos, error_in);
        sendResponse(msg);
        return;
    }

    // Check for excessive error (mechanical problem)
    if (fabs(error_in) > MAX_POSITION_ERROR_IN) {
        char msg[128];
        snprintf(msg, sizeof(msg), "ERROR Position error too large: %.3f in (target: %.3f, actual: %.3f)",
                 error_in, motor.target_position_in, actual_pos);
        sendResponse(msg);
        stop();
        return;
    }

    syncMotorStepsWithEncoder();

    // Send correction move
    char msg[128];
    snprintf(msg, sizeof(msg), "CORRECTING error: %.4f in, moving to %.3f",
             error_in, motor.target_position_in);
    sendResponse(msg);

    // Calculate correction in steps
    int32_t correction_steps = (int32_t)(error_in * STEPS_PER_IN);
    motor.target_steps = motor.current_steps + correction_steps;

    // Set direction
    if (correction_steps > 0) {
        motor.direction = true;
        digitalWrite(M3_DIR_PIN, HIGH);
    } else {
        motor.direction = false;
        digitalWrite(M3_DIR_PIN, LOW);
    }

    motor.velocity_ips = motor.base_velocity_ips;
    float correction_vel = motor.base_velocity_ips * CORRECTION_VELOCITY_SCALE;
    if (correction_vel < MIN_CORRECTION_VEL_IPS) {
        correction_vel = MIN_CORRECTION_VEL_IPS;
    }
    motor.velocity_ips = correction_vel;
    updateTimerFrequency();
    motor.in_motion = true;
}

// ========== Serial Command Processing ==========
void processSerialCommand() {
    if (!Serial.available()) return;

    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() == 0) return;

    Serial.print("CMD ");
    Serial.println(cmd);

    char command = cmd.charAt(0);
    String arg = cmd.substring(1);

    switch (command) {
        case 'g':
        case 'G': {
            float pos = arg.toFloat();
            gotoPosition(pos);
            break;
        }

        case 'h':
        case 'H':
            home();
            break;

        case 's':
        case 'S':
            stop();
            break;

        case 'v':
        case 'V': {
            float vel = arg.toFloat();
            setVelocity(vel);
            break;
        }

        case 'r':
        case 'R':
            resetEncoder();
            break;

        case 'i':
        case 'I':
            sendResponse("ID:ESP32B");
            break;

        case '?':
            queryStatus();
            break;

        default:
            sendResponse("ERROR Unknown command");
            break;
    }
}

// ========== Helper: Send Response ==========
void sendResponse(const char* msg) {
    Serial.println(msg);
    Serial.flush();
}

// ========== Status Update (10 Hz) ==========
void sendStatusUpdate() {
    // Format: POS <encoder_in> <velocity_ips> <encoder_counts> <motor_steps>
    char msg[128];
    if (encoder.detected) {
        snprintf(msg, sizeof(msg), "POS %.3f %.3f %ld %ld",
                 encoder.position_in,
                 encoder.velocity_ema_ips,
                 (long)readEncoderCount(),
                 motor.current_steps);
    } else {
        float pos_in = motor.current_steps / STEPS_PER_IN;
        snprintf(msg, sizeof(msg), "POS %.3f 0.000 0 %ld",
                 pos_in, motor.current_steps);
    }
    sendResponse(msg);
}

// ========== Timer Frequency Update ==========
void updateTimerFrequency() {
    float step_rate = motor.velocity_ips * STEPS_PER_IN;
    if (step_rate < 10.0) step_rate = 10.0;
    motor.step_interval_us = (uint32_t)(1000000.0 / step_rate);
    timerAlarmWrite(timer, motor.step_interval_us / 2, true);
}

// ========== Motion Control Functions ==========
void gotoPosition(float position_in) {
    motor.target_position_in = position_in;
    float actual_pos = encoder.detected ? encoder.position_in : (motor.current_steps / STEPS_PER_IN);
    if (encoder.detected) {
        syncMotorStepsWithEncoder();
    }
    float error_in = position_in - actual_pos;
    if (fabs(error_in) <= POSITION_TOLERANCE_IN) {
        char msg[64];
        snprintf(msg, sizeof(msg), "AT_TARGET %.3f", actual_pos);
        sendResponse(msg);
        return;
    }

    motor.target_steps = motor.current_steps + (int32_t)(error_in * STEPS_PER_IN);

    // Set direction
    if (error_in > 0) {
        motor.direction = true;
        digitalWrite(M3_DIR_PIN, HIGH);
    } else {
        motor.direction = false;
        digitalWrite(M3_DIR_PIN, LOW);
    }

    updateTimerFrequency();
    motor.in_motion = true;

    char msg[128];
    float current_in = motor.current_steps / STEPS_PER_IN;
    if (encoder.detected) {
        snprintf(msg, sizeof(msg), "MOVING encoder: %.3f -> %.3f",
                 encoder.position_in, position_in);
    } else {
        snprintf(msg, sizeof(msg), "MOVING %.3f -> %.3f", current_in, position_in);
    }
    sendResponse(msg);
}

void home() {
    motor.current_steps = 0;
    motor.target_steps = 0;
    motor.target_position_in = 0.0f;
    motor.in_motion = false;
    if (encoder.detected) {
        syncMotorStepsWithEncoder();
    }
    resetEncoder();
    sendResponse("HOMED");
}

void stop() {
    motor.in_motion = false;
    float motor_pos_in = motor.current_steps / STEPS_PER_IN;
    char msg[128];
    if (encoder.detected) {
        snprintf(msg, sizeof(msg), "STOPPED motor: %.3f, encoder: %.3f",
                 motor_pos_in, encoder.position_in);
    } else {
        snprintf(msg, sizeof(msg), "STOPPED %.3f", motor_pos_in);
    }
    sendResponse(msg);
}

void setVelocity(float vel_ips) {
    if (vel_ips <= 0) {
        sendResponse("ERROR Velocity must be > 0");
        return;
    }

    motor.base_velocity_ips = vel_ips;
    motor.velocity_ips = vel_ips;

    if (motor.in_motion) {
        updateTimerFrequency();
    }

    char msg[64];
    snprintf(msg, sizeof(msg), "VELOCITY %.2f", vel_ips);
    sendResponse(msg);
}

void queryStatus() {
    char msg[256];

    if (encoder.detected) {
        float motor_pos_in = motor.current_steps / STEPS_PER_IN;
        float error_in = encoder.position_in - motor_pos_in;

        snprintf(msg, sizeof(msg),
                 "STATUS %s | Motor: %.3f in (%ld steps) | Encoder: %.3f in (%ld counts) | Error: %.4f in | Vel: %.2f in/s | Target: %.3f in",
                 motor.in_motion ? "MOVING" : "IDLE",
                 motor_pos_in, motor.current_steps,
                 encoder.position_in, (long)readEncoderCount(),
                 error_in,
                 motor.velocity_ips,
                 motor.target_position_in);
    } else {
        float motor_pos_in = motor.current_steps / STEPS_PER_IN;
        snprintf(msg, sizeof(msg),
                 "STATUS %s | Motor: %.3f in (%ld steps) | Encoder: NOT DETECTED | Vel: %.2f in/s | Target: %.3f in",
                 motor.in_motion ? "MOVING" : "IDLE",
                 motor_pos_in, motor.current_steps,
                 motor.velocity_ips,
                 motor.target_position_in);
    }

    sendResponse(msg);
}
