/**
 * ESP32 Sensor Controller Firmware
 * 
 * Responsibilities:
 * - Scan 64 Hall Effect sensors via 4x CD74HC4067 multiplexers
 * - Control 64 WS2812B LEDs for board visualization
 * - Read 6 buttons and 2 rotary encoders
 * - Communicate with Raspberry Pi via UART (JSON protocol)
 * 
 * Hardware:
 * - ESP32-S3 DevKit C-1
 * - 4x CD74HC4067 16:1 Analog Multiplexers
 * - 64x AH3503 Hall Effect Sensors (digital, active LOW)
 * - 64x WS2812B RGB LEDs
 * - 6x Buttons
 * - 2x Rotary Encoders (with button)
 * - 2x TXS0108E Level Shifters (3.3V <-> 5V)
 */

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

// ==================== PIN DEFINITIONS ====================

// Multiplexer control pins (shared by all 4 multiplexers)
#define MUX_S0_PIN    2
#define MUX_S1_PIN    3
#define MUX_S2_PIN    4
#define MUX_S3_PIN    5

// Multiplexer enable/output pins (one per multiplexer)
#define MUX_EN_PIN    16  // Enable (active LOW)
#define MUX1_OUT_PIN  17  // Multiplexer 1 output (rows 0-1)
#define MUX2_OUT_PIN  18  // Multiplexer 2 output (rows 2-3)
#define MUX3_OUT_PIN  19  // Multiplexer 3 output (rows 4-5)
#define MUX4_OUT_PIN  21  // Multiplexer 4 output (rows 6-7)

// LED control
#define LED_DATA_PIN  22
#define LED_COUNT     64

// Buttons (active LOW with internal pullup)
#define BTN1_PIN      25
#define BTN2_PIN      26
#define BTN3_PIN      27
#define BTN4_PIN      32
#define BTN5_PIN      33
#define BTN6_PIN      34

// Rotary Encoders
#define ENC1_A_PIN    35
#define ENC1_B_PIN    36
#define ENC1_BTN_PIN  39

#define ENC2_A_PIN    14
#define ENC2_B_PIN    12
#define ENC2_BTN_PIN  13

// UART communication with Raspberry Pi
#define UART_RX_PIN   1   // RX from Pi
#define UART_TX_PIN   3   // TX to Pi
#define UART_BAUD     115200

// ==================== CONSTANTS ====================

#define BOARD_SIZE    8
#define SCAN_INTERVAL_MS    100   // Scan sensors every 100ms
#define BUTTON_DEBOUNCE_MS  50    // Button debounce time
#define LED_BRIGHTNESS      128   // Default brightness (0-255)

// ==================== GLOBAL VARIABLES ====================

// Sensor state (8x8 matrix, true = piece detected)
bool sensorState[BOARD_SIZE][BOARD_SIZE];
bool lastSensorState[BOARD_SIZE][BOARD_SIZE];

// LED control
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

// Button states
bool buttonStates[6] = {false};
bool lastButtonStates[6] = {false};
unsigned long lastButtonPress[6] = {0};

// Rotary encoder states
volatile int encoder1Position = 0;
volatile int encoder2Position = 0;
int lastEncoder1Position = 0;
int lastEncoder2Position = 0;

// Timing
unsigned long lastScanTime = 0;

// JSON buffer
StaticJsonDocument<2048> jsonDoc;
String inputBuffer = "";

// LED theme/colors
struct LEDTheme {
    uint32_t backgroundColor;
    uint32_t whitePieceColor;
    uint32_t blackPieceColor;
    uint32_t highlightColor;
    uint32_t legalMoveColor;
} currentTheme;

// ==================== FUNCTION DECLARATIONS ====================

void setupPins();
void setupLEDs();
void scanSensors();
void readButtons();
void sendSensorUpdate();
void sendButtonEvent(int buttonIndex, bool pressed);
void sendEncoderEvent(int encoderIndex, int delta);
void processUARTCommand();
void handleLEDCommand(JsonObject& cmd);
void handleConfigCommand(JsonObject& cmd);
void setLEDSquare(int file, int rank, uint32_t color);
void updateLEDs();
uint8_t readMultiplexer(uint8_t muxIndex, uint8_t channel);
void IRAM_ATTR encoder1ISR();
void IRAM_ATTR encoder2ISR();

