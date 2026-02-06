"""
Main entry point for the Smart Chess Board system.
Implements the async event loop that coordinates all subsystems.
"""
import asyncio
import logging
import signal
from typing import Optional

from statemachine import StateMachine, State
from game_manager import GameManager
from hardware_interface import HardwareInterface
from database_manager import DatabaseManager
from user_manager import UserManager
from voice_service import VoiceService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChessStateMachine(StateMachine):
    """
    State machine for Chess Board Logic Flow
    
    States:
    - BOOT: System startup, hardware checks, homing motors
    - IDLE: Waiting for user login or game start
    - HUMAN_TURN: Waiting for physical sensor changes
    - ROBOT_THINKING: AI calculating next move
    - ROBOT_MOVING: Executing mechanical movements
    - ERROR: Illegal move detected or hardware fault
    - GAME_OVER: Display results, save stats
    """
    
    # Define States
    boot = State(initial=True)
    idle = State()
    human_turn = State()
    robot_thinking = State()
    robot_moving = State()
    error = State()
    game_over = State()

    # Define Transitions
    startup_complete = boot.to(idle)
    start_game = idle.to(human_turn)
    
    # Move processing transitions
    move_detected = human_turn.to(robot_thinking, cond="is_robot_next") | human_turn.to(human_turn)
    
    think_complete = robot_thinking.to(robot_moving)
    move_executed = robot_moving.to(human_turn, cond="game_continues") | robot_moving.to(game_over)
    
    # Error handling
    error_occurred = (human_turn | robot_thinking | robot_moving).to(error)
    error_resolved = error.to(human_turn)
    
    # Game termination
    game_ended = (human_turn | robot_moving).to(game_over)
    reset_game = game_over.to(idle)
    
    # Conditions
    def is_robot_next(self) -> bool:
        """Check if it's the robot's turn to move"""
        return self.model.game_manager and not self.model.game_manager.board.turn == self.model.game_manager.human_color
    
    def game_continues(self) -> bool:
        """Check if game should continue"""
        return self.model.game_manager and not self.model.game_manager.board.is_game_over()


