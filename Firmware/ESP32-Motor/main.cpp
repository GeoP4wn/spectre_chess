/**
 * ESP32 Motor Controller Firmware
 * 
 * Responsibilities:
 * - Control 2x TMC2226 stepper drivers for H-Bot gantry system
 * - Electromagnet control (4x electromagnets via MOSFETs)
 * - Limit switch homing
 * - PWM fan control (4x fans)
 * - Communicate with Raspberry Pi via UART (JSON protocol)
 * 
 * Hardware:
 * - ESP32-S3 DevKit C-1
 * - 2x TMC2226 stepper drivers
 * - 2x NEMA17 stepper motors (0.7A)
 * - 4x P25/20 electromagnets (12V)
 * - 4x IRFL44N MOSFETs for electromagnet switching
 * - 1x Limit switch (for homing)
 * - 4x Arctic S4028-6K fans (40mm, PWM)
 * - TXS0108E Level Shifter for fan PWM
 * 
 * H-Bot Kinematics:
 * - Both motors affect both X and Y
 * - Motor A forward + Motor B forward = Move +X
 * - Motor A forward + Motor B backward = Move +Y
 */

#include <Arduino.h>
#include <TMCStepper.h>
#include <ArduinoJson.h>

// ==================== PIN DEFINITIONS ====================

// TMC2226 Motor Drivers
// Motor A (X-axis component)
#define MOTOR_A_STEP_PIN    2
#define MOTOR_A_DIR_PIN     3
#define MOTOR_A_EN_PIN      4
#define MOTOR_A_TX_PIN      5   // ESP32 TX to TMC2226
#define MOTOR_A_RX_PIN      6   // ESP32 RX from TMC2226

// Motor B (Y-axis component)
#define MOTOR_B_STEP_PIN    7
#define MOTOR_B_DIR_PIN     8
#define MOTOR_B_EN_PIN      9
#define MOTOR_B_TX_PIN      10  // ESP32 TX to TMC2226
#define MOTOR_B_RX_PIN      11  // ESP32 RX from TMC2226

// Electromagnets (via MOSFETs, active HIGH)
#define MAGNET_1_PIN        16
#define MAGNET_2_PIN        17
#define MAGNET_3_PIN        18
#define MAGNET_4_PIN        19

// Limit switch (active LOW with pullup)
#define LIMIT_SWITCH_PIN    32

// PWM Fan control (via level shifter to 5V)
#define FAN_1_PIN           25
#define FAN_2_PIN           26
#define FAN_3_PIN           27
#define FAN_4_PIN           33

// UART communication with Raspberry Pi
#define UART_RX_PIN         1   // RX from Pi
#define UART_TX_PIN         3   // TX to Pi
#define UART_BAUD           115200

// ==================== MOTOR CONFIGURATION ====================

// TMC2226 UART addresses (set via MS1_AD0 and MS2_AD1 pins on driver)
#define MOTOR_A_ADDRESS     0b00  // Both MS pins LOW
#define MOTOR_B_ADDRESS     0b01  // MS1_AD0 HIGH, MS2_AD1 LOW

// Stepper motor specs
#define STEPS_PER_REV       200     // 1.8° stepper
#define MICROSTEPS          16      // TMC2226 microstepping
#define STEPS_PER_MM        80      // Steps per mm (configure based on pulley size)

// Speed settings (steps/second)
#define DEFAULT_SPEED       2000    // Default movement speed
#define MAX_SPEED           8000    // Maximum speed
#define HOMING_SPEED        500     // Slower speed for homing
#define ACCELERATION        2000    // Steps/second²

// Current limits (RMS current in mA)
#define MOTOR_CURRENT_RUN   500     // 0.7A * 0.707 ≈ 500mA RMS
#define MOTOR_CURRENT_HOLD  200     // Lower current when holding

// Board dimensions (in mm)
#define MAX_X_MM            400.0
#define MAX_Y_MM            400.0

