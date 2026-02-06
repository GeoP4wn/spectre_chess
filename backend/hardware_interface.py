"""
Hardware Interface for the Smart Chess Board.
Manages communication with ESP32 microcontrollers via UART.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class HardwareInterface:
    """
    Interface to the physical hardware (ESP32s, motors, sensors, LEDs).
    Communicates via JSON-over-UART protocol.
    """
    
    def __init__(self):
        self.sensor_esp: Optional[Any] = None  # Will be serial connection
        self.motor_esp: Optional[Any] = None   # Will be serial connection
        
        # Current gantry position
        self.current_position: Tuple[int, int] = (0, 0)
        self.is_homed: bool = False
        
        # Simulated sensor state for testing
        self.mock_sensor_state: List[List[bool]] = [[False] * 8 for _ in range(8)]
        
    async def initialize(self):
        """Initialize hardware connections"""
        logger.info("Initializing hardware interface...")
        
        # TODO: Open serial connections to ESP32s
        # For now, using mock mode
        logger.warning("Running in MOCK MODE - no real hardware")
        
        await asyncio.sleep(0.1)  # Simulate initialization delay
        logger.info("Hardware interface initialized (mock mode)")
    
    async def home_motors(self):
        """Home the H-Bot gantry to (0,0) using limit switch"""
        logger.info("Homing motors...")
        
        # TODO: Send homing command to motor ESP32
        # Command format: {"cmd": "home"}
        
        await self._send_motor_command({"cmd": "home"})
        
        # Wait for homing to complete
        await asyncio.sleep(2.0)  # Simulate homing time
        
        self.current_position = (0, 0)
        self.is_homed = True
        logger.info("Motors homed successfully")
    
    async def shutdown(self):
        """Shutdown hardware gracefully"""
        logger.info("Shutting down hardware...")
        
        # TODO: Close serial connections
        # Turn off electromagnets
        await self._send_motor_command({"cmd": "magnet_off"})
        
        # Turn off LEDs
        await self._send_sensor_command({"cmd": "leds_off"})
        
        logger.info("Hardware shutdown complete")
    
    # ==================== Sensor Interface ====================
    
    async def read_sensor_matrix(self) -> List[List[bool]]:
        """
        Read the 8x8 Hall Effect sensor matrix.
        
        Returns:
            8x8 boolean matrix (True = piece present)
        """
        # TODO: Send command to sensor ESP32 to scan matrix
        # Command format: {"cmd": "scan_sensors"}
        # Response format: {"sensors": [[bool, ...], ...]}
        
        response = await self._send_sensor_command({"cmd": "scan_sensors"})
        
        if response and "sensors" in response:
            return response["sensors"]
        
        # Return mock state for testing
        return self.mock_sensor_state
    
    async def read_buttons(self) -> List[Dict[str, Any]]:
        """
        Read button states.
        
        Returns:
            List of button events: [{"button": "BTN1", "state": "pressed"}, ...]
        """
        # TODO: Poll button states from sensor ESP32
        response = await self._send_sensor_command({"cmd": "read_buttons"})
        
        if response and "buttons" in response:
            return response["buttons"]
        
        return []  # No button events
    
    # ==================== Motion Control ====================
    
    async def move_piece(self, from_square: Tuple[int, int], to_square: Tuple[int, int]):
        """
        Move a piece from one square to another.
        
        Args:
            from_square: (file, rank) - 0-indexed
            to_square: (file, rank) - 0-indexed
        """
        logger.info(f"Moving piece from {from_square} to {to_square}")
        
        # Calculate physical coordinates (convert chess coords to mm)
        from_pos = self._square_to_position(from_square)
        to_pos = self._square_to_position(to_square)
        
        # Move to source square
        await self._move_gantry(from_pos)
        
        # Engage electromagnet
        await self._send_motor_command({"cmd": "magnet_on"})
        await asyncio.sleep(0.2)  # Wait for magnet to engage
        
        # Move to destination square
        await self._move_gantry(to_pos)
        
        # Disengage electromagnet
        await self._send_motor_command({"cmd": "magnet_off"})
        await asyncio.sleep(0.1)
        
        logger.info("Move complete")
    
    async def _move_gantry(self, position: Tuple[float, float]):
        """
        Move gantry to absolute position (in mm).
        
        Args:
            position: (x, y) in millimeters
        """
        x, y = position
        
        # TODO: Calculate stepper pulses needed
        # Send movement command to motor ESP32
        command = {
            "cmd": "move_absolute",
            "x": x,
            "y": y,
            "speed": 5000  # mm/min - will come from settings
        }
        
        await self._send_motor_command(command)
        
        # Wait for movement to complete
        # TODO: Implement proper movement completion detection
        distance = ((x - self.current_position[0])**2 + (y - self.current_position[1])**2)**0.5
        movement_time = distance / 83.3  # 5000 mm/min = 83.3 mm/s
        await asyncio.sleep(movement_time)
        
        self.current_position = (x, y)
    
    def _square_to_position(self, square: Tuple[int, int]) -> Tuple[float, float]:
        """
        Convert chess square coordinates to physical position in mm.
        
        Args:
            square: (file, rank) where file=0-7, rank=0-7
            
        Returns:
            (x, y) position in mm
        """
        file, rank = square
        
        # Square size: 50mm (400mm board / 8 squares)
        # Add 5mm for LED strip between squares
        square_size = 55.0  # 50mm square + 5mm LED strip
        
        # Center of square
        x = (file * square_size) + (square_size / 2)
        y = (rank * square_size) + (square_size / 2)
        
        return (x, y)
    
    # ==================== LED Control ====================
    
    async def highlight_move(self, move):
        """
        Highlight a move on the LED matrix.
        
        Args:
            move: chess.Move object
        """
        from_square = (move.from_square % 8, move.from_square // 8)
        to_square = (move.to_square % 8, move.to_square // 8)
        
        logger.info(f"Highlighting move: {from_square} -> {to_square}")
        
        command = {
            "cmd": "highlight_squares",
            "squares": [from_square, to_square],
            "color": [0, 255, 0],  # Green
            "duration": 2000  # ms
        }
        
        await self._send_sensor_command(command)
    
    async def flash_error(self):
        """Flash LEDs red to indicate an error"""
        logger.info("Flashing error indication")
        
        command = {
            "cmd": "flash_all",
            "color": [255, 0, 0],  # Red
            "count": 3
        }
        
        await self._send_sensor_command(command)
    
    async def set_led_theme(self, theme: str):
        """Set the LED color theme"""
        command = {
            "cmd": "set_theme",
            "theme": theme
        }
        
        await self._send_sensor_command(command)
    
    # ==================== Communication Protocol ====================
    
    async def _send_sensor_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a command to the sensor ESP32 and wait for response.
        
        Args:
            command: Command dictionary
            
        Returns:
            Response dictionary or None
        """
        # TODO: Implement actual UART communication
        # For now, return mock responses
        
        logger.debug(f"Sensor ESP32 <- {json.dumps(command)}")
        
        # Simulate response delay
        await asyncio.sleep(0.01)
        
        # Mock responses
        if command["cmd"] == "scan_sensors":
            # Return initial board position
            return {"sensors": self._get_initial_board_state()}
        elif command["cmd"] == "read_buttons":
            return {"buttons": []}
        
        return {"status": "ok"}
    
    async def _send_motor_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a command to the motor ESP32 and wait for response.
        
        Args:
            command: Command dictionary
            
        Returns:
            Response dictionary or None
        """
        # TODO: Implement actual UART communication
        
        logger.debug(f"Motor ESP32 <- {json.dumps(command)}")
        
        # Simulate response delay
        await asyncio.sleep(0.01)
        
        return {"status": "ok"}
    
    def _get_initial_board_state(self) -> List[List[bool]]:
        """Get the standard chess starting position sensor state"""
        state = [[False] * 8 for _ in range(8)]
        
        # Ranks 0-1 (white pieces) and 6-7 (black pieces) are occupied
        for file in range(8):
            state[0][file] = True  # White back rank
            state[1][file] = True  # White pawns
            state[6][file] = True  # Black pawns
            state[7][file] = True  # Black back rank
        
        return state