class ChessBoardController:
    """
    Main controller coordinating all subsystems of the chess board.
    Manages the async event loop and state machine.
    """
    
    def __init__(self):
        self.state_machine = ChessStateMachine(model=self)
        self.hardware: Optional[HardwareInterface] = None
        self.game_manager: Optional[GameManager] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.user_manager: Optional[UserManager] = None
        self.voice_service: Optional[VoiceService] = None
        
        # Task management
        self.background_tasks: list[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
        
        # Current game state
        self.current_user_id: Optional[int] = None
        self.pending_move: Optional[str] = None
        
    async def initialize(self):
        """Initialize all subsystems"""
        logger.info("Initializing chess board controller...")
        
        try:
            # Initialize database
            self.db_manager = DatabaseManager()
            await self.db_manager.initialize()
            
            # Initialize user manager
            self.user_manager = UserManager(self.db_manager)
            
            # Initialize hardware interface
            self.hardware = HardwareInterface()
            await self.hardware.initialize()
            
            # Home the motors
            logger.info("Homing motors...")
            await self.hardware.home_motors()
            
            # Initialize voice service
            self.voice_service = VoiceService()
            await self.voice_service.initialize()
            
            logger.info("Initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def start(self):
        """Start the main event loop"""
        logger.info("Starting chess board system...")
        
        # Initialize subsystems
        if not await self.initialize():
            logger.error("Failed to initialize. Exiting.")
            return
        
        # Transition to IDLE state
        self.state_machine.startup_complete()
        
        # Start background tasks
        self.background_tasks = [
            asyncio.create_task(self._sensor_polling_loop(), name="sensor_polling"),
            asyncio.create_task(self._voice_listening_loop(), name="voice_listening"),
            asyncio.create_task(self._ui_update_loop(), name="ui_updates"),
            asyncio.create_task(self._button_monitoring_loop(), name="button_monitoring"),
        ]
        
        logger.info(f"System ready. Current state: {self.state_machine.current_state.id}")
        
        # Main loop - wait for shutdown signal
        try:
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown all subsystems"""
        logger.info("Shutting down chess board system...")
        
        # Cancel all background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Shutdown subsystems
        if self.hardware:
            await self.hardware.shutdown()
        
        if self.voice_service:
            await self.voice_service.shutdown()
        
        if self.db_manager:
            await self.db_manager.close()
        
        logger.info("Shutdown complete")
    
    # ==================== Background Tasks ====================
    
    async def _sensor_polling_loop(self):
        """
        Continuously poll Hall Effect sensors for board state changes.
        Runs every 100ms as specified in the technical report.
        """
        logger.info("Starting sensor polling loop")
        
        try:
            while not self.shutdown_event.is_set():
                # Only poll when in states that care about physical moves
                if self.state_machine.current_state.id in ['human_turn', 'idle']:
                    board_state = await self.hardware.read_sensor_matrix()
                    
                    # Check for changes (delta detection)
                    if self.game_manager and self.game_manager.has_board_changed(board_state):
                        logger.info("Board change detected")
                        await self._handle_board_change(board_state)
                
                # Poll every 100ms
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info("Sensor polling loop cancelled")
    
    async def _voice_listening_loop(self):
        """
        Continuously listen for voice commands using Vosk.
        """
        logger.info("Starting voice listening loop")
        
        try:
            while not self.shutdown_event.is_set():
                if self.voice_service and self.voice_service.is_enabled():
                    command = await self.voice_service.listen_for_command()
                    
                    if command:
                        logger.info(f"Voice command received: {command}")
                        await self._handle_voice_command(command)
                
                await asyncio.sleep(0.05)  # Check for voice every 50ms
                
        except asyncio.CancelledError:
            logger.info("Voice listening loop cancelled")
    
    async def _ui_update_loop(self):
        """
        Send periodic updates to the UI via WebSocket.
        Updates board state, clock, evaluation, etc.
        """
        logger.info("Starting UI update loop")
        
        try:
            while not self.shutdown_event.is_set():
                if self.game_manager:
                    # Prepare UI update payload
                    ui_data = {
                        'state': self.state_machine.current_state.id,
                        'board_fen': self.game_manager.board.fen(),
                        'turn': 'white' if self.game_manager.board.turn else 'black',
                        'game_over': self.game_manager.board.is_game_over(),
                    }
                    
                    # Send to WebSocket clients (will implement later)
                    # await self.websocket_manager.broadcast(ui_data)
                
                await asyncio.sleep(0.5)  # Update UI every 500ms
                
        except asyncio.CancelledError:
            logger.info("UI update loop cancelled")
    
    async def _button_monitoring_loop(self):
        """
        Monitor physical buttons and rotary encoders for input.
        """
        logger.info("Starting button monitoring loop")
        
        try:
            while not self.shutdown_event.is_set():
                button_events = await self.hardware.read_buttons()
                
                for event in button_events:
                    await self._handle_button_event(event)
                
                await asyncio.sleep(0.05)  # Poll buttons every 50ms
                
        except asyncio.CancelledError:
            logger.info("Button monitoring loop cancelled")
    
    # ==================== Event Handlers ====================
    
    async def _handle_board_change(self, new_board_state):
        """
        Process a detected change in the physical board state.
        """
        try:
            if self.state_machine.current_state.id == 'human_turn':
                # Validate the move
                move = self.game_manager.parse_physical_move(new_board_state)
                
                if move and self.game_manager.is_legal_move(move):
                    logger.info(f"Legal move detected: {move}")
                    self.game_manager.make_move(move)
                    
                    # Update LEDs to show the move
                    await self.hardware.highlight_move(move)
                    
                    # Transition to robot's turn if applicable
                    self.state_machine.move_detected()
                    
                    # If it's robot's turn, start thinking
                    if self.state_machine.current_state.id == 'robot_thinking':
                        await self._robot_think()
                else:
                    logger.warning(f"Illegal move detected: {move}")
                    # Flash LEDs red to indicate error
                    await self.hardware.flash_error()
                    self.state_machine.error_occurred()
                    
        except Exception as e:
            logger.error(f"Error handling board change: {e}")
            self.state_machine.error_occurred()
    
    async def _robot_think(self):
        """
        Calculate the robot's next move using the chess engine.
        """
        logger.info("Robot thinking...")
        
        try:
            # Get next move from the current provider (engine, lichess, etc.)
            current_player = self.game_manager.get_current_player()
            move = await current_player.get_next_move(self.game_manager.board)
            
            logger.info(f"Robot chose move: {move}")
            
            # Transition to moving state
            self.state_machine.think_complete()
            
            # Execute the move
            await self._robot_move(move)
            
        except Exception as e:
            logger.error(f"Error during robot thinking: {e}")
            self.state_machine.error_occurred()
    
    async def _robot_move(self, move):
        """
        Execute a physical move with the gantry system.
        """
        logger.info(f"Executing robot move: {move}")
        
        try:
            # Calculate path (handles captures, castling, etc.)
            path = await self.game_manager.calculate_move_path(move)
            
            # Execute each step of the path
            for step in path:
                await self.hardware.move_piece(step['from'], step['to'])
                await asyncio.sleep(0.1)  # Small delay between steps
            
            # Update the internal board state
            self.game_manager.make_move(move)
            
            # Check if game is over
            if self.game_manager.board.is_game_over():
                logger.info("Game over!")
                self.state_machine.move_executed()  # Will transition to game_over
                await self._handle_game_over()
            else:
                # Transition back to human turn
                self.state_machine.move_executed()
                
        except Exception as e:
            logger.error(f"Error during robot move: {e}")
            self.state_machine.error_occurred()
    
    async def _handle_voice_command(self, command: str):
        """
        Process a voice command.
        """
        logger.info(f"Processing voice command: {command}")
        
        # Simple command parsing (you'll expand this)
        command = command.lower()
        
        if "new game" in command:
            await self.start_new_game()
        elif "resign" in command:
            await self.resign_game()
        elif "hint" in command:
            await self.show_hint()
        # Add more commands as needed
    
    async def _handle_button_event(self, event):
        """
        Process a button press or rotary encoder turn.
        """
        logger.info(f"Button event: {event}")
        # Implement button logic here
    
    async def _handle_game_over(self):
        """
        Handle game completion - save to database, show results.
        """
        result = self.game_manager.get_game_result()
        logger.info(f"Game over. Result: {result}")
        
        # Save game to database
        if self.db_manager and self.game_manager.game_id:
            await self.db_manager.save_game_result(
                game_id=self.game_manager.game_id,
                result=result
            )
        
        # Update UI to show result
        # await self.websocket_manager.broadcast({'type': 'game_over', 'result': result})
    
    # ==================== Public API ====================
    
    async def start_new_game(self, mode: str = "VS_ENGINE", user_id: Optional[int] = None):
        """
        Start a new game with specified mode.
        """
        logger.info(f"Starting new game: mode={mode}, user_id={user_id}")
        
        # Load user settings if provided
        settings = None
        if user_id:
            settings = await self.user_manager.get_user_settings(user_id)
            self.current_user_id = user_id
        
        # Create game manager with mode
        self.game_manager = GameManager(mode=mode, settings=settings)
        
        # Create game record in database
        if self.db_manager:
            self.game_manager.game_id = await self.db_manager.create_game(
                white_user_id=user_id,
                black_user_id=None,  # AI or online opponent
                mode=mode
            )
        
        # Transition to human turn
        self.state_machine.start_game()
        logger.info("Game started. Waiting for first move...")
    
    async def resign_game(self):
        """
        Resign the current game.
        """
        if self.game_manager:
            self.game_manager.resign()
            self.state_machine.game_ended()
            await self._handle_game_over()
    
    async def show_hint(self):
        """
        Show a hint for the current position.
        """
        if self.game_manager:
            hint = await self.game_manager.get_hint()
            logger.info(f"Hint: {hint}")
            # Highlight the hint on LEDs
            await self.hardware.highlight_move(hint)


def handle_shutdown_signal(controller: ChessBoardController):
    """Signal handler for graceful shutdown"""
    logger.info("Shutdown signal received")
    controller.shutdown_event.set()


async def main():
    """
    Main entry point for the chess board application.
    """
    logger.info("=" * 60)
    logger.info("Smart Chess Board - Starting")
    logger.info("=" * 60)
    
    # Create controller
    controller = ChessBoardController()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: handle_shutdown_signal(controller))
    
    try:
        # Start the main event loop
        await controller.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Application terminated")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