// ==================== SETUP ====================

void setup() {
    // Initialize serial for debugging
    Serial.begin(115200);
    Serial.println("\n\n=== ESP32 Sensor Controller Starting ===");
    
    // Initialize UART for Pi communication
    Serial1.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
    
    // Setup hardware
    setupPins();
    setupLEDs();
    
    // Initialize sensor state to all empty
    memset(sensorState, 0, sizeof(sensorState));
    memset(lastSensorState, 0, sizeof(lastSensorState));
    
    // Set default LED theme
    currentTheme.backgroundColor = strip.Color(0, 0, 0);        // Black
    currentTheme.whitePieceColor = strip.Color(255, 255, 255);  // White
    currentTheme.blackPieceColor = strip.Color(100, 100, 100);  // Gray
    currentTheme.highlightColor = strip.Color(0, 255, 0);       // Green
    currentTheme.legalMoveColor = strip.Color(0, 100, 255);     // Blue
    
    Serial.println("Setup complete. Ready for commands.");
    
    // Send ready signal to Pi
    StaticJsonDocument<128> readyMsg;
    readyMsg["type"] = "status";
    readyMsg["status"] = "ready";
    readyMsg["controller"] = "sensor";
    serializeJson(readyMsg, Serial1);
    Serial1.println();
}

// ==================== MAIN LOOP ====================

void loop() {
    unsigned long currentTime = millis();
    
    // Scan sensors at regular interval
    if (currentTime - lastScanTime >= SCAN_INTERVAL_MS) {
        scanSensors();
        lastScanTime = currentTime;
    }
    
    // Read buttons
    readButtons();
    
    // Check for encoder changes
    if (encoder1Position != lastEncoder1Position) {
        int delta = encoder1Position - lastEncoder1Position;
        sendEncoderEvent(1, delta);
        lastEncoder1Position = encoder1Position;
    }
    
    if (encoder2Position != lastEncoder2Position) {
        int delta = encoder2Position - lastEncoder2Position;
        sendEncoderEvent(2, delta);
        lastEncoder2Position = encoder2Position;
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
    // Multiplexer control pins
    pinMode(MUX_S0_PIN, OUTPUT);
    pinMode(MUX_S1_PIN, OUTPUT);
    pinMode(MUX_S2_PIN, OUTPUT);
    pinMode(MUX_S3_PIN, OUTPUT);
    pinMode(MUX_EN_PIN, OUTPUT);
    
    digitalWrite(MUX_EN_PIN, LOW); // Enable multiplexers (active LOW)
    
    // Multiplexer output pins (inputs to ESP32)
    pinMode(MUX1_OUT_PIN, INPUT);
    pinMode(MUX2_OUT_PIN, INPUT);
    pinMode(MUX3_OUT_PIN, INPUT);
    pinMode(MUX4_OUT_PIN, INPUT);
    
    // Button pins with pullup
    pinMode(BTN1_PIN, INPUT_PULLUP);
    pinMode(BTN2_PIN, INPUT_PULLUP);
    pinMode(BTN3_PIN, INPUT_PULLUP);
    pinMode(BTN4_PIN, INPUT_PULLUP);
    pinMode(BTN5_PIN, INPUT_PULLUP);
    pinMode(BTN6_PIN, INPUT_PULLUP);
    
    // Rotary encoder pins with pullup
    pinMode(ENC1_A_PIN, INPUT_PULLUP);
    pinMode(ENC1_B_PIN, INPUT_PULLUP);
    pinMode(ENC1_BTN_PIN, INPUT_PULLUP);
    
    pinMode(ENC2_A_PIN, INPUT_PULLUP);
    pinMode(ENC2_B_PIN, INPUT_PULLUP);
    pinMode(ENC2_BTN_PIN, INPUT_PULLUP);
    
    // Attach encoder interrupts
    attachInterrupt(digitalPinToInterrupt(ENC1_A_PIN), encoder1ISR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC2_A_PIN), encoder2ISR, CHANGE);
    
    Serial.println("Pins configured");
}

