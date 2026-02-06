"""
Database manager for the Smart Chess Board.
Handles all database operations using SQLite with async support.
"""
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages all database operations for users, games, settings, and move history.
    Uses SQLite with aiosqlite for async operations.
    """
    
    def __init__(self, db_path: str = "chessboard.db"):
        self.db_path = Path(db_path)
        self.connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize database connection and create tables if they don't exist"""
        logger.info(f"Initializing database at {self.db_path}")
        
        # Create database directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        self.connection = await aiosqlite.connect(self.db_path)
        
        # Enable foreign keys
        await self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
        await self._create_tables()
        
        logger.info("Database initialized successfully")
    
    async def _create_tables(self):
        """Create all necessary tables"""
        
        # Table 1: Users
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                email TEXT UNIQUE,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0
            )
        """)
        
        # Table 2: UserSettings
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                -- Motor & Movement
                motor_speed TEXT DEFAULT 'MEDIUM',  -- SLOW/MEDIUM/FAST
                move_animation_speed TEXT DEFAULT 'MEDIUM',
                
                -- Chess Clock
                clock_enabled BOOLEAN DEFAULT 0,
                clock_time_minutes INTEGER DEFAULT 10,
                clock_increment_seconds INTEGER DEFAULT 0,
                
                -- Move Evaluation
                evaluation_enabled BOOLEAN DEFAULT 1,
                evaluation_level TEXT DEFAULT 'BASIC',  -- NONE/BASIC/ADVANCED
                show_blunders BOOLEAN DEFAULT 1,
                show_mistakes BOOLEAN DEFAULT 1,
                show_inaccuracies BOOLEAN DEFAULT 1,
                show_good_moves BOOLEAN DEFAULT 1,
                show_excellent_moves BOOLEAN DEFAULT 1,
                show_brilliant_moves BOOLEAN DEFAULT 1,
                hint_count INTEGER DEFAULT 3,
                
                -- LEDs
                leds_enabled BOOLEAN DEFAULT 1,
                led_brightness INTEGER DEFAULT 128,  -- 0-255
                led_theme TEXT DEFAULT 'CLASSIC',  -- CLASSIC/MODERN/RAINBOW/etc
                highlight_legal_moves BOOLEAN DEFAULT 1,
                highlight_last_move BOOLEAN DEFAULT 1,
                
                -- Engine
                engine_difficulty INTEGER DEFAULT 5,  -- 1-20 Stockfish skill level
                engine_type TEXT DEFAULT 'STOCKFISH',
                
                -- Voice Recognition
                voice_enabled BOOLEAN DEFAULT 1,
                voice_language TEXT DEFAULT 'en-US',
                voice_feedback BOOLEAN DEFAULT 1,
                
                -- UI Preferences
                ui_theme TEXT DEFAULT 'DARK',  -- DARK/LIGHT
                sound_enabled BOOLEAN DEFAULT 1,
                sound_volume INTEGER DEFAULT 70,  -- 0-100
                
                -- Advanced
                auto_queen_promotion BOOLEAN DEFAULT 0,
                confirm_moves BOOLEAN DEFAULT 0,
                
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Table 3: Games
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                white_user_id INTEGER,
                black_user_id INTEGER,  -- NULL for AI
                game_mode TEXT NOT NULL,  -- OFFLINE_PVP/VS_ENGINE/ONLINE_LICHESS
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                result TEXT,  -- WHITE_WIN/BLACK_WIN/DRAW/ABANDONED
                termination TEXT,  -- CHECKMATE/STALEMATE/RESIGNATION/TIME/AGREEMENT
                opening_name TEXT,
                final_fen TEXT,
                
                -- Clock data
                white_time_remaining INTEGER,  -- seconds
                black_time_remaining INTEGER,
                
                -- Online game reference
                lichess_game_id TEXT,
                
                FOREIGN KEY (white_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
                FOREIGN KEY (black_user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
        """)
        
        # Table 4: MoveHistory
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS move_history (
                move_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                move_number INTEGER NOT NULL,
                side TEXT NOT NULL,  -- WHITE/BLACK
                move_notation TEXT NOT NULL,  -- e.g., "e2e4"
                san_notation TEXT,  -- Standard Algebraic Notation: "Nf3"
                fen_after TEXT,  -- Board state after move
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                time_taken INTEGER,  -- milliseconds
                
                -- Move evaluation (from Stockfish)
                evaluation_cp INTEGER,  -- centipawns
                evaluation_mate INTEGER,  -- moves to mate (NULL if not applicable)
                classification TEXT,  -- BRILLIANT/EXCELLENT/GOOD/INACCURACY/MISTAKE/BLUNDER
                
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            )
        """)
        
        # Table 5: Graveyard (piece capture positions)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS graveyard (
                graveyard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                side TEXT NOT NULL,  -- WHITE/BLACK (which side's pieces)
                coordinate TEXT NOT NULL,  -- e.g., "G1", "G2" (graveyard position)
                piece_type TEXT NOT NULL,  -- PAWN/KNIGHT/BISHOP/ROOK/QUEEN
                occupied BOOLEAN DEFAULT 1,
                captured_on_move INTEGER,  -- move number when captured
                
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
            )
        """)
        
        # Table 6: CustomPositions (for board editor)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS custom_positions (
                position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                fen TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_used INTEGER DEFAULT 0,
                
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.commit()
        logger.info("All tables created successfully")
    
    # ==================== User Management ====================
    
    async def create_user(self, username: str, display_name: Optional[str] = None, 
                         email: Optional[str] = None, password_hash: Optional[str] = None) -> int:
        """Create a new user and return user_id"""
        cursor = await self.connection.execute(
            """
            INSERT INTO users (username, display_name, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (username, display_name or username, email, password_hash)
        )
        await self.connection.commit()
        
        user_id = cursor.lastrowid
        
        # Create default settings for new user
        await self.connection.execute(
            "INSERT INTO user_settings (user_id) VALUES (?)",
            (user_id,)
        )
        await self.connection.commit()
        
        logger.info(f"Created user: {username} (ID: {user_id})")
        return user_id
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        async with self.connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        async with self.connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    async def update_user_stats(self, user_id: int, result: str):
        """Update user statistics after a game"""
        if result == "WHITE_WIN":
            await self.connection.execute(
                "UPDATE users SET total_games = total_games + 1, wins = wins + 1 WHERE user_id = ?",
                (user_id,)
            )
        elif result == "BLACK_WIN":
            await self.connection.execute(
                "UPDATE users SET total_games = total_games + 1, losses = losses + 1 WHERE user_id = ?",
                (user_id,)
            )
        elif result == "DRAW":
            await self.connection.execute(
                "UPDATE users SET total_games = total_games + 1, draws = draws + 1 WHERE user_id = ?",
                (user_id,)
            )
        await self.connection.commit()
    
    # ==================== Settings Management ====================
    
    async def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings"""
        async with self.connection.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        """Update user settings"""
        # Build dynamic UPDATE query
        set_clause = ", ".join([f"{key} = ?" for key in settings.keys()])
        values = list(settings.values()) + [user_id]
        
        await self.connection.execute(
            f"UPDATE user_settings SET {set_clause} WHERE user_id = ?",
            values
        )
        await self.connection.commit()
        logger.info(f"Updated settings for user {user_id}")
    
    # ==================== Game Management ====================
    
    async def create_game(self, white_user_id: Optional[int], black_user_id: Optional[int],
                         game_mode: str) -> int:
        """Create a new game record and return game_id"""
        cursor = await self.connection.execute(
            """
            INSERT INTO games (white_user_id, black_user_id, game_mode)
            VALUES (?, ?, ?)
            """,
            (white_user_id, black_user_id, game_mode)
        )
        await self.connection.commit()
        
        game_id = cursor.lastrowid
        logger.info(f"Created game {game_id}: {game_mode}")
        return game_id
    
    async def save_game_result(self, game_id: int, result: str, termination: str = "CHECKMATE",
                               final_fen: Optional[str] = None):
        """Save game result when game ends"""
        await self.connection.execute(
            """
            UPDATE games 
            SET end_time = CURRENT_TIMESTAMP, result = ?, termination = ?, final_fen = ?
            WHERE game_id = ?
            """,
            (result, termination, final_fen, game_id)
        )
        await self.connection.commit()
        logger.info(f"Game {game_id} finished: {result} by {termination}")
    
    async def get_game(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Get game by ID"""
        async with self.connection.execute(
            "SELECT * FROM games WHERE game_id = ?", (game_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    async def get_user_games(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent games for a user"""
        async with self.connection.execute(
            """
            SELECT * FROM games 
            WHERE white_user_id = ? OR black_user_id = ?
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (user_id, user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== Move History ====================
    
    async def save_move(self, game_id: int, move_number: int, side: str,
                       move_notation: str, san_notation: Optional[str] = None,
                       fen_after: Optional[str] = None, time_taken: Optional[int] = None) -> int:
        """Save a move to the database"""
        cursor = await self.connection.execute(
            """
            INSERT INTO move_history 
            (game_id, move_number, side, move_notation, san_notation, fen_after, time_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, move_number, side, move_notation, san_notation, fen_after, time_taken)
        )
        await self.connection.commit()
        return cursor.lastrowid
    
    async def update_move_evaluation(self, move_id: int, evaluation_cp: Optional[int],
                                    evaluation_mate: Optional[int], classification: str):
        """Update move with engine evaluation"""
        await self.connection.execute(
            """
            UPDATE move_history 
            SET evaluation_cp = ?, evaluation_mate = ?, classification = ?
            WHERE move_id = ?
            """,
            (evaluation_cp, evaluation_mate, classification, move_id)
        )
        await self.connection.commit()
    
    async def get_game_moves(self, game_id: int) -> List[Dict[str, Any]]:
        """Get all moves for a game"""
        async with self.connection.execute(
            """
            SELECT * FROM move_history 
            WHERE game_id = ?
            ORDER BY move_number ASC
            """,
            (game_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== Graveyard Management ====================
    
    async def occupy_graveyard_space(self, game_id: int, side: str, coordinate: str,
                                    piece_type: str, move_number: int) -> int:
        """Mark a graveyard position as occupied when a piece is captured"""
        cursor = await self.connection.execute(
            """
            INSERT INTO graveyard (game_id, side, coordinate, piece_type, captured_on_move)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, side, coordinate, piece_type, move_number)
        )
        await self.connection.commit()
        return cursor.lastrowid
    
    async def get_graveyard_state(self, game_id: int) -> List[Dict[str, Any]]:
        """Get current graveyard occupancy for a game"""
        async with self.connection.execute(
            """
            SELECT * FROM graveyard 
            WHERE game_id = ? AND occupied = 1
            ORDER BY captured_on_move ASC
            """,
            (game_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== Custom Positions ====================
    
    async def save_custom_position(self, user_id: int, name: str, fen: str,
                                   description: Optional[str] = None) -> int:
        """Save a custom board position"""
        cursor = await self.connection.execute(
            """
            INSERT INTO custom_positions (user_id, name, fen, description)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, name, fen, description)
        )
        await self.connection.commit()
        return cursor.lastrowid
    
    async def get_user_positions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all custom positions for a user"""
        async with self.connection.execute(
            """
            SELECT * FROM custom_positions 
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== Utility ====================
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            logger.info("Database connection closed")