// ==================== GLOBAL VARIABLES ====================

// Hardware Serial for TMC2226 communication
// Using Serial2 with separate TX and RX pins
HardwareSerial MotorSerial(2);  // Use UART2

// TMC2226 driver instances
TMC2226Stepper driverA(&MotorSerial, 0.11f, MOTOR_A_ADDRESS);
TMC2226Stepper driverB(&MotorSerial, 0.11f, MOTOR_B_ADDRESS);

// Current position (in steps)
long currentStepsX = 0;
long currentStepsY = 0;

// Current position (in mm)
float currentPosX = 0.0;
float currentPosY = 0.0;

// Target position
long targetStepsX = 0;
long targetStepsY = 0;

// Movement state
bool isMoving = false;
bool isHomed = false;

// Speed and acceleration
float currentSpeed = DEFAULT_SPEED;
unsigned long stepDelay = 1000000 / DEFAULT_SPEED; // microseconds

// Electromagnet states
bool magnetStates[4] = {false, false, false, false};

// JSON buffer
StaticJsonDocument<2048> jsonDoc;
String inputBuffer = "";

// Timing
unsigned long lastStepTime = 0;

// ==================== FUNCTION DECLARATIONS ====================

void setupPins();
void setupMotorDrivers();
void homeGantry();
void moveToAbsolute(float targetX, float targetY);
void moveRelative(float deltaX, float deltaY);
void stepMotors();
void calculateHBotSteps(long targetX, long targetY, long& stepsA, long& stepsB);
void setMagnet(int magnetIndex, bool state);
void setAllMagnets(bool state);
void setFanSpeed(int fanIndex, int pwmValue);
void processUARTCommand();
void sendStatus(const char* status, const char* message = nullptr);
void sendPositionUpdate();

// ==================== SETUP ====================

void setup() {
    // Initialize serial for debugging
    Serial.begin(115200);
    Serial.println("\n\n=== ESP32 Motor Controller Starting ===");
    
    // Initialize UART for Pi communication
    Serial1.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
    
    // Initialize UART for TMC2226 drivers (both share same UART bus)
    // Motor A TX connects to both drivers' PDN_UART via 1kΩ resistors
    // Motor A RX also connects (for reading back status)
    MotorSerial.begin(115200, SERIAL_8N1, MOTOR_A_RX_PIN, MOTOR_A_TX_PIN);
    
    // Setup hardware
    setupPins();
    setupMotorDrivers();
    
    Serial.println("Setup complete. Ready for commands.");
    
    // Send ready signal to Pi
    sendStatus("ready", "Motor controller initialized");
}

// ==================== MAIN LOOP ====================

void loop() {
    // Execute movement if in motion
    if (isMoving) {
        stepMotors();
    }
    
    // Process UART commands from Pi
    while (Serial1.available()) {
        char c = Serial1.read();
        
        if (c == '\n') {
            processUARTCommand();
            inputBuffer = "";
        } else {
            inputBuffer += c;
        }
    }
}

// ==================== PIN SETUP ====================

