# ESP32 Sensor Controller Firmware

## Overview
This firmware runs on the ESP32-S3 responsible for sensor scanning, LED control, and button input monitoring.

## Hardware Responsibilities
- ✅ Scan 64 Hall Effect sensors (8x8 matrix) via 4x CD74HC4067 multiplexers
- ✅ Control 64 WS2812B RGB LEDs for board visualization
- ✅ Read 6 physical buttons
- ✅ Read 2 rotary encoders with buttons
- ✅ Communicate with Raspberry Pi via UART (JSON protocol)

## Pin Assignments

### Multiplexer Control (Shared)
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO2 | MUX_S0 | Multiplexer select bit 0 (all 4 muxes) |
| GPIO3 | MUX_S1 | Multiplexer select bit 1 |
| GPIO4 | MUX_S2 | Multiplexer select bit 2 |
| GPIO5 | MUX_S3 | Multiplexer select bit 3 |
| GPIO16 | MUX_EN | Multiplexer enable (active LOW) |

### Multiplexer Outputs
| Pin | Function | Handles |
|-----|----------|---------|
| GPIO17 | MUX1_OUT | Ranks 0-1 (squares a1-h2) |
| GPIO18 | MUX2_OUT | Ranks 2-3 (squares a3-h4) |
| GPIO19 | MUX3_OUT | Ranks 4-5 (squares a5-h6) |
| GPIO21 | MUX4_OUT | Ranks 6-7 (squares a7-h8) |

### LEDs
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO22 | LED_DATA | WS2812B data line (64 LEDs) |

### Buttons
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO25 | BTN1 | Clock button 1 (top left) |
| GPIO26 | BTN2 | Clock button 2 (top right) |
| GPIO27 | BTN3 | Side button 1 |
| GPIO32 | BTN4 | Side button 2 |
| GPIO33 | BTN5 | Side button 3 |
| GPIO34 | BTN6 | Side button 4 |

### Rotary Encoders
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO35 | ENC1_A | Encoder 1 channel A |
| GPIO36 | ENC1_B | Encoder 1 channel B |
| GPIO39 | ENC1_BTN | Encoder 1 button |
| GPIO14 | ENC2_A | Encoder 2 channel A |
| GPIO12 | ENC2_B | Encoder 2 channel B |
| GPIO13 | ENC2_BTN | Encoder 2 button |

### UART Communication
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO1 (RX) | UART_RX | Receive from Raspberry Pi |
| GPIO3 (TX) | UART_TX | Transmit to Raspberry Pi |

## Dependencies
```ini
adafruit/Adafruit NeoPixel@^1.11.0
bblanchon/ArduinoJson@^6.21.3
```

## Communication Protocol

### Messages FROM ESP32 to Pi

#### Sensor Update
Sent when board state changes.
```json
{
  "type": "sensor_update",
  "sensors": [
    [false, true, true, true, true, true, true, false],
    [true, true, true, true, true, true, true, true],
    [false, false, false, false, false, false, false, false],
    ...
  ]
}
```

#### Button Event
```json
{
  "type": "button",
  "button": 1,
  "state": "pressed"
}
```

#### Encoder Event
```json
{
  "type": "encoder",
  "encoder": 1,
  "delta": -2
}
```

#### Status
```json
{
  "type": "status",
  "status": "ready",
  "controller": "sensor"
}
```

### Messages TO ESP32 from Pi

#### Scan Sensors
Request immediate sensor scan.
```json
{
  "cmd": "scan_sensors"
}
```

#### Highlight Squares
Light up specific squares.
```json
{
  "cmd": "highlight_squares",
  "squares": [[3, 4], [4, 4]],
  "color": [0, 255, 0],
  "duration": 2000
}
```

#### Flash All LEDs
Flash all LEDs (error indication).
```json
{
  "cmd": "flash_all",
  "color": [255, 0, 0],
  "count": 3
}
```

#### Set LED Theme
```json
{
  "cmd": "set_theme",
  "theme": "classic"
}
```

#### LEDs Off
```json
{
  "cmd": "leds_off"
}
```

#### Set Brightness
```json
{
  "cmd": "set_brightness",
  "brightness": 128
}
```

## Sensor Scanning Logic

