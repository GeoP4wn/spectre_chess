"""
FastAPI Web Server for Chess Board Web UI
Provides WebSocket for real-time updates and REST API for settings.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

app = FastAPI(title="Spectre Chess API", version="1.0.0")

# Enable CORS for React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Send message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

manager = ConnectionManager()

# Pydantic models for API
class UserSettings(BaseModel):
    motor_speed: str = "MEDIUM"
    leds_enabled: bool = True
    led_brightness: int = 128
    led_theme: str = "CLASSIC"
    highlight_legal_moves: bool = True
    highlight_last_move: bool = True
    evaluation_enabled: bool = True
    show_blunders: bool = True
    show_mistakes: bool = True
    hint_count: int = 3
    engine_difficulty: int = 5
    voice_enabled: bool = False
    sound_enabled: bool = True
    sound_volume: int = 70

class GameInfo(BaseModel):
    game_id: Optional[int]
    mode: str
    white_player: str
    black_player: str
    current_turn: str
    move_count: int
    status: str
    fen: str

# Global state (will be replaced with controller reference)
current_game: Optional[GameInfo] = None
current_settings: UserSettings = UserSettings()

# ==================== WebSocket Endpoint ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time board updates"""
    await manager.connect(websocket)
    
    try:
        # Send initial state
        await manager.send_personal({
            "type": "init",
            "game": current_game.dict() if current_game else None,
            "settings": current_settings.dict()
        }, websocket)
        
        # Listen for client messages
        while True:
            data = await websocket.receive_json()
            
            # Handle client commands
            if data.get("type") == "ping":
                await manager.send_personal({"type": "pong"}, websocket)
            
            elif data.get("type") == "request_hint":
                # TODO: Trigger hint from controller
                await manager.broadcast({
                    "type": "hint",
                    "move": "e2e4"  # Placeholder
                })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# ==================== REST API Endpoints ====================

@app.get("/")
async def root():
    """Health check"""
    return {"status": "online", "name": "Spectre Chess API"}

@app.get("/api/game/current")
async def get_current_game() -> Dict[str, Any]:
    """Get current game state"""
    if current_game:
        return current_game.dict()
    return {"game": None}

@app.get("/api/settings")
async def get_settings() -> UserSettings:
    """Get current settings"""
    return current_settings

@app.put("/api/settings")
async def update_settings(settings: UserSettings) -> Dict[str, str]:
    """Update settings"""
    global current_settings
    current_settings = settings
    
    # Broadcast to all clients
    await manager.broadcast({
        "type": "settings_updated",
        "settings": settings.dict()
    })
    
    # TODO: Apply settings to controller
    
    return {"status": "success"}

@app.post("/api/game/new")
async def new_game(mode: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Start a new game"""
    # TODO: Trigger game start in controller
    global current_game
    current_game = GameInfo(
        game_id=1,
        mode=mode,
        white_player="Player 1",
        black_player="AI" if mode == "VS_ENGINE" else "Player 2",
        current_turn="white",
        move_count=0,
        status="in_progress",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    
    await manager.broadcast({
        "type": "game_started",
        "game": current_game.dict()
    })
    
    return {"status": "success", "game_id": current_game.game_id}

@app.post("/api/game/resign")
async def resign_game() -> Dict[str, str]:
    """Resign current game"""
    # TODO: Trigger resignation in controller
    await manager.broadcast({
        "type": "game_over",
        "result": "resignation"
    })
    return {"status": "success"}

@app.get("/api/game/history")
async def get_game_history(user_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Get game history"""
    # TODO: Query from database
    return []

@app.get("/api/game/{game_id}/moves")
async def get_game_moves(game_id: int) -> List[Dict[str, Any]]:
    """Get moves for a specific game"""
    # TODO: Query from database
    return []

@app.post("/api/board/led/theme")
async def set_led_theme(theme: str) -> Dict[str, str]:
    """Set LED theme"""
    # TODO: Send to hardware controller
    await manager.broadcast({
        "type": "led_theme_changed",
        "theme": theme
    })
    return {"status": "success"}

@app.post("/api/board/led/brightness")
async def set_led_brightness(brightness: int) -> Dict[str, str]:
    """Set LED brightness (0-255)"""
    # TODO: Send to hardware controller
    return {"status": "success"}

# ==================== Helper Functions ====================

async def broadcast_board_state(fen: str, last_move: Optional[str] = None):
    """Broadcast board state update to all clients"""
    await manager.broadcast({
        "type": "board_update",
        "fen": fen,
        "last_move": last_move,
        "timestamp": datetime.now().isoformat()
    })

async def broadcast_move_evaluation(move: str, evaluation: Dict[str, Any]):
    """Broadcast move evaluation"""
    await manager.broadcast({
        "type": "move_evaluation",
        "move": move,
        "evaluation": evaluation
    })

async def broadcast_error(message: str):
    """Broadcast error message"""
    await manager.broadcast({
        "type": "error",
        "message": message,
        "timestamp": datetime.now().isoformat()
    })

# Mount static files (React build)
# app.mount("/", StaticFiles(directory="web-ui/build", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
