# Smart Chess Board - Software Architecture

## Overview
This is the complete async event loop implementation for your robotic chess board project. The architecture follows a distributed processing model with proper async/await patterns throughout.

## Architecture

### Core Components

1. **main.py** - Main event loop and state machine
   - `ChessBoardController`: Orchestrates all subsystems
   - `ChessStateMachine`: State management (BOOT → IDLE → HUMAN_TURN → ROBOT_THINKING → ROBOT_MOVING → GAME_OVER)
   - Background tasks: sensor polling, voice listening, UI updates, button monitoring

2. **game_manager.py** - Chess logic and move validation
   - Maintains the "digital twin" of the physical board
   - Interfaces with chess providers (local, engine, Lichess)
   - Handles move parsing, validation, and path calculation

3. **database_manager.py** - SQLite database operations
   - User management
   - Game history and move tracking
   - Settings persistence
   - Graveyard state tracking

4. **hardware_interface.py** - ESP32 communication
   - JSON-over-UART protocol
   - Sensor matrix reading
   - Motor control commands
   - LED control

5. **user_manager.py** - User authentication and settings

6. **voice_service.py** - Vosk voice recognition (stub)

### Provider Pattern
The game manager uses a provider pattern for different input sources:

- **LocalProvider**: Human player (physical board input)
- **EngineProvider**: Stockfish AI opponent
- **LichessProvider**: Online play via Lichess API

## State Machine Flow

```
BOOT (startup, hardware checks, homing)
  ↓
IDLE (waiting for game start)
  ↓
HUMAN_TURN (waiting for physical sensor changes)
  ↓
ROBOT_THINKING (AI calculating move)
  ↓
ROBOT_MOVING (executing mechanical movement)
  ↓
HUMAN_TURN (back to human) or GAME_OVER
```