The firmware scans all 64 sensors every 100ms:

1. **Loop through each square** (8x8 = 64 total)
2. **Calculate multiplexer and channel**:
   - Multiplexer index = rank ÷ 2 (0-3)
   - Channel = (rank mod 2) × 8 + file (0-15)
3. **Set channel select pins** (S0-S3)
4. **Read from appropriate MUX output pin**
5. **Invert result** (AH3503 is active LOW)
6. **Compare with last state** - if changed, send update

## LED Layout

LEDs are arranged in a serpentine pattern:
- **Rank 0** (a1-h1): Left to right (indices 0-7)
- **Rank 1** (a2-h2): Right to left (indices 8-15)
- **Rank 2** (a3-h3): Left to right (indices 16-23)
- And so on...

This minimizes wiring length for WS2812B strip.

## Building and Uploading

### Using PlatformIO CLI
```bash
cd ESP32-Sensor
pio run --target upload
pio device monitor
```

### Using PlatformIO IDE
1. Open folder in VS Code with PlatformIO extension
2. Click "Upload" button
3. Click "Serial Monitor" button

## Testing

### 1. Basic Boot Test
After upload, check serial monitor:
```
=== ESP32 Sensor Controller Starting ===
Pins configured
LEDs initialized
Setup complete. Ready for commands.
```

### 2. LED Test
LEDs should flash white briefly on boot.

### 3. Sensor Test
Place a magnet on the board and observe serial output:
```
Sensor update sent
```

### 4. Button Test
Press any button:
```
Button 1 pressed
Button 1 released
```

### 5. UART Test
Send from Pi:
```bash
echo '{"cmd":"scan_sensors"}' > /dev/ttyUSB0
```

Should receive JSON response.

## Troubleshooting

### LEDs don't light up
- Check 5V power supply to LED strip
- Verify data pin connection (GPIO22)
- Ensure ground is common between ESP32 and LED strip

### Sensors not responding
- Verify 5V power to AH3503 sensors
- Check TXS0108E level shifter connections
- Ensure multiplexer enable (GPIO16) is LOW
- Test with multimeter: sensor output should be LOW when magnet present

### No UART communication
- Check TX/RX connections (they should cross: ESP32 TX → Pi RX)
- Verify baud rate matches (115200)
- Test with USB-to-serial adapter first

### Buttons always pressed / never pressed
- Buttons should be active LOW with pullup resistors
- Check wiring: one side to GND, other to GPIO
- Verify internal pullup is enabled

## Hardware Notes

### Level Shifters
The TXS0108E shifts between:
- **A-side (VCCA)**: 3.3V (ESP32 logic)
- **B-side (VCCB)**: 5V (sensor outputs)

Connect sensor outputs to B-side, ESP32 GPIOs to A-side.

### Hall Effect Sensors
AH3503 sensors:
- **Pin 1 (VCC)**: 5V
- **Pin 2 (GND)**: Ground
- **Pin 3 (VOUT)**: Open drain output (active LOW)
  - Needs pull-up resistor to 5V (typically 10kΩ)
  - LOW when magnet present
  - HIGH (pulled up) when no magnet

### Multiplexer Channel Mapping
Each CD74HC4067 handles 16 sensors (2 ranks × 8 files):

**MUX 1** (Ranks 0-1):
- Channel 0-7: a1, b1, c1, d1, e1, f1, g1, h1
- Channel 8-15: a2, b2, c2, d2, e2, f2, g2, h2

**MUX 2** (Ranks 2-3):
- Channel 0-7: a3, b3, c3, d3, e3, f3, g3, h3
- Channel 8-15: a4, b4, c4, d4, e4, f4, g4, h4

And so on for MUX 3 and MUX 4.

## Power Consumption

Estimated current draw:
- ESP32-S3: ~200mA (WiFi off)
- 64x WS2812B LEDs (all white, full brightness): ~3.8A
- Hall Effect sensors: ~64mA
- **Total**: ~4.1A at 5V

Use a quality 5V 5A power supply!

## Future Enhancements

- [ ] Automatic LED animations during idle
- [ ] Configurable scan interval
- [ ] Sensor calibration routine
- [ ] Button long-press detection
- [ ] LED brightness auto-adjustment
- [ ] Power-saving mode
