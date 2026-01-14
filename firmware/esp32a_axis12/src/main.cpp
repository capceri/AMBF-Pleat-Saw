/**
 * ESP32-A Firmware v2.0: Blade (M1) + Fixture (M2) USB Serial Controller
 *
 * Controls two motors over USB Serial (converted from Modbus/RS-485).
 * - M1: Blade spindle (step/dir, RPM control)
 * - M2: Fixture feed (step/dir, position/velocity control)
 *
 * Hardware:
 * - Motor1 blade: STEP=GPIO32, DIR=GPIO33
 * - Motor2 fixture: STEP=GPIO25, DIR=GPIO26
 * - USB Serial: 115200 baud
 *
 * Protocol:
 * - I or i: ID query → "ID:ESP32A"
 * - ?: Query status → "M1 <status> <rpm> | M2 <status> <vel>"
 * - 1r<rpm>: M1 run at RPM (e.g., "1r3500")
 * - 1s: M1 stop
 * - 2f: M2 feed forward
 * - 2b: M2 feed reverse (back)
 * - 2s: M2 stop
 * - 2v<velocity>: M2 set velocity mm/s (e.g., "2v120.5")
 */

#include <Arduino.h>
#include "driver/mcpwm.h"

// ========== Hardware Pin Definitions ==========

// M1 Blade Motor
#define M1_STEP_PIN     32
#define M1_DIR_PIN      33

// M2 Fixture Motor
#define M2_STEP_PIN     25
#define M2_DIR_PIN      26
#define M2_HOME_PIN     2

// ========== Motor Parameters ==========

#define M1_PULSES_PER_REV   22333   // Calibrated from testing
#define M1_DIR_CW           false   // Direction reversed
#define MAX_FREQ_HZ         375000.0

#define M2_PULSES_PER_REV   5000
#define M2_DIR_FWD          false   // Direction reversed  
#define M2_STEPS_PER_MM     750.0   // 5000 × 1.5 gear / 10mm leadscrew

#define PWM_DUTY_CYCLE      50.0
#define MIN_FREQ_HZ         1.0

// ========== Global State ==========

struct {
    bool running;
    uint16_t rpm;
    double freq_hz;
} m1;

struct {
    bool in_motion;
    bool direction_fwd;
    double vel_mm_s;
    double freq_hz;
} m2;

uint32_t heartbeat_counter = 0;
unsigned long last_status_ms = 0;

// ========== Function Prototypes ==========

void processSerialCommand();
void m1_set_rpm(uint16_t rpm);
void m1_stop();
void m2_feed_forward();
void m2_feed_reverse();
void m2_stop();
void m2_set_velocity(double vel_mm_s);
bool is_m2_home_active();
void m2_check_home_stop();
void queryStatus();
void sendResponse(const char* msg);
void m1_pwm_set_frequency(double freq_hz);
void m1_pwm_enable(bool enable);
void m2_pwm_set_frequency(double freq_hz);
void m2_pwm_enable(bool enable);

// ========== Setup ==========

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\nESP32-A: Blade + Fixture USB Serial Controller");
    Serial.println("Firmware v2.0");

    // Configure GPIO
    pinMode(M1_DIR_PIN, OUTPUT);
    pinMode(M2_DIR_PIN, OUTPUT);
    pinMode(M2_HOME_PIN, INPUT_PULLUP);
    digitalWrite(M1_DIR_PIN, M1_DIR_CW ? HIGH : LOW);
    digitalWrite(M2_DIR_PIN, LOW);

    // Initialize state
    memset(&m1, 0, sizeof(m1));
    memset(&m2, 0, sizeof(m2));

    // Setup MCPWM for M1 (Unit 0, Timer 0)
    mcpwm_gpio_init(MCPWM_UNIT_0, MCPWM0A, M1_STEP_PIN);
    mcpwm_config_t pwm_config_m1;
    pwm_config_m1.frequency = 1000;
    pwm_config_m1.cmpr_a = 0;
    pwm_config_m1.duty_mode = MCPWM_DUTY_MODE_0;
    pwm_config_m1.counter_mode = MCPWM_UP_COUNTER;
    mcpwm_init(MCPWM_UNIT_0, MCPWM_TIMER_0, &pwm_config_m1);
    mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A, 0);
    mcpwm_set_signal_low(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A);

    // Setup MCPWM for M2 (Unit 0, Timer 1)
    mcpwm_gpio_init(MCPWM_UNIT_0, MCPWM1A, M2_STEP_PIN);
    mcpwm_config_t pwm_config_m2;
    pwm_config_m2.frequency = 1000;
    pwm_config_m2.cmpr_a = 0;
    pwm_config_m2.duty_mode = MCPWM_DUTY_MODE_0;
    pwm_config_m2.counter_mode = MCPWM_UP_COUNTER;
    mcpwm_init(MCPWM_UNIT_0, MCPWM_TIMER_1, &pwm_config_m2);
    mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A, 0);
    mcpwm_set_signal_low(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A);

    Serial.println("Initialization complete");
    Serial.println("Ready for commands (send 'I' for ID, '?' for status)");
}

