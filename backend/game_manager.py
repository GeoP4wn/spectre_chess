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
    
    def __init__(self, mode: str = "VS_ENGINE", settings: Optional[Dict[str, Any]] = None, 
                 human_color: Optional[chess.Color] = None):
        """
        Initialize game manager with specified mode.
        
        Args:
            mode: Game mode (OFFLINE_PVP, VS_ENGINE, ONLINE_LICHESS, ENGINE_VS_ENGINE, ANALYSIS)
            settings: User settings dictionary
            human_color: Which side human plays (WHITE/BLACK/None for PVP). 
                        For ONLINE_LICHESS, None means accept either color from server
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
        
        # For human vs AI games - None means both are AI or both are human
        self.human_color = human_color
        
        # Analysis mode state
        self.analysis_mode = False
        self.analysis_position_index = 0  # Current position in loaded PGN
        
        # Set up players based on mode
        self._setup_players(mode, settings, human_color)
        
        logger.info(f"GameManager initialized: mode={mode}")
    
    def _setup_players(self, mode: str, settings: Optional[Dict[str, Any]], 
                      human_color: Optional[chess.Color]):
        """Set up the input providers based on game mode"""
        if mode == "OFFLINE_PVP":
            # Both players are local humans
            self.white_player = LocalProvider()
            self.black_player = LocalProvider()
            self.human_color = None  # Both are human
            
        elif mode == "VS_ENGINE":
            # Get engine difficulty from settings
            difficulty = settings.get('engine_difficulty', 5) if settings else 5
            
            # If human_color not specified, default to WHITE
            if human_color is None:
                human_color = chess.WHITE
            
            # Set up human and engine based on chosen color
            if human_color == chess.WHITE:
                self.white_player = LocalProvider()
                self.black_player = EngineProvider(difficulty=difficulty)
            else:
                self.white_player = EngineProvider(difficulty=difficulty)
                self.black_player = LocalProvider()
            
            self.human_color = human_color
            
        elif mode == "ONLINE_LICHESS":
            # Lichess token should be stored in settings
            token = settings.get('lichess_token') if settings else None
            lichess_provider = LichessProvider(token=token)
            
            # For online play, the server assigns colors
            # We'll update human_color once the game starts
            # For now, assume we'll be told which side we are
            if human_color == chess.WHITE or human_color is None:
                self.white_player = LocalProvider()
                self.black_player = lichess_provider
            else:
                self.white_player = lichess_provider
                self.black_player = LocalProvider()
            
            self.human_color = human_color  # May be None initially
            
        elif mode == "ENGINE_VS_ENGINE":
            # Both players are engines (for demonstration/analysis)
            difficulty_white = settings.get('engine_difficulty_white', 10) if settings else 10
            difficulty_black = settings.get('engine_difficulty_black', 10) if settings else 10
            
            self.white_player = EngineProvider(difficulty=difficulty_white)
            self.black_player = EngineProvider(difficulty=difficulty_black)
            self.human_color = None  # No human player
            
        elif mode == "ANALYSIS":
            # Analysis mode - can load PGN and step through
            # No active players, moves are manually controlled
            self.white_player = None
            self.black_player = None
            self.human_color = None
            self.analysis_mode = True
            
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
        
        CAPTURE HANDLING:
        Captures happen in a temporal sequence:
        1. Human lifts their piece from square A (A becomes empty)
        2. Human removes opponent's piece from square B (B becomes empty)  
        3. Human places their piece on square B (B becomes occupied)
        
        We need to wait for the full sequence to complete before validating.
        
        NORMAL MOVE:
        1. Piece lifted from square A (A becomes empty)
        2. Piece placed on square B (B becomes occupied)
        
        Args:
            new_state: Current sensor reading
            
        Returns:
            chess.Move object if valid, None if still in progress or invalid
        """
        if self.last_known_state is None:
            return None
        
        # Find squares that changed
        changed_squares = []
        for rank in range(8):
            for file in range(8):
                if self.last_known_state[rank][file] != new_state[rank][file]:
                    square = chess.square(file, 7 - rank)  # Convert to chess.Square
                    is_occupied_now = new_state[rank][file]
                    changed_squares.append((square, is_occupied_now))
        
        # No changes detected
        if len(changed_squares) == 0:
            return None
        
        # Single square change - piece lifted but not yet placed
        # Wait for the full move to complete
        if len(changed_squares) == 1:
            logger.debug(f"Piece in transit - waiting for placement...")
            return None  # Move still in progress
        
        # Two squares changed - normal move OR capture in progress
        if len(changed_squares) == 2:
            from_square = None
            to_square = None
            
            for square, is_occupied in changed_squares:
                if not is_occupied:  # Was occupied, now empty
                    from_square = square
                else:  # Was empty, now occupied
                    to_square = square
            
            # Both squares should be identified
            if from_square is None or to_square is None:
                # This might be capture in progress (two pieces lifted)
                logger.debug(f"Two pieces lifted - capture in progress?")
                return None  # Wait for piece to be placed
            
            # Validate this is actually a legal move
            move = chess.Move(from_square, to_square)
            
            # Check if this move is legal
            if move not in self.board.legal_moves:
                # Maybe it's a capture and we detected it at the wrong time
                logger.debug(f"Move {move.uci()} not legal yet - waiting...")
                return None
            
            # Update last known state
            self.last_known_state = new_state
            
            # Handle pawn promotion
            if self.board.piece_at(from_square) == chess.Piece(chess.PAWN, self.board.turn):
                to_rank = chess.square_rank(to_square)
                if to_rank in [0, 7]:  # Back rank
                    # Default to queen promotion
                    # TODO: Add UI for promotion choice
                    move = chess.Move(from_square, to_square, promotion=chess.QUEEN)
            
            return move
        
        # Three squares changed - this is likely capture sequence
        # Player has lifted their piece (1 empty), removed opponent piece (1 empty),
        # but hasn't placed yet. OR they just placed.
        if len(changed_squares) == 3:
            # Check if this resolves to a valid capture
            # One square should be newly occupied (destination)
            # Two squares should be newly empty (from_square and captured_square)
            
            newly_empty = [sq for sq, occupied in changed_squares if not occupied]
            newly_occupied = [sq for sq, occupied in changed_squares if occupied]
            
            if len(newly_occupied) == 1 and len(newly_empty) == 2:
                # This looks like a capture!
                to_square = newly_occupied[0]
                
                # One of the empty squares was the captured piece
                # The other was where our piece came from
                # We need to figure out which is which using the legal moves
                
                for from_candidate in newly_empty:
                    move = chess.Move(from_candidate, to_square)
                    if move in self.board.legal_moves and self.board.is_capture(move):
                        # This is the valid capture!
                        self.last_known_state = new_state
                        logger.info(f"Capture detected: {move.uci()}")
                        return move
            
            # Still in progress
            logger.debug(f"3 changes detected - capture still in progress")
            return None
        
        # Four squares changed - castling
        if len(changed_squares) == 4:
            # Castling: 4 squares change (king moves 2, rook jumps over)
            self.last_known_state = new_state
            
            moves = list(self.board.legal_moves)
            castling_moves = [m for m in moves if self.board.is_castling(m)]
            
            # Find which castling move matches the changed squares
            for move in castling_moves:
                if self._move_matches_changes(move, changed_squares):
                    logger.info(f"Castling detected: {move.uci()}")
                    return move
        
        # More than 4 changes - something weird happened
        logger.warning(f"Unexpected number of square changes: {len(changed_squares)}")
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
    
    async def get_live_evaluation_for_piece(self, from_square: chess.Square) -> Dict[int, Dict[str, Any]]:
        """
        Get live evaluation for all legal moves from a given square.
        This creates the "lift piece and see colored squares" effect.
        
        Args:
            from_square: The square where the piece is lifted from
            
        Returns:
            Dict mapping to_square -> {
                'move': chess.Move,
                'evaluation_cp': int (centipawns),
                'classification': str (BRILLIANT/EXCELLENT/GOOD/NEUTRAL/INACCURACY/MISTAKE/BLUNDER),
                'color': [r, g, b] (LED color to display)
            }
        """
        logger.info(f"Calculating live evaluation for piece on {chess.square_name(from_square)}")
        
        # Get current position evaluation
        current_eval = await self.evaluate_position()
        current_score = self._extract_cp_score(current_eval.get('score'))
        
        # Find all legal moves from this square
        legal_moves_from_square = [
            move for move in self.board.legal_moves 
            if move.from_square == from_square
        ]
        
        if not legal_moves_from_square:
            logger.warning(f"No legal moves from {chess.square_name(from_square)}")
            return {}
        
        evaluations = {}
        
        # Evaluate each possible destination
        for move in legal_moves_from_square:
            # Make the move temporarily
            self.board.push(move)
            
            # Evaluate the resulting position
            eval_after = await self.evaluate_position()
            score_after = self._extract_cp_score(eval_after.get('score'))
            
            # Undo the move
            self.board.pop()
            
            # Calculate the evaluation delta
            # Positive delta = good for current player
            if self.board.turn == chess.WHITE:
                delta = score_after - current_score
            else:
                delta = current_score - score_after  # Flip for black
            
            # Classify the move based on evaluation delta
            classification, color = self._classify_move_by_delta(delta)
            
            evaluations[move.to_square] = {
                'move': move,
                'evaluation_cp': delta,
                'classification': classification,
                'color': color
            }
        
        logger.info(f"Evaluated {len(evaluations)} possible moves")
        return evaluations
    
    def _extract_cp_score(self, score_str: Optional[str]) -> int:
        """
        Extract centipawn score from Stockfish score string.
        
        Args:
            score_str: String like "PovScore(Cp(+35), WHITE)" or "PovScore(Mate(+3), WHITE)"
            
        Returns:
            Centipawn value (large positive/negative for mate)
        """
        if not score_str:
            return 0
        
        # Handle mate scores
        if "Mate" in score_str:
            # Mate in X moves - return very large value
            if "+" in score_str:
                return 10000  # Winning
            else:
                return -10000  # Losing
        
        # Extract centipawn value
        # Format: "PovScore(Cp(+35), WHITE)"
        try:
            cp_part = score_str.split("Cp(")[1].split(")")[0]
            return int(cp_part)
        except:
            logger.warning(f"Could not parse score: {score_str}")
            return 0
    
    def _classify_move_by_delta(self, delta_cp: int) -> tuple[str, list[int]]:
        """
        Classify a move and assign LED color based on evaluation delta.
        
        Args:
            delta_cp: Centipawn change (positive = good, negative = bad)
            
        Returns:
            (classification, [r, g, b] color)
        """
        # Thresholds based on common chess evaluation guidelines
        if delta_cp >= 300:
            return ("BRILLIANT", [255, 215, 0])      # Gold
        elif delta_cp >= 100:
            return ("EXCELLENT", [0, 255, 0])        # Green
        elif delta_cp >= 0:
            return ("GOOD", [100, 200, 100])         # Light green
        elif delta_cp >= -50:
            return ("NEUTRAL", [200, 200, 200])      # White/gray
        elif delta_cp >= -100:
            return ("INACCURACY", [255, 165, 0])     # Orange
        elif delta_cp >= -300:
            return ("MISTAKE", [255, 100, 0])        # Dark orange
        else:
            return ("BLUNDER", [255, 0, 0])          # Red
    
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
    
    # ==================== Analysis Mode ====================
    
    def load_pgn(self, pgn_string: str) -> bool:
        """
        Load a PGN game for analysis.
        
        Args:
            pgn_string: PGN format game
            
        Returns:
            True if loaded successfully
        """
        try:
            import io
            import chess.pgn
            
            pgn = chess.pgn.read_game(io.StringIO(pgn_string))
            if pgn is None:
                logger.error("Failed to parse PGN")
                return False
            
            # Reset to starting position
            self.board = pgn.board()
            self.move_history = []
            
            # Store all moves from the PGN
            self.pgn_moves = list(pgn.mainline_moves())
            self.analysis_position_index = 0
            
            logger.info(f"Loaded PGN with {len(self.pgn_moves)} moves")
            return True
            
        except Exception as e:
            logger.error(f"Error loading PGN: {e}")
            return False
    
    def step_forward(self) -> Optional[chess.Move]:
        """
        Step forward one move in analysis mode.
        
        Returns:
            The move that was made, or None if at end
        """
        if not self.analysis_mode:
            logger.warning("Not in analysis mode")
            return None
        
        if not hasattr(self, 'pgn_moves'):
            logger.warning("No PGN loaded")
            return None
        
        if self.analysis_position_index >= len(self.pgn_moves):
            logger.info("At end of game")
            return None
        
        move = self.pgn_moves[self.analysis_position_index]
        self.board.push(move)
        self.analysis_position_index += 1
        
        logger.info(f"Stepped forward: {move.uci()} (position {self.analysis_position_index}/{len(self.pgn_moves)})")
        return move
    
    def step_backward(self) -> Optional[chess.Move]:
        """
        Step backward one move in analysis mode.
        
        Returns:
            The move that was undone, or None if at start
        """
        if not self.analysis_mode:
            logger.warning("Not in analysis mode")
            return None
        
        if self.analysis_position_index == 0:
            logger.info("At start of game")
            return None
        
        move = self.board.pop()
        self.analysis_position_index -= 1
        
        logger.info(f"Stepped backward: {move.uci()} (position {self.analysis_position_index}/{len(self.pgn_moves)})")
        return move
    
    def jump_to_position(self, move_number: int) -> bool:
        """
        Jump to a specific position in the loaded game.
        
        Args:
            move_number: Position to jump to (0 = start)
            
        Returns:
            True if successful
        """
        if not self.analysis_mode or not hasattr(self, 'pgn_moves'):
            return False
        
        if move_number < 0 or move_number > len(self.pgn_moves):
            return False
        
        # Reset to start
        self.board.reset()
        self.analysis_position_index = 0
        
        # Replay moves up to target position
        for i in range(move_number):
            self.board.push(self.pgn_moves[i])
            self.analysis_position_index += 1
        
        logger.info(f"Jumped to position {move_number}")
        return True
    
    def enter_play_mode_from_position(self) -> bool:
        """
        Switch from analysis mode to play mode at current position.
        Allows playing out alternative lines from a position.
        
        Returns:
            True if successful
        """
        if not self.analysis_mode:
            return False
        
        # Store the current PGN moves in case we want to return
        if hasattr(self, 'pgn_moves'):
            self.stored_pgn_moves = self.pgn_moves
            self.stored_position_index = self.analysis_position_index
        
        # Switch to play mode
        self.analysis_mode = False
        
        # Set up for human play from this position
        # Keep the current board state
        logger.info(f"Entering play mode from position {self.analysis_position_index}")
        return True
    
    def return_to_analysis(self) -> bool:
        """
        Return to analysis mode from play mode.
        Restores the original PGN position.
        
        Returns:
            True if successful
        """
        if self.analysis_mode:
            return False
        
        if not hasattr(self, 'stored_pgn_moves'):
            logger.warning("No stored position to return to")
            return False
        
        # Restore the PGN state
        self.pgn_moves = self.stored_pgn_moves
        self.analysis_position_index = self.stored_position_index
        
        # Replay to the stored position
        self.jump_to_position(self.stored_position_index)
        
        self.analysis_mode = True
        logger.info("Returned to analysis mode")
        return True
