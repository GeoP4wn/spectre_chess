"""
Local Provider - Human player input from physical board.
"""
import chess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LocalProvider:
    """
    Provider for local human players.
    Moves are detected via Hall Effect sensors on the physical board.
    """
    
    def __init__(self):
        self.name = "Human Player"
    
    async def get_next_move(self, board: chess.Board) -> Optional[chess.Move]:
        """
        For local players, this doesn't actually "get" a move - 
        moves are detected by the sensor system in the main loop.
        
        This method exists to maintain the provider interface.
        """
        # This is handled by the sensor polling loop
        # Just return None to indicate we're waiting for physical input
        return None
    
    async def shutdown(self):
        """No cleanup needed for local provider"""
        pass