// ========== Main Loop ==========

void loop() {
    processSerialCommand();
    m2_check_home_stop();

    // Send status update every 100ms
    unsigned long now = millis();
    if (now - last_status_ms >= 100) {
        last_status_ms = now;
        heartbeat_counter++;
    }

    yield();
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

    switch (command) {
        case 'i':
        case 'I':
            sendResponse("ID:ESP32A");
            break;

        case '?':
            queryStatus();
            break;

        case '1': {  // M1 commands
            char subcmd = cmd.charAt(1);
            String arg = cmd.substring(2);
            
            if (subcmd == 'r' || subcmd == 'R') {
                uint16_t rpm = arg.toInt();
                m1_set_rpm(rpm);
            } else if (subcmd == 's' || subcmd == 'S') {
                m1_stop();
            } else {
                sendResponse("ERROR M1 unknown subcommand");
            }
            break;
        }

        case '2': {  // M2 commands
            char subcmd = cmd.charAt(1);
            String arg = cmd.substring(2);
            
            if (subcmd == 'f' || subcmd == 'F') {
                m2_feed_forward();
            } else if (subcmd == 'b' || subcmd == 'B') {
                m2_feed_reverse();
            } else if (subcmd == 's' || subcmd == 'S') {
                m2_stop();
            } else if (subcmd == 'v' || subcmd == 'V') {
                double vel = arg.toFloat();
                m2_set_velocity(vel);
            } else {
                sendResponse("ERROR M2 unknown subcommand");
            }
            break;
        }

        default:
            sendResponse("ERROR Unknown command");
            break;
    }
}

// ========== M1 Control Functions ==========

void m1_set_rpm(uint16_t rpm) {
    if (rpm < 100 || rpm > 6000) {
        sendResponse("ERROR M1 RPM out of range (100-6000)");
        return;
    }

    m1.rpm = rpm;
    m1.freq_hz = (double)rpm * M1_PULSES_PER_REV / 60.0;
    
    if (m1.freq_hz > MAX_FREQ_HZ) {
        m1.freq_hz = MAX_FREQ_HZ;
    }

    m1_pwm_set_frequency(m1.freq_hz);
    m1_pwm_enable(true);
    m1.running = true;

    char msg[64];
    snprintf(msg, sizeof(msg), "M1_RUN rpm=%d freq=%.1f", rpm, m1.freq_hz);
    sendResponse(msg);
}

void m1_stop() {
    m1_pwm_enable(false);
    m1.running = false;
    m1.freq_hz = 0;
    sendResponse("M1_STOPPED");
}

// ========== M2 Control Functions ==========

void m2_feed_forward() {
    digitalWrite(M2_DIR_PIN, M2_DIR_FWD ? HIGH : LOW);
    m2.direction_fwd = true;
    m2.in_motion = true;
    
    if (m2.vel_mm_s == 0) {
        m2.vel_mm_s = 120.0;  // Default velocity
    }
    
    m2.freq_hz = m2.vel_mm_s * M2_STEPS_PER_MM;
    m2_pwm_set_frequency(m2.freq_hz);
    m2_pwm_enable(true);
    
    sendResponse("M2_FWD");
}