void setupPins() {
    // Motor control pins
    pinMode(MOTOR_A_STEP_PIN, OUTPUT);
    pinMode(MOTOR_A_DIR_PIN, OUTPUT);
    pinMode(MOTOR_A_EN_PIN, OUTPUT);
    
    pinMode(MOTOR_B_STEP_PIN, OUTPUT);
    pinMode(MOTOR_B_DIR_PIN, OUTPUT);
    pinMode(MOTOR_B_EN_PIN, OUTPUT);
    
    // Enable motors (active LOW)
    digitalWrite(MOTOR_A_EN_PIN, LOW);
    digitalWrite(MOTOR_B_EN_PIN, LOW);
    
    // Electromagnet pins
    pinMode(MAGNET_1_PIN, OUTPUT);
    pinMode(MAGNET_2_PIN, OUTPUT);
    pinMode(MAGNET_3_PIN, OUTPUT);
    pinMode(MAGNET_4_PIN, OUTPUT);
    
    // Ensure all magnets off
    setAllMagnets(false);
    
    // Limit switch
    pinMode(LIMIT_SWITCH_PIN, INPUT_PULLUP);
    
    // Fan PWM pins
    pinMode(FAN_1_PIN, OUTPUT);
    pinMode(FAN_2_PIN, OUTPUT);
    pinMode(FAN_3_PIN, OUTPUT);
    pinMode(FAN_4_PIN, OUTPUT);
    
    // Configure PWM for fans (25kHz, common for PC fans)
    ledcSetup(0, 25000, 8); // Channel 0, 25kHz, 8-bit resolution
    ledcSetup(1, 25000, 8);
    ledcSetup(2, 25000, 8);
    ledcSetup(3, 25000, 8);
    
    ledcAttachPin(FAN_1_PIN, 0);
    ledcAttachPin(FAN_2_PIN, 1);
    ledcAttachPin(FAN_3_PIN, 2);
    ledcAttachPin(FAN_4_PIN, 3);
    
    // Start fans at 50% speed
    for (int i = 0; i < 4; i++) {
        setFanSpeed(i, 128);
    }
    
    Serial.println("Pins configured");
}

// ==================== TMC2226 SETUP ====================

void setupMotorDrivers() {
    Serial.println("Configuring TMC2226 drivers...");
    
    // Driver A configuration
    driverA.begin();
    driverA.toff(5);                    // Enable driver
    driverA.rms_current(MOTOR_CURRENT_RUN); // Set RMS current
    driverA.microsteps(MICROSTEPS);     // Set microstepping
    driverA.pwm_autoscale(true);        // Enable automatic current scaling
    driverA.en_spreadCycle(false);      // Use StealthChop (quieter)
    
    // Driver B configuration
    driverB.begin();
    driverB.toff(5);
    driverB.rms_current(MOTOR_CURRENT_RUN);
    driverB.microsteps(MICROSTEPS);
    driverB.pwm_autoscale(true);
    driverB.en_spreadCycle(false);
    
    Serial.println("TMC2226 drivers configured");
    
    // Test: Read back configuration
    Serial.print("Driver A current: ");
    Serial.println(driverA.rms_current());
    Serial.print("Driver B current: ");
    Serial.println(driverB.rms_current());
}

// ==================== HOMING ====================

void homeGantry() {
    Serial.println("Starting homing sequence...");
    
    isHomed = false;
    
    // Move towards limit switch until triggered
    // Assuming limit switch is at (0, 0)
    
    digitalWrite(MOTOR_A_DIR_PIN, LOW);  // Reverse direction
    digitalWrite(MOTOR_B_DIR_PIN, LOW);
    
    // Move slowly until limit switch triggers
    while (digitalRead(LIMIT_SWITCH_PIN) == HIGH) {
        // Step both motors
        digitalWrite(MOTOR_A_STEP_PIN, HIGH);
        digitalWrite(MOTOR_B_STEP_PIN, HIGH);
        delayMicroseconds(5);
        digitalWrite(MOTOR_A_STEP_PIN, LOW);
        digitalWrite(MOTOR_B_STEP_PIN, LOW);
        delayMicroseconds(1000000 / HOMING_SPEED);
    }
    
    Serial.println("Limit switch triggered");
    
    // Back off slightly
    digitalWrite(MOTOR_A_DIR_PIN, HIGH);
    digitalWrite(MOTOR_B_DIR_PIN, HIGH);
    
    for (int i = 0; i < 100; i++) {
        digitalWrite(MOTOR_A_STEP_PIN, HIGH);
        digitalWrite(MOTOR_B_STEP_PIN, HIGH);
        delayMicroseconds(5);
        digitalWrite(MOTOR_A_STEP_PIN, LOW);
        digitalWrite(MOTOR_B_STEP_PIN, LOW);
        delayMicroseconds(1000000 / HOMING_SPEED);
    }
    
    // Set current position as (0, 0)
    currentStepsX = 0;
    currentStepsY = 0;
    currentPosX = 0.0;
    currentPosY = 0.0;
    
    isHomed = true;
    
    Serial.println("Homing complete");
    sendStatus("homed", "Gantry homed to (0, 0)");
}

