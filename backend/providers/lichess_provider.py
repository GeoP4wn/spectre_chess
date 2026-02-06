"""
Lichess Provider - Online play via Lichess API.
"""
import chess
import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)


class LichessProvider:
    """
    Provider for online play via Lichess.
    Uses the berserk library to interact with Lichess API.
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize Lichess provider.
        
        Args:
            token: Lichess API token
        """
        self.token = token
        self.client = None
        self.game_id: Optional[str] = None
        self.name = "Lichess Opponent"
        
        if not token:
            logger.warning("No Lichess token provided - online play will not work")
    
    async def _ensure_client(self):
        """Ensure Lichess client is initialized"""
        if self.client is None and self.token:
            try:
                import berserk
                session = berserk.TokenSession(self.token)
                self.client = berserk.Client(session=session)
                logger.info("Lichess client initialized")
            except ImportError:
                logger.error("berserk library not installed. Install with: pip install berserk")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Lichess client: {e}")
                raise
    
    async def create_challenge(self, time_control: str = "10+0") -> str:
        """
        Create a game challenge on Lichess.
        
        Args:
            time_control: Time control (e.g., "10+0" for 10 min no increment)
            
        Returns:
            game_id
        """
        await self._ensure_client()
        
        # TODO: Implement challenge creation
        # This would use the Lichess API to create a game
        logger.info(f"Creating Lichess challenge with time control {time_control}")
        
        # Placeholder
        return "mock_game_id"
    
    async def get_next_move(self, board: chess.Board) -> chess.Move:
        """
        Wait for the opponent's move from Lichess.
        
        Args:
            board: Current chess.Board state
            
        Returns:
            Opponent's move
        """
        await self._ensure_client()
        
        logger.info("Waiting for opponent's move from Lichess...")
        
        # TODO: Implement actual Lichess game stream listening
        # This would poll/stream the game state and return when opponent moves
        
        # For now, just simulate waiting
        await asyncio.sleep(1.0)
        
        # Placeholder - return a random legal move
        import random
        legal_moves = list(board.legal_moves)
        if legal_moves:
            move = random.choice(legal_moves)
            logger.info(f"Lichess opponent played: {move.uci()}")
            return move
        
        raise Exception("No legal moves available")
    
    async def send_move(self, move: chess.Move):
        """
        Send our move to Lichess.
        
        Args:
            move: The move we made
        """
        await self._ensure_client()
        
        logger.info(f"Sending move to Lichess: {move.uci()}")
        
        # TODO: Implement move sending via Lichess API
        # This would use berserk to submit the move
    
    async def shutdown(self):
        """Clean up Lichess connection"""
        logger.info("Lichess provider shutdown")