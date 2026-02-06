"""
Game Manager for the Smart Chess Board.
Handles chess logic, move validation, and integration with chess engines/providers.
"""
import chess
import chess.engine
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import asyncio

from providers.local_provider import LocalProvider
from providers.engine_provider import EngineProvider
from providers.lichess_provider import LichessProvider

logger = logging.getLogger(__name__)


class GameManager:
    """
    Manages the chess game state, move validation, and player providers.
    Acts as the bridge between the physical board and chess logic.
    """
    
    def __init__(self, mode: str = "VS_ENGINE", settings: Optional[Dict[str, Any]] = None):
        """
        Initialize game manager with specified mode.
        
        Args:
            mode: Game mode (OFFLINE_PVP, VS_ENGINE, ONLINE_LICHESS)
            settings: User settings dictionary
        """
        self.board = chess.Board()
        self.mode = mode
        self.settings = settings or {}
        self.game_id: Optional[int] = None
        
        # Track the digital twin of the physical board
        self.physical_board_state: Optional[List[List[bool]]] = None
        self.last_known_state: Optional[List[List[bool]]] = None
        
        # Move history (for UI and analysis)
        self.move_history: List[chess.Move] = []
        
        # For human vs AI games
        self.human_color = chess.WHITE  # Default: human plays white
        
        # Set up players based on mode
        self._setup_players(mode, settings)
        
        logger.info(f"GameManager initialized: mode={mode}")
    
    def _setup_players(self, mode: str, settings: Optional[Dict[str, Any]]):
        """Set up the input providers based on game mode"""
        if mode == "OFFLINE_PVP":
            self.white_player = LocalProvider()
            self.black_player = LocalProvider()
            
        elif mode == "VS_ENGINE":
            self.white_player = LocalProvider()
            
            # Get engine difficulty from settings
            difficulty = settings.get('engine_difficulty', 5) if settings else 5
            self.black_player = EngineProvider(difficulty=difficulty)
            
        elif mode == "ONLINE_LICHESS":
            self.white_player = LocalProvider()
            
            # Lichess token should be stored in settings
            token = settings.get('lichess_token') if settings else None
            self.black_player = LichessProvider(token=token)
        else:
            raise ValueError(f"Unknown game mode: {mode}")
    
    # ==================== Board State Management ====================
    
    def has_board_changed(self, new_state: List[List[bool]]) -> bool:
        """
        Check if the physical board state has changed.
        
        Args:
            new_state: 8x8 boolean matrix from Hall Effect sensors
            
        Returns:
            True if state has changed since last reading
        """
        if self.last_known_state is None:
            self.last_known_state = new_state
            return False
        
        changed = new_state != self.last_known_state
        
        if changed:
            self.physical_board_state = new_state
            
        return changed
    
    def parse_physical_move(self, new_state: List[List[bool]]) -> Optional[chess.Move]:
        """
        Parse a physical board change into a chess move.
        
        This uses the "digital twin" approach: compare the before/after sensor state
        to determine which squares changed, then validate against legal moves.
        
        Args:
            new_state: Current sensor reading
            
        Returns:
            chess.Move object if valid, None otherwise
        """
        if self.last_known_state is None:
            return None
        
        # Find squares that changed
        changed_squares = []
        for rank in range(8):
            for file in range(8):
                if self.last_known_state[rank][file] != new_state[rank][file]:
                    square = chess.square(file, 7 - rank)  # Convert to chess.Square
                    changed_squares.append((square, new_state[rank][file]))
        
        # Update last known state
        self.last_known_state = new_state
        
        # Logic to determine the move
        # Normal move: one square went from occupied to empty (from_square)
        #              one square went from empty to occupied (to_square)
        
        if len(changed_squares) == 2:
            # Normal move or capture
            from_square = None
            to_square = None
            
            for square, is_occupied in changed_squares:
                if not is_occupied:  # Was occupied, now empty
                    from_square = square
                else:  # Was empty, now occupied
                    to_square = square
            
            if from_square is not None and to_square is not None:
                move = chess.Move(from_square, to_square)
                
                # Check for promotion (if pawn reaches back rank)
                if self.board.piece_at(from_square) == chess.Piece(chess.PAWN, self.board.turn):
                    to_rank = chess.square_rank(to_square)
                    if to_rank in [0, 7]:  # Back rank
                        # Default to queen promotion
                        # TODO: Add UI for promotion choice
                        move = chess.Move(from_square, to_square, promotion=chess.QUEEN)
                
                return move
        
        elif len(changed_squares) == 4:
            # Castling: 4 squares change (king moves 2, rook jumps over)
            # Detect castling moves and construct the move
            moves = list(self.board.legal_moves)
            castling_moves = [m for m in moves if self.board.is_castling(m)]
            
            # Find which castling move matches the changed squares
            for move in castling_moves:
                if self._move_matches_changes(move, changed_squares):
                    return move
        
        logger.warning(f"Could not parse move from {len(changed_squares)} changed squares")
        return None
    
    def _move_matches_changes(self, move: chess.Move, changed_squares: List[Tuple[int, bool]]) -> bool:
        """Helper to check if a move matches the observed square changes"""
        # This is a simplified check - you might need to make this more robust
        changed_square_nums = {sq for sq, _ in changed_squares}
        
        # For castling, check if the king and rook squares are in the changes
        if self.board.is_castling(move):
            # Get the squares involved in this castling move
            from_sq = move.from_square
            to_sq = move.to_square
            
            # Rook squares depend on which side
            if to_sq > from_sq:  # Kingside
                rook_from = from_sq + 3
                rook_to = from_sq + 1
            else:  # Queenside
                rook_from = from_sq - 4
                rook_to = from_sq - 1
            
            expected = {from_sq, to_sq, rook_from, rook_to}
            return changed_square_nums == expected
        
        return False
    
    # ==================== Move Validation & Execution ====================
    
    def is_legal_move(self, move: chess.Move) -> bool:
        """Check if a move is legal in the current position"""
        return move in self.board.legal_moves
    
    def make_move(self, move: chess.Move) -> bool:
        """
        Execute a move on the internal board.
        
        Args:
            move: chess.Move to execute
            
        Returns:
            True if move was successful
        """
        if not self.is_legal_move(move):
            logger.warning(f"Attempted illegal move: {move}")
            return False
        
        # Push the move
        self.board.push(move)
        self.move_history.append(move)
        
        logger.info(f"Move executed: {move.uci()} (SAN: {self.board.san(move)})")
        return True
    
    def undo_move(self) -> Optional[chess.Move]:
        """Undo the last move"""
        if len(self.board.move_stack) > 0:
            move = self.board.pop()
            self.move_history.pop()
            logger.info(f"Move undone: {move.uci()}")
            return move
        return None
    
    # ==================== Player/Provider Interface ====================
    
    def get_current_player(self):
        """Get the current player's provider"""
        if self.board.turn == chess.WHITE:
            return self.white_player
        else:
            return self.black_player
    
    async def get_hint(self) -> Optional[chess.Move]:
        """
        Get a hint for the current position.
        Uses the engine even if playing PvP.
        """
        # Temporarily create an engine provider
        hint_engine = EngineProvider(difficulty=15)
        try:
            hint_move = await hint_engine.get_next_move(self.board)
            logger.info(f"Hint: {hint_move.uci()}")
            return hint_move
        except Exception as e:
            logger.error(f"Error getting hint: {e}")
            return None
        finally:
            await hint_engine.shutdown()
    
    # ==================== Path Calculation ====================
    
    async def calculate_move_path(self, move: chess.Move) -> List[Dict[str, Any]]:
        """
        Calculate the physical path for executing a move.
        Handles captures, castling, and complex piece movements.
        
        Returns:
            List of movement steps with 'from', 'to', 'action' (move/capture)
        """
        path = []
        
        # Check if it's a capture
        if self.board.is_capture(move):
            # First, remove the captured piece
            captured_square = move.to_square
            
            # Find an empty graveyard spot
            graveyard_spot = await self._find_empty_graveyard_spot(
                side=not self.board.turn  # Opponent's piece
            )
            
            path.append({
                'from': self._square_to_coords(captured_square),
                'to': graveyard_spot,
                'action': 'capture'
            })
        
        # Check if it's castling
        if self.board.is_castling(move):
            # Castling requires moving both king and rook
            king_from = move.from_square
            king_to = move.to_square
            
            # Determine rook movement
            if king_to > king_from:  # Kingside
                rook_from = king_from + 3
                rook_to = king_from + 1
            else:  # Queenside
                rook_from = king_from - 4
                rook_to = king_from - 1
            
            # Move rook first, then king
            path.append({
                'from': self._square_to_coords(rook_from),
                'to': self._square_to_coords(rook_to),
                'action': 'castle_rook'
            })
            path.append({
                'from': self._square_to_coords(king_from),
                'to': self._square_to_coords(king_to),
                'action': 'castle_king'
            })
        else:
            # Normal move
            path.append({
                'from': self._square_to_coords(move.from_square),
                'to': self._square_to_coords(move.to_square),
                'action': 'move'
            })
        
        return path
    
    async def _find_empty_graveyard_spot(self, side: chess.Color) -> Tuple[int, int]:
        """
        Find an empty graveyard position.
        
        Args:
            side: Which side's graveyard (WHITE or BLACK)
            
        Returns:
            (x, y) coordinate in graveyard zone
        """
        # This is a placeholder - you'll need to implement graveyard tracking
        # For now, just return a dummy position
        
        # Graveyard zones (from technical report):
        # - Along long sides: 51.5mm
        # - Along short sides: 48.5mm
        
        # Simplified: return sequential positions along the top/bottom
        if side == chess.WHITE:
            # Black pieces captured - top graveyard
            return (-1, 0)  # Placeholder
        else:
            # White pieces captured - bottom graveyard
            return (-1, 7)  # Placeholder
    
    def _square_to_coords(self, square: int) -> Tuple[int, int]:
        """Convert chess.Square to (x, y) coordinates"""
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        return (file, rank)
    
    # ==================== Game State ====================
    
    def get_game_result(self) -> str:
        """
        Get the result of the game.
        
        Returns:
            "WHITE_WIN", "BLACK_WIN", "DRAW", or "IN_PROGRESS"
        """
        if not self.board.is_game_over():
            return "IN_PROGRESS"
        
        outcome = self.board.outcome()
        if outcome is None:
            return "DRAW"
        
        if outcome.winner == chess.WHITE:
            return "WHITE_WIN"
        elif outcome.winner == chess.BLACK:
            return "BLACK_WIN"
        else:
            return "DRAW"
    
    def resign(self):
        """Resign the current game"""
        # Mark game as resigned (the opposite color wins)
        logger.info(f"{'White' if self.board.turn else 'Black'} resigned")
        # The game is considered over
    
    def get_fen(self) -> str:
        """Get current board position in FEN notation"""
        return self.board.fen()
    
    def get_pgn(self) -> str:
        """Get game in PGN format"""
        # TODO: Implement PGN export
        return ""
    
    # ==================== Analysis ====================
    
    async def evaluate_position(self) -> Dict[str, Any]:
        """
        Get engine evaluation of current position.
        
        Returns:
            Dict with 'score', 'best_move', 'pv' (principal variation)
        """
        # Use Stockfish to evaluate
        engine_path = Path("/usr/games/stockfish")  # Default Stockfish path on Linux
        
        if not engine_path.exists():
            logger.warning("Stockfish not found")
            return {}
        
        transport, engine = await chess.engine.popen_uci(str(engine_path))
        
        try:
            info = await engine.analyse(self.board, chess.engine.Limit(time=0.1))
            
            score = info.get("score")
            best_move = info.get("pv", [None])[0] if "pv" in info else None
            
            return {
                'score': str(score),
                'best_move': best_move.uci() if best_move else None,
                'pv': [m.uci() for m in info.get("pv", [])]
            }
        finally:
            await engine.quit()
    
    async def classify_move(self, move: chess.Move) -> str:
        """
        Classify a move as brilliant/good/inaccuracy/mistake/blunder.
        
        This requires comparing the evaluation before and after the move.
        """
        # Get evaluation before move
        eval_before = await self.evaluate_position()
        
        # Make move temporarily
        self.board.push(move)
        
        # Get evaluation after move
        eval_after = await self.evaluate_position()
        
        # Undo move
        self.board.pop()
        
        # Compare evaluations and classify
        # (This is simplified - real implementation would be more sophisticated)
        
        # TODO: Implement proper move classification logic
        
        return "GOOD"  # Placeholder