// ==================== MOVEMENT ====================

void moveToAbsolute(float targetX, float targetY) {
    if (!isHomed) {
        Serial.println("ERROR: Cannot move - not homed");
        sendStatus("error", "Gantry not homed");
        return;
    }
    
    // Constrain to board limits
    targetX = constrain(targetX, 0, MAX_X_MM);
    targetY = constrain(targetY, 0, MAX_Y_MM);
    
    Serial.print("Moving to (");
    Serial.print(targetX);
    Serial.print(", ");
    Serial.print(targetY);
    Serial.println(")");
    
    // Convert mm to steps
    targetStepsX = (long)(targetX * STEPS_PER_MM);
    targetStepsY = (long)(targetY * STEPS_PER_MM);
    
    isMoving = true;
}

void moveRelative(float deltaX, float deltaY) {
    moveToAbsolute(currentPosX + deltaX, currentPosY + deltaY);
}

void stepMotors() {
    // Calculate remaining distance
    long remainingX = targetStepsX - currentStepsX;
    long remainingY = targetStepsY - currentStepsY;
    
    // Check if we've reached target
    if (remainingX == 0 && remainingY == 0) {
        isMoving = false;
        sendPositionUpdate();
        Serial.println("Movement complete");
        return;
    }
    
    // Calculate H-Bot motor directions
    // H-Bot kinematics:
    // Motor A: controls X + Y diagonal
    // Motor B: controls X - Y diagonal
    //
    // To move +X: A forward, B forward
    // To move +Y: A forward, B backward
    
    long stepsA = remainingX + remainingY;  // A motor steps
    long stepsB = remainingX - remainingY;  // B motor steps
    
    // Set motor directions
    digitalWrite(MOTOR_A_DIR_PIN, stepsA > 0 ? HIGH : LOW);
    digitalWrite(MOTOR_B_DIR_PIN, stepsB > 0 ? HIGH : LOW);
    
    // Step motors
    unsigned long currentTime = micros();
    if (currentTime - lastStepTime >= stepDelay) {
        // Step motor A if needed
        if (stepsA != 0) {
            digitalWrite(MOTOR_A_STEP_PIN, HIGH);
            delayMicroseconds(5);
            digitalWrite(MOTOR_A_STEP_PIN, LOW);
            currentStepsX += (stepsA > 0) ? 1 : -1;
        }
        
        // Step motor B if needed
        if (stepsB != 0) {
            digitalWrite(MOTOR_B_STEP_PIN, HIGH);
            delayMicroseconds(5);
            digitalWrite(MOTOR_B_STEP_PIN, LOW);
            // Y component is difference in motor steps
            if (stepsA == 0) {
                currentStepsY += (stepsB > 0) ? -1 : 1;
            } else {
                currentStepsY += (remainingY > 0) ? 1 : -1;
            }
        }
        
        // Update current position in mm
        currentPosX = (float)currentStepsX / STEPS_PER_MM;
        currentPosY = (float)currentStepsY / STEPS_PER_MM;
        
        lastStepTime = currentTime;
    }
}

// ==================== ELECTROMAGNET CONTROL ====================

void setMagnet(int magnetIndex, bool state) {
    if (magnetIndex < 0 || magnetIndex >= 4) return;
    
    int pins[] = {MAGNET_1_PIN, MAGNET_2_PIN, MAGNET_3_PIN, MAGNET_4_PIN};
    
    digitalWrite(pins[magnetIndex], state ? HIGH : LOW);
    magnetStates[magnetIndex] = state;
    
    Serial.print("Magnet ");
    Serial.print(magnetIndex + 1);
    Serial.println(state ? " ON" : " OFF");
}