void m2_feed_reverse() {
    if (is_m2_home_active()) {
        sendResponse("ERROR M2_HOME_ACTIVE");
        return;
    }

    digitalWrite(M2_DIR_PIN, M2_DIR_FWD ? LOW : HIGH);
    m2.direction_fwd = false;
    m2.in_motion = true;
    
    if (m2.vel_mm_s == 0) {
        m2.vel_mm_s = 120.0;  // Default velocity
    }
    
    m2.freq_hz = m2.vel_mm_s * M2_STEPS_PER_MM;
    m2_pwm_set_frequency(m2.freq_hz);
    m2_pwm_enable(true);
    
    sendResponse("M2_REV");
}

void m2_stop() {
    m2_pwm_enable(false);
    m2.in_motion = false;
    m2.freq_hz = 0;
    sendResponse("M2_STOPPED");
}

void m2_set_velocity(double vel_mm_s) {
    if (vel_mm_s < 1.0 || vel_mm_s > 400.0) {
        sendResponse("ERROR M2 velocity out of range (1-400 mm/s)");
        return;
    }

    m2.vel_mm_s = vel_mm_s;

    // If already in motion, update frequency
    if (m2.in_motion) {
        m2.freq_hz = m2.vel_mm_s * M2_STEPS_PER_MM;
        m2_pwm_set_frequency(m2.freq_hz);
    }

    char msg[64];
    snprintf(msg, sizeof(msg), "M2_VEL_SET vel=%.1f", vel_mm_s);
    sendResponse(msg);
}

bool is_m2_home_active() {
    return digitalRead(M2_HOME_PIN) == LOW;
}

void m2_check_home_stop() {
    if (m2.in_motion && !m2.direction_fwd && is_m2_home_active()) {
        m2_stop();
    }
}

// ========== Status Query ==========

void queryStatus() {
    char msg[128];
    snprintf(msg, sizeof(msg), "STATUS M1:%s rpm=%d | M2:%s vel=%.1f dir=%s",
             m1.running ? "RUN" : "STOP",
             m1.rpm,
             m2.in_motion ? "MOVING" : "STOP",
             m2.vel_mm_s,
             m2.direction_fwd ? "FWD" : "REV");
    sendResponse(msg);
}

// ========== Helper Functions ==========

void sendResponse(const char* msg) {
    Serial.println(msg);
    Serial.flush();
}

void m1_pwm_set_frequency(double freq_hz) {
    if (freq_hz < MIN_FREQ_HZ) freq_hz = MIN_FREQ_HZ;
    if (freq_hz > MAX_FREQ_HZ) freq_hz = MAX_FREQ_HZ;

    uint32_t period_us = (uint32_t)(1000000.0 / freq_hz);
    mcpwm_set_frequency(MCPWM_UNIT_0, MCPWM_TIMER_0, (uint32_t)freq_hz);
}

void m1_pwm_enable(bool enable) {
    if (enable) {
        mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A, PWM_DUTY_CYCLE);
        mcpwm_set_duty_type(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A, MCPWM_DUTY_MODE_0);
    } else {
        mcpwm_set_signal_low(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A);
        mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_0, MCPWM_OPR_A, 0);
    }
}

void m2_pwm_set_frequency(double freq_hz) {
    if (freq_hz < MIN_FREQ_HZ) freq_hz = MIN_FREQ_HZ;
    if (freq_hz > MAX_FREQ_HZ) freq_hz = MAX_FREQ_HZ;

    mcpwm_set_frequency(MCPWM_UNIT_0, MCPWM_TIMER_1, (uint32_t)freq_hz);
}

void m2_pwm_enable(bool enable) {
    if (enable) {
        mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A, PWM_DUTY_CYCLE);
        mcpwm_set_duty_type(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A, MCPWM_DUTY_MODE_0);
    } else {
        mcpwm_set_signal_low(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A);
        mcpwm_set_duty(MCPWM_UNIT_0, MCPWM_TIMER_1, MCPWM_OPR_A, 0);
    }
}