void setupLEDs() {
    strip.begin();
    strip.setBrightness(LED_BRIGHTNESS);
    strip.clear();
    strip.show();
    
    // Test pattern: flash all LEDs
    for (int i = 0; i < LED_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(50, 50, 50));
    }
    strip.show();
    delay(200);
    strip.clear();
    strip.show();
    
    Serial.println("LEDs initialized");
}

// ==================== SENSOR SCANNING ====================

void scanSensors() {
    bool changed = false;
    
    // Scan all 64 sensors (8x8 matrix)
    for (int rank = 0; rank < BOARD_SIZE; rank++) {
        for (int file = 0; file < BOARD_SIZE; file++) {
            // Calculate which multiplexer and channel
            // Layout: 4 multiplexers, each handles 2 ranks (16 sensors)
            int muxIndex = rank / 2;        // 0-3
            int channel = (rank % 2) * 8 + file;  // 0-15
            
            // Read sensor (active LOW, so invert)
            bool pieceDetected = !readMultiplexer(muxIndex, channel);
            
            sensorState[rank][file] = pieceDetected;
            
            // Check for changes
            if (sensorState[rank][file] != lastSensorState[rank][file]) {
                changed = true;
            }
        }
    }
    
    // If board state changed, send update to Pi
    if (changed) {
        sendSensorUpdate();
        
        // Update last known state
        memcpy(lastSensorState, sensorState, sizeof(sensorState));
    }
}

uint8_t readMultiplexer(uint8_t muxIndex, uint8_t channel) {
    // Set multiplexer channel (S0-S3)
    digitalWrite(MUX_S0_PIN, channel & 0x01);
    digitalWrite(MUX_S1_PIN, (channel >> 1) & 0x01);
    digitalWrite(MUX_S2_PIN, (channel >> 2) & 0x01);
    digitalWrite(MUX_S3_PIN, (channel >> 3) & 0x01);
    
    // Small delay for multiplexer to settle
    delayMicroseconds(10);
    
    // Read from appropriate multiplexer output pin
    uint8_t value;
    switch (muxIndex) {
        case 0: value = digitalRead(MUX1_OUT_PIN); break;
        case 1: value = digitalRead(MUX2_OUT_PIN); break;
        case 2: value = digitalRead(MUX3_OUT_PIN); break;
        case 3: value = digitalRead(MUX4_OUT_PIN); break;
        default: value = 0;
    }
    
    return value;
}

void sendSensorUpdate() {
    // Build JSON message with sensor matrix
    jsonDoc.clear();
    jsonDoc["type"] = "sensor_update";
    
    JsonArray sensors = jsonDoc.createNestedArray("sensors");
    
    for (int rank = 0; rank < BOARD_SIZE; rank++) {
        JsonArray row = sensors.createNestedArray();
        for (int file = 0; file < BOARD_SIZE; file++) {
            row.add(sensorState[rank][file]);
        }
    }
    
    serializeJson(jsonDoc, Serial1);
    Serial1.println();
    
    Serial.println("Sensor update sent");
}

// ==================== BUTTON READING ====================

void readButtons() {
    unsigned long currentTime = millis();
    
    // Read all buttons
    int buttonPins[] = {BTN1_PIN, BTN2_PIN, BTN3_PIN, BTN4_PIN, BTN5_PIN, BTN6_PIN};
    
    for (int i = 0; i < 6; i++) {
        bool currentState = !digitalRead(buttonPins[i]); // Active LOW, invert
        
        // Debounce
        if (currentState != lastButtonStates[i]) {
            if (currentTime - lastButtonPress[i] > BUTTON_DEBOUNCE_MS) {
                buttonStates[i] = currentState;
                lastButtonPress[i] = currentTime;
                
                // Send button event
                sendButtonEvent(i + 1, currentState);
            }
        }
        
        lastButtonStates[i] = currentState;
    }
}

void sendButtonEvent(int buttonIndex, bool pressed) {
    jsonDoc.clear();
    jsonDoc["type"] = "button";
    jsonDoc["button"] = buttonIndex;
    jsonDoc["state"] = pressed ? "pressed" : "released";
    
    serializeJson(jsonDoc, Serial1);
    Serial1.println();
    
    Serial.printf("Button %d %s\n", buttonIndex, pressed ? "pressed" : "released");
}