void setAllMagnets(bool state) {
    for (int i = 0; i < 4; i++) {
        setMagnet(i, state);
    }
}

// ==================== FAN CONTROL ====================

void setFanSpeed(int fanIndex, int pwmValue) {
    if (fanIndex < 0 || fanIndex >= 4) return;
    
    pwmValue = constrain(pwmValue, 0, 255);
    ledcWrite(fanIndex, pwmValue);
    
    Serial.print("Fan ");
    Serial.print(fanIndex + 1);
    Serial.print(" speed: ");
    Serial.println(pwmValue);
}

// ==================== UART COMMAND PROCESSING ====================

void processUARTCommand() {
    // Parse JSON command
    DeserializationError error = deserializeJson(jsonDoc, inputBuffer);
    
    if (error) {
        Serial.print("JSON parse error: ");
        Serial.println(error.c_str());
        return;
    }
    
    JsonObject cmd = jsonDoc.as<JsonObject>();
    const char* cmdType = cmd["cmd"];
    
    if (cmdType == nullptr) {
        Serial.println("No 'cmd' field in JSON");
        return;
    }
    
    // Route command
    if (strcmp(cmdType, "home") == 0) {
        homeGantry();
    }
    else if (strcmp(cmdType, "move_absolute") == 0) {
        float x = cmd["x"] | 0.0;
        float y = cmd["y"] | 0.0;
        
        if (cmd.containsKey("speed")) {
            currentSpeed = cmd["speed"];
            stepDelay = 1000000 / currentSpeed;
        }
        
        moveToAbsolute(x, y);
    }
    else if (strcmp(cmdType, "move_relative") == 0) {
        float dx = cmd["dx"] | 0.0;
        float dy = cmd["dy"] | 0.0;
        moveRelative(dx, dy);
    }
    else if (strcmp(cmdType, "magnet_on") == 0) {
        if (cmd.containsKey("magnet")) {
            int magnet = cmd["magnet"];
            setMagnet(magnet - 1, true);
        } else {
            setAllMagnets(true);
        }
    }
    else if (strcmp(cmdType, "magnet_off") == 0) {
        if (cmd.containsKey("magnet")) {
            int magnet = cmd["magnet"];
            setMagnet(magnet - 1, false);
        } else {
            setAllMagnets(false);
        }
    }
    else if (strcmp(cmdType, "set_fan") == 0) {
        int fan = cmd["fan"] | 1;
        int speed = cmd["speed"] | 128;
        setFanSpeed(fan - 1, speed);
    }
    else if (strcmp(cmdType, "stop") == 0) {
        isMoving = false;
        targetStepsX = currentStepsX;
        targetStepsY = currentStepsY;
        sendStatus("stopped", "Movement stopped");
    }
    else if (strcmp(cmdType, "get_position") == 0) {
        sendPositionUpdate();
    }
    else {
        Serial.print("Unknown command: ");
        Serial.println(cmdType);
    }
}

// ==================== STATUS REPORTING ====================

void sendStatus(const char* status, const char* message) {
    jsonDoc.clear();
    jsonDoc["type"] = "status";
    jsonDoc["status"] = status;
    jsonDoc["controller"] = "motor";
    
    if (message) {
        jsonDoc["message"] = message;
    }
    
    serializeJson(jsonDoc, Serial1);
    Serial1.println();
}

void sendPositionUpdate() {
    jsonDoc.clear();
    jsonDoc["type"] = "position";
    jsonDoc["x"] = currentPosX;
    jsonDoc["y"] = currentPosY;
    jsonDoc["homed"] = isHomed;
    
    serializeJson(jsonDoc, Serial1);
    Serial1.println();
}