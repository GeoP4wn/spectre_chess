# ESP32 Motor Controller Firmware

## Overview
This firmware runs on the ESP32-S3 responsible for H-Bot gantry control, electromagnet actuation, and fan management.

## Hardware Responsibilities
- ✅ Control 2x TMC2209 stepper drivers (H-Bot kinematics)
- ✅ Home gantry using limit switch
- ✅ Control 4x electromagnets via MOSFETs
- ✅ PWM control of 4x cooling fans
- ✅ Communicate with Raspberry Pi via UART (JSON protocol)

## Pin Assignments

### Stepper Motors (TMC2209)
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO2 | MOTOR_A_STEP | Step pulses for Motor A |
| GPIO3 | MOTOR_A_DIR | Direction for Motor A |
| GPIO4 | MOTOR_A_EN | Enable for Motor A (active LOW) |
| GPIO5 | MOTOR_A_UART | Single-wire UART (with 1kΩ resistor) |
| GPIO6 | MOTOR_B_STEP | Step pulses for Motor B |
| GPIO7 | MOTOR_B_DIR | Direction for Motor B |
| GPIO8 | MOTOR_B_EN | Enable for Motor B (active LOW) |
| GPIO9 | MOTOR_B_UART | Single-wire UART (with 1kΩ resistor) |

### Electromagnets (MOSFET Control)
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO16 | MAGNET_1 | Electromagnet 1 gate (via 10kΩ pulldown) |
| GPIO17 | MAGNET_2 | Electromagnet 2 gate |
| GPIO18 | MAGNET_3 | Electromagnet 3 gate |
| GPIO19 | MAGNET_4 | Electromagnet 4 gate |

### Limit Switch
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO32 | LIMIT_SWITCH | Homing limit switch (active LOW) |

### Fans (PWM Control)
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO25 | FAN_1 | Fan 1 PWM (via level shifter to 5V) |
| GPIO26 | FAN_2 | Fan 2 PWM |
| GPIO27 | FAN_3 | Fan 3 PWM |
| GPIO33 | FAN_4 | Fan 4 PWM |

### UART Communication
| Pin | Function | Description |
|-----|----------|-------------|
| GPIO1 (RX) | UART_RX | Receive from Raspberry Pi |
| GPIO3 (TX) | UART_TX | Transmit to Raspberry Pi |

## Dependencies
```ini
bblanchon/ArduinoJson@^6.21.3
teemuatlut/TMCStepper@^0.7.3
```

## H-Bot Kinematics Explained

### What is H-Bot?
H-Bot is a motion system where **both motors affect both X and Y axes**. Unlike traditional XY systems where one motor moves X and another moves Y, H-Bot uses a clever belt arrangement.

### Motor Coordination
```
To move +X: Motor A forward + Motor B forward
To move +Y: Motor A forward + Motor B backward
To move -X: Motor A backward + Motor B backward
To move -Y: Motor A backward + Motor B forward
```

### Mathematical Model
```
stepsA = stepsX + stepsY
stepsB = stepsX - stepsY
```

Inverse:
```
stepsX = (stepsA + stepsB) / 2
stepsY = (stepsA - stepsB) / 2
```

### Advantages
- ✅ Low moving mass (motors are stationary)
- ✅ Compact vertical profile (both belts in same plane)
- ✅ Good for speed and precision
- ✅ Perfect for our <45mm height constraint

### Disadvantages
- ⚠️ More complex firmware
- ⚠️ Requires synchronized motor control
- ⚠️ Belt tension is critical

## Communication Protocol

### Messages FROM ESP32 to Pi

#### Status
```json
{
  "type": "status",
  "status": "ready",
  "controller": "motor",
  "message": "Motor controller initialized"
}
```

```json
{
  "type": "status",
  "status": "homed",
  "controller": "motor",
  "message": "Gantry homed to (0, 0)"
}
```

#### Position Update
```json
{
  "type": "position",
  "x": 165.5,
  "y": 220.0,
  "homed": true
}
```