// ==================== ENCODER INTERRUPTS ====================

void IRAM_ATTR encoder1ISR() {
    static int lastA = HIGH;
    int a = digitalRead(ENC1_A_PIN);
    int b = digitalRead(ENC1_B_PIN);
    
    if (a != lastA) {
        if (a == LOW) {
            encoder1Position += (b == HIGH) ? 1 : -1;
        }
        lastA = a;
    }
}

void IRAM_ATTR encoder2ISR() {
    static int lastA = HIGH;
    int a = digitalRead(ENC2_A_PIN);
    int b = digitalRead(ENC2_B_PIN);
    
    if (a != lastA) {
        if (a == LOW) {
            encoder2Position += (b == HIGH) ? 1 : -1;
        }
        lastA = a;
    }
}

void sendEncoderEvent(int encoderIndex, int delta) {
    jsonDoc.clear();
    jsonDoc["type"] = "encoder";
    jsonDoc["encoder"] = encoderIndex;
    jsonDoc["delta"] = delta;
    
    serializeJson(jsonDoc, Serial1);
    Serial1.println();
    
    Serial.printf("Encoder %d: %+d\n", encoderIndex, delta);
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
    if (strcmp(cmdType, "scan_sensors") == 0) {
        scanSensors();
        sendSensorUpdate();
    }
    else if (strcmp(cmdType, "highlight_squares") == 0) {
        handleLEDCommand(cmd);
    }
    else if (strcmp(cmdType, "set_theme") == 0) {
        handleLEDCommand(cmd);
    }
    else if (strcmp(cmdType, "flash_all") == 0) {
        handleLEDCommand(cmd);
    }
    else if (strcmp(cmdType, "leds_off") == 0) {
        strip.clear();
        strip.show();
    }
    else if (strcmp(cmdType, "set_brightness") == 0) {
        if (cmd.containsKey("brightness")) {
            int brightness = cmd["brightness"];
            strip.setBrightness(constrain(brightness, 0, 255));
            strip.show();
        }
    }
    else {
        Serial.print("Unknown command: ");
        Serial.println(cmdType);
    }
}

// ==================== LED CONTROL ====================

void handleLEDCommand(JsonObject& cmd) {
    const char* cmdType = cmd["cmd"];
    
    if (strcmp(cmdType, "highlight_squares") == 0) {
        JsonArray squares = cmd["squares"];
        JsonArray colorArray = cmd["color"];
        
        if (squares.isNull() || colorArray.isNull()) return;
        
        uint32_t color = strip.Color(colorArray[0], colorArray[1], colorArray[2]);
        int duration = cmd["duration"] | 2000; // Default 2 seconds
        
        // Highlight specified squares
        for (JsonVariant square : squares) {
            JsonArray pos = square.as<JsonArray>();
            int file = pos[0];
            int rank = pos[1];
            setLEDSquare(file, rank, color);
        }
        strip.show();
        
        // TODO: Auto-clear after duration (needs timer)
    }
    else if (strcmp(cmdType, "flash_all") == 0) {
        JsonArray colorArray = cmd["color"];
        int count = cmd["count"] | 3;
        
        uint32_t color = strip.Color(colorArray[0], colorArray[1], colorArray[2]);
        
        for (int i = 0; i < count; i++) {
            for (int j = 0; j < LED_COUNT; j++) {
                strip.setPixelColor(j, color);
            }
            strip.show();
            delay(200);
            
            strip.clear();
            strip.show();
            delay(200);
        }
    }
}

void setLEDSquare(int file, int rank, uint32_t color) {
    // LED index calculation
    // Assuming serpentine layout: rank 0 goes left-to-right, rank 1 right-to-left, etc.
    int ledIndex;
    
    if (rank % 2 == 0) {
        // Even ranks: left to right
        ledIndex = rank * 8 + file;
    } else {
        // Odd ranks: right to left
        ledIndex = rank * 8 + (7 - file);
    }
    
    strip.setPixelColor(ledIndex, color);
}

void updateLEDs() {
    strip.show();
}
