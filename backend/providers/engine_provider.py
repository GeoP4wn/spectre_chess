"""
Engine Provider - Stockfish chess engine.
"""
import chess
import chess.engine
import logging
from typing import Optional
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


class EngineProvider:
    """
    Provider for Stockfish chess engine.
    Calculates moves based on difficulty setting.
    """
    
    def __init__(self, difficulty: int = 5):
        """
        Initialize engine provider.
        
        Args:
            difficulty: Skill level 0-20 (0=easiest, 20=strongest)
        """
        self.difficulty = max(0, min(20, difficulty))
        self.engine = None
        self.transport = None
        self.name = f"Stockfish (Level {self.difficulty})"
        
    async def _ensure_engine(self):
        """Ensure engine is initialized"""
        if self.engine is None:
            # Try common Stockfish paths
            stockfish_paths = [
                Path("/usr/games/stockfish"),
                Path("/usr/local/bin/stockfish"),
                Path("/opt/homebrew/bin/stockfish"),
                Path("stockfish")
            ]
            
            stockfish_path = None
            for path in stockfish_paths:
                if path.exists():
                    stockfish_path = path
                    break
            
            if stockfish_path is None:
                logger.error("Stockfish not found! Install it with: sudo apt install stockfish")
                raise FileNotFoundError("Stockfish engine not found")
            
            logger.info(f"Starting Stockfish from {stockfish_path}")
            self.transport, self.engine = await chess.engine.popen_uci(str(stockfish_path))
            
            # Set skill level
            await self.engine.configure({"Skill Level": self.difficulty})
            
            logger.info(f"Stockfish initialized at skill level {self.difficulty}")
    
    async def get_next_move(self, board: chess.Board) -> chess.Move:
        """
        Calculate the best move for the current position.
        
        Args:
            board: Current chess.Board state
            
        Returns:
            Best move according to the engine
        """
        await self._ensure_engine()
        
        # Calculate time based on difficulty (higher = more time)
        think_time = 0.1 + (self.difficulty * 0.05)  # 0.1s to 1.1s
        
        logger.info(f"Stockfish thinking (difficulty={self.difficulty}, time={think_time}s)...")
        
        result = await self.engine.play(
            board,
            chess.engine.Limit(time=think_time)
        )
        
        logger.info(f"Stockfish chose: {result.move.uci()}")
        return result.move
    
    async def shutdown(self):
        """Clean up engine resources"""
        if self.engine:
            await self.engine.quit()
            logger.info("Stockfish engine shutdown")