### Messages TO ESP32 from Pi

#### Home Gantry
```json
{
  "cmd": "home"
}
```

#### Move to Absolute Position
```json
{
  "cmd": "move_absolute",
  "x": 200.0,
  "y": 150.0,
  "speed": 5000
}
```

#### Move Relative
```json
{
  "cmd": "move_relative",
  "dx": 10.0,
  "dy": -5.0
}
```

#### Electromagnet Control
Turn on specific magnet:
```json
{
  "cmd": "magnet_on",
  "magnet": 1
}
```

Turn on all magnets:
```json
{
  "cmd": "magnet_on"
}
```

Turn off:
```json
{
  "cmd": "magnet_off",
  "magnet": 1
}
```

#### Fan Control
```json
{
  "cmd": "set_fan",
  "fan": 1,
  "speed": 200
}
```

#### Emergency Stop
```json
{
  "cmd": "stop"
}
```

#### Get Current Position
```json
{
  "cmd": "get_position"
}
```

## TMC2209 Configuration

### Current Settings
- **Run current**: 500mA RMS (for 0.7A NEMA17)
- **Hold current**: 200mA RMS (reduced when stationary)
- **Microstepping**: 16 (1/16 step)
- **Mode**: StealthChop (silent operation)

### Why StealthChop?
- 🔇 Near-silent operation
- ✅ Smooth motion at low speeds
- ✅ No tuning required
- ⚠️ Less torque at very high speeds (not an issue for chess board)

### UART Communication
TMC2209 uses **single-wire half-duplex UART**:
- 1kΩ resistor on RX pin prevents short circuit
- ESP32 TX and RX share same pin via resistor
- Address switches (MS1_AD0, MS2_AD1 on driver):
  - Motor A: Address 0b00
  - Motor B: Address 0b01

## Motor Calibration

### Steps Per MM Calculation
```
Pulley diameter: 20 teeth × 2mm = 40mm circumference
Belt pitch: GT2 (2mm)
Circumference: 40mm × π ≈ 125.66mm

Steps per revolution: 200 (1.8° stepper)
Microstepping: 16
Total steps per rev: 200 × 16 = 3200 steps

Steps per mm: 3200 / 125.66 ≈ 25.5 steps/mm
```

**Default in firmware: 80 steps/mm** (adjust based on your actual pulley size)

### Speed Settings
- **Default speed**: 2000 steps/sec (≈78mm/sec with 25.5 steps/mm)
- **Max speed**: 8000 steps/sec (≈314mm/sec)
- **Homing speed**: 500 steps/sec (slower for safety)

## Homing Sequence

1. **Move towards limit switch** (both motors reverse)
2. **Wait for trigger** (limit switch goes LOW)
3. **Stop immediately**
4. **Back off 100 steps** (move away from switch)
5. **Set position to (0, 0)**
6. **Mark as homed**

## Electromagnet Circuit

### MOSFET Switching
- **MOSFET**: IRFL44N (N-channel, logic level)
- **Gate resistor**: 10kΩ pulldown (prevents firing during boot)
- **Flyback diode**: 1N4007 (protects against back-EMF)
- **Load**: P25/20 electromagnet (12V, ~1A)

### Control Logic
```
GPIO HIGH (3.3V) → MOSFET ON → Magnet energized
GPIO LOW (0V)    → MOSFET OFF → Magnet off
```

### Why Pulldown?
During ESP32 boot, GPIOs are in high-impedance state. Without pulldown, the gate could float HIGH and accidentally energize magnets. The 10kΩ pulldown ensures MOSFET stays OFF until explicitly commanded.

## Building and Uploading

### Using PlatformIO CLI
```bash
cd ESP32-Motor
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
=== ESP32 Motor Controller Starting ===
Configuring TMC2209 drivers...
TMC2209 drivers configured
Driver A current: 500
Driver B current: 500
Pins configured
Setup complete. Ready for commands.
```