## Running the System

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Stockfish (if not already installed)
sudo apt install stockfish
```

### Quick Start

```bash
# Run the main application
python main.py
```

The system will:
1. Initialize database (creates `chessboard.db`)
2. Initialize hardware (currently in MOCK MODE)
3. Home motors
4. Enter IDLE state waiting for game start

### Mock Mode
Currently running in **MOCK MODE** for testing without physical hardware. The system simulates:
- Hall Effect sensor readings
- Motor movements
- LED control
- Button inputs

## Database Schema

### Tables

1. **users** - User accounts
2. **user_settings** - Per-user preferences (motor speed, LED theme, engine difficulty, etc.)
3. **games** - Game metadata
4. **move_history** - All moves with timestamps and evaluations
5. **graveyard** - Captured piece positions
6. **custom_positions** - Saved board positions

## Background Tasks

The system runs 4 concurrent background tasks:

1. **Sensor Polling** (100ms interval)
   - Reads Hall Effect matrix
   - Detects board changes
   - Validates moves

2. **Voice Listening** (50ms interval)
   - Listens for voice commands
   - Processes commands ("new game", "resign", "hint")

3. **UI Updates** (500ms interval)
   - Sends board state to WebSocket clients
   - Updates clock and evaluation

4. **Button Monitoring** (50ms interval)
   - Reads physical buttons and rotary encoders
   - Processes input events

## Communication Protocol

### JSON-over-UART Format

**To Sensor ESP32:**
```json
{
  "cmd": "scan_sensors"
}
{
  "cmd": "highlight_squares",
  "squares": [[3, 4], [4, 4]],
  "color": [0, 255, 0],
  "duration": 2000
}
```

**From Sensor ESP32:**
```json
{
  "sensors": [[true, true, ...], ...]
}
```

**To Motor ESP32:**
```json
{
  "cmd": "move_absolute",
  "x": 165.5,
  "y": 220.0,
  "speed": 5000
}
{
  "cmd": "magnet_on"
}
```

## Next Steps

### Phase 1: Complete Core Features
- [ ] Implement actual UART communication with ESP32s
- [ ] Add pathfinding algorithm for knight moves
- [ ] Implement graveyard management logic
- [ ] Add move evaluation (blunder/mistake/good detection)

### Phase 2: Web Interface
- [ ] Build FastAPI WebSocket server
- [ ] Create web UI for settings
- [ ] Real-time board visualization
- [ ] Game history viewer

### Phase 3: Advanced Features
- [ ] Vosk voice recognition integration
- [ ] Lichess API integration
- [ ] Chess clock implementation
- [ ] Move hints and analysis

### Phase 4: ESP32 Firmware
- [ ] Sensor scanning firmware
- [ ] Motor control firmware
- [ ] LED control (WS2812B)
- [ ] Button debouncing

## File Structure

```
backend/
├── main.py                    # Main event loop
├── game_manager.py            # Chess logic
├── database_manager.py        # Database operations
├── hardware_interface.py      # ESP32 communication
├── user_manager.py            # User management
├── voice_service.py           # Voice recognition
├── providers/
│   ├── __init__.py
│   ├── local_provider.py     # Human player
│   ├── engine_provider.py    # Stockfish AI
│   └── lichess_provider.py   # Online play
├── requirements.txt
└── README.md
```

## Hardware Integration

### ESP32 Pin Assignments (from schematics)

**Sensor ESP32 (ESP32-S3):**
- GPIO2-5: Multiplexer select lines (S0-S3)
- GPIO16-17: Multiplexer enable/output
- GPIO18: WS2812B LED data
- GPIO19-23: Button inputs
- GPIO25-27: Rotary encoder inputs
- UART: Communication with Raspberry Pi

**Motor ESP32 (ESP32-S3):**
- GPIO2-3: TMC2209 STEP/DIR (Motor 1)
- GPIO4-5: TMC2209 STEP/DIR (Motor 2)
- GPIO16-19: Electromagnet MOSFETs (Q1-Q4)
- GPIO25-27: Fan PWM control
- GPIO32: Limit switch input
- UART: Communication with Raspberry Pi

### Voltage Levels
- Logic: 3.3V (ESP32, Raspberry Pi)
- Sensors: 5V (with TXS0108E level shifters)
- Motors/Magnets: 12V
- LEDs: 5V

## Settings Available

### Motor Settings
- Speed: SLOW/MEDIUM/FAST
- Animation speed

### Chess Clock
- Enabled: on/off
- Time: minutes
- Increment: seconds

### Move Evaluation
- Level: NONE/BASIC/ADVANCED
- Show: blunders, mistakes, inaccuracies, good, excellent, brilliant
- Hint count: number of hints allowed

### LEDs
- Enabled: on/off
- Brightness: 0-255
- Theme: CLASSIC/MODERN/RAINBOW
- Highlight legal moves
- Highlight last move

### Engine
- Difficulty: 1-20 (Stockfish skill level)
- Engine type: STOCKFISH

### Voice
- Enabled: on/off
- Language: en-US, etc.
- Feedback: on/off

### UI
- Theme: DARK/LIGHT
- Sound: on/off
- Volume: 0-100

## Logging

The system uses Python's logging module. Logs include:
- State transitions
- Move detection and validation
- Hardware commands
- Error conditions

Adjust log level in `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # For verbose output
```

## Testing Without Hardware

The system is designed to run without physical hardware for software development:

1. **Mock sensor readings**: Returns standard chess starting position
2. **Mock motor commands**: Simulates movement with delays
3. **Mock LED control**: Logs commands instead of sending to hardware
4. **Stockfish AI**: Works normally (requires Stockfish installation)

## API for External Integration

The system exposes these public methods on `ChessBoardController`:

- `start_new_game(mode, user_id)` - Start a new game
- `resign_game()` - Resign current game
- `show_hint()` - Get and display a hint

These can be called from:
- Voice commands
- Button presses
- Web UI
- External scripts

## Performance Considerations

- **Sensor polling**: 100ms (10 Hz) - fast enough for responsive play
- **Voice processing**: 50ms (20 Hz) - responsive to commands
- **UI updates**: 500ms (2 Hz) - smooth without overwhelming WebSocket clients
- **Move execution**: Variable based on distance and motor speed setting

## Contributing

When extending this code:

1. **Add new settings**: Update `user_settings` table in `database_manager.py`
2. **Add new providers**: Implement in `providers/` following the provider interface
3. **Add new states**: Extend `ChessStateMachine` with new states and transitions
4. **Add new hardware**: Extend `hardware_interface.py` with new commands

## Troubleshooting

### Database locked
- Close any other programs accessing `chessboard.db`
- SQLite allows only one writer at a time

### Stockfish not found
```bash
sudo apt install stockfish
```

### Import errors
```bash
pip install -r requirements.txt
```

### State machine errors
- Check that all transitions have valid source and target states
- Verify conditions return boolean values

---

## What You've Learned So Far

From this implementation, you should understand:

1. **Async/await patterns**: How to structure concurrent tasks
2. **State machines**: Managing complex system states
3. **Provider pattern**: Abstracting different input sources
4. **Database design**: Relational schema for game data
5. **Hardware abstraction**: Separating logic from physical interface
6. **Event-driven architecture**: Responding to sensors, buttons, voice

## Next Session Goals

Based on your 5-hour window with Claude Pro, I recommend focusing on:

1. **Test the current code** - Run it, understand the flow
2. **Build the WebSocket server** - Real-time UI updates
3. **Implement pathfinding** - Knight moves and collision avoidance
4. **Add basic web UI** - Settings management interface

Each of these is a focused task that fits within a coding session.
