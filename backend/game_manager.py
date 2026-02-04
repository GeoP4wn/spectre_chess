import chess
import chess.engine
from providers.local_provider import LocalProvider
from providers.engine_provider import EngineProvider
from providers.lichess_provider import LichessProvider
# provisional!
class GameManager:
    def __init__(self, mode):
        self.board = chess.Board()
        
        # Set the "Input Provider" based on the game mode
        if mode == "OFFLINE_PVP":
            self.white_player = LocalProvider()
            self.black_player = LocalProvider()
        elif mode == "VS_ENGINE":
            self.white_player = LocalProvider()
            self.black_player = EngineProvider(difficulty=5)
        elif mode == "ONLINE_LICHESS":
            self.white_player = LocalProvider()
            self.black_player = LichessProvider(token="...")

    def game_loop(self):
        while not self.board.is_game_over():
            current_player = self.white_player if self.board.turn == chess.WHITE else self.black_player
            
            # This is the magic line: it doesn't care WHAT the provider is.
            move = current_player.get_next_move(self.board) 
            
            self.execute_move(move)