### 2. Driver Communication Test
Verify TMC2209 UART is working:
- Check "Driver A current: 500" appears
- If shows 0 or error, check UART wiring

### 3. Manual Movement Test (NO LOAD)
**⚠️ Remove belt before this test!**

Send via Serial Monitor:
```json
{"cmd":"move_absolute","x":10,"y":0,"speed":1000}
```

Motors should turn slowly.

### 4. Homing Test
**WITH limit switch connected:**
```json
{"cmd":"home"}
```

Should see:
```
Starting homing sequence...
Limit switch triggered
Homing complete
```

### 5. Electromagnet Test
```json
{"cmd":"magnet_on","magnet":1}
```

Should hear relay/magnet click. Verify with multimeter: 12V across magnet.

### 6. Fan Test
```json
{"cmd":"set_fan","fan":1,"speed":200}
```

Fan should spin up.

## Troubleshooting

### Motors don't move
1. **Check enable pins** - Should be LOW to enable
2. **Check TMC2209 power** - Need 12V to VM pin
3. **Check UART communication** - Should see current readback
4. **Check motor wiring** - Coil pairs must be correct

### Motors move wrong direction
Swap direction logic in firmware or physically swap one coil pair.

### Homing doesn't work
1. **Test limit switch** - Should read HIGH when open, LOW when closed
2. **Check direction** - Motors should move toward switch
3. **Verify switch is in (0,0) corner**

### Electromagnets won't turn on
1. **Check 12V power supply**
2. **Verify MOSFET orientation** - Drain to +12V, Source to magnet
3. **Test GPIO directly** - Should read 3.3V when on
4. **Check flyback diode** - Stripe toward +12V

### TMC2209 gets hot
- Reduce current: `driverA.rms_current(400);`
- Add heatsink to driver
- Verify motor current rating

### Motors skip steps
- Increase current (up to motor rating)
- Reduce speed
- Check belt tension
- Verify acceleration isn't too high

## Calibration Procedure

### 1. Mechanical Setup
- Ensure belts are properly tensioned (should "twang" when plucked)
- Verify pulleys are tight on motor shafts
- Check that gantry moves smoothly by hand

### 2. Steps/MM Calibration
```cpp
// In firmware, adjust STEPS_PER_MM
#define STEPS_PER_MM  80  // Start here

// Test: Command 100mm movement
{"cmd":"move_absolute","x":100,"y":0}

// Measure actual distance traveled
// Adjust STEPS_PER_MM = (commanded / actual) * current
```

### 3. Speed Tuning
Start slow and increase:
```json
{"cmd":"move_absolute","x":200,"y":200,"speed":1000}
{"cmd":"move_absolute","x":0,"y":0,"speed":2000}
{"cmd":"move_absolute","x":200,"y":200,"speed":5000}
```

Find max speed where no steps are lost.

### 4. Acceleration Tuning
Currently not implemented (constant speed). Future enhancement.

## Power Requirements

- **Motors**: 12V, 0.7A each = 16.8W
- **Electromagnets**: 12V, 1A each × 4 = 48W (worst case, all on)
- **Fans**: 12V, 0.15A each × 4 = 7.2W
- **ESP32**: 3.3V, 0.2A = 0.66W
- **Total**: ~73W at full load

Recommended: **12V 10A power supply** for safety margin.

## Safety Features

### Implemented
- ✅ Position limits (won't move beyond MAX_X_MM, MAX_Y_MM)
- ✅ Homing required before movement
- ✅ Emergency stop command
- ✅ Pulldown resistors on MOSFET gates

### To Add (Future)
- [ ] Stall detection via TMC2209
- [ ] Soft limits
- [ ] Current monitoring
- [ ] Thermal protection
- [ ] Watchdog timer

## Future Enhancements

- [ ] Acceleration/deceleration curves
- [ ] Multi-segment path following
- [ ] Automatic stall recovery
- [ ] Position feedback verification
- [ ] Coordinated multi-axis circular interpolation
- [ ] Backlash compensation
