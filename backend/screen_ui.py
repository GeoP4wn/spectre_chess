"""
HDMI Screen UI - Main Interface
Simple, touch-friendly interface for game setup and chess clock.

Screens:
1. User Selection
2. Game Mode Selection
3. Quick Settings
4. Game Clock & Status
"""
import pygame
import sys
from enum import Enum
from typing import Optional, Tuple, List
import asyncio
from datetime import datetime, timedelta

# Initialize Pygame
pygame.init()

# Screen configuration
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 1024
FPS = 60

# Colors (Material Design inspired)
class Colors:
    BACKGROUND = (18, 18, 18)        # Dark background
    SURFACE = (30, 30, 30)           # Card background
    PRIMARY = (129, 199, 132)        # Green
    SECONDARY = (144, 202, 249)      # Light blue
    ACCENT = (255, 193, 7)           # Amber
    ERROR = (239, 83, 80)            # Red
    TEXT_PRIMARY = (255, 255, 255)   # White
    TEXT_SECONDARY = (158, 158, 158) # Gray
    WHITE = (255, 255, 255)
    BLACK = (33, 33, 33)
    
    # Clock colors
    WHITE_CLOCK = (240, 240, 240)
    BLACK_CLOCK = (60, 60, 60)
    ACTIVE_CLOCK = PRIMARY
    INACTIVE_CLOCK = (100, 100, 100)

# Fonts (will be initialized after pygame.init())
class Fonts:
    title = None
    large = None
    medium = None
    small = None
    clock = None
    _initialized = False
    
    @classmethod
    def init(cls):
        if cls._initialized:
            return
        try:
            cls.title = pygame.font.Font(None, 72)
            cls.large = pygame.font.Font(None, 56)
            cls.medium = pygame.font.Font(None, 40)
            cls.small = pygame.font.Font(None, 32)
            cls.clock = pygame.font.Font(None, 120)
            cls._initialized = True
        except Exception as e:
            # Fall back to system font if default font fails
            import logging
            logging.warning(f"Failed to load default font, using system font: {e}")
            cls.title = pygame.font.SysFont('arial', 72)
            cls.large = pygame.font.SysFont('arial', 56)
            cls.medium = pygame.font.SysFont('arial', 40)
            cls.small = pygame.font.SysFont('arial', 32)
            cls.clock = pygame.font.SysFont('arial', 120)
            cls._initialized = True

class Screen(Enum):
    USER_SELECT = 1
    MODE_SELECT = 2
    SETTINGS = 3
    GAME_CLOCK = 4

class Button:
    """Simple button with touch support"""
    def __init__(self, x: int, y: int, width: int, height: int, 
                 text: str, color: Tuple[int, int, int] = Colors.PRIMARY):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover = False
        self.pressed = False
        
    def draw(self, surface: pygame.Surface):
        # Draw button background
        color = self.color if not self.hover else tuple(min(c + 30, 255) for c in self.color)
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        
        # Draw border if pressed
        if self.pressed:
            pygame.draw.rect(surface, Colors.WHITE, self.rect, 3, border_radius=8)
        
        # Draw text
        text_surface = Fonts.medium.render(self.text, True, Colors.WHITE)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if button was clicked"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                return False
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed and self.rect.collidepoint(event.pos):
                self.pressed = False
                return True
            self.pressed = False
        elif event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        
        return False

class ChessClockUI:
    """Chess clock display with time tracking"""
    def __init__(self):
        self.white_time = timedelta(minutes=10)
        self.black_time = timedelta(minutes=10)
        self.white_active = True
        self.paused = True
        self.last_update = datetime.now()
        
    def update(self):
        """Update clock times"""
        if self.paused:
            return
            
        now = datetime.now()
        delta = now - self.last_update
        
        if self.white_active:
            self.white_time -= delta
        else:
            self.black_time -= delta
            
        self.last_update = now
        
        # Check for time out
        if self.white_time.total_seconds() <= 0:
            self.white_time = timedelta(0)
            self.paused = True
        elif self.black_time.total_seconds() <= 0:
            self.black_time = timedelta(0)
            self.paused = True
    
    def toggle_turn(self):
        """Switch active player"""
        if not self.paused:
            self.white_active = not self.white_active
            self.last_update = datetime.now()
    
    def start(self):
        """Start the clock"""
        self.paused = False
        self.last_update = datetime.now()
    
    def pause(self):
        """Pause the clock"""
        self.paused = True
    
    def reset(self, minutes: int = 10):
        """Reset clock to initial time"""
        self.white_time = timedelta(minutes=minutes)
        self.black_time = timedelta(minutes=minutes)
        self.white_active = True
        self.paused = True
    
    def format_time(self, time: timedelta) -> str:
        """Format time as MM:SS"""
        total_seconds = int(time.total_seconds())
        if total_seconds < 0:
            return "00:00"
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def draw(self, surface: pygame.Surface):
        """Draw chess clocks"""
        # White clock (top)
        white_rect = pygame.Rect(50, 50, SCREEN_WIDTH - 100, 200)
        white_color = Colors.WHITE_CLOCK if self.white_active else Colors.INACTIVE_CLOCK
        pygame.draw.rect(surface, white_color, white_rect, border_radius=12)
        
        if self.white_active and not self.paused:
            pygame.draw.rect(surface, Colors.ACTIVE_CLOCK, white_rect, 5, border_radius=12)
        
        white_text = Fonts.clock.render(self.format_time(self.white_time), True, Colors.BLACK)
        white_text_rect = white_text.get_rect(center=white_rect.center)
        surface.blit(white_text, white_text_rect)
        
        # White label
        label = Fonts.medium.render("WHITE", True, Colors.TEXT_SECONDARY)
        surface.blit(label, (70, 60))
        
        # Black clock (bottom)
        black_rect = pygame.Rect(50, 350, SCREEN_WIDTH - 100, 200)
        black_color = Colors.BLACK_CLOCK if not self.white_active else Colors.INACTIVE_CLOCK
        pygame.draw.rect(surface, black_color, black_rect, border_radius=12)
        
        if not self.white_active and not self.paused:
            pygame.draw.rect(surface, Colors.ACTIVE_CLOCK, black_rect, 5, border_radius=12)
        
        black_text = Fonts.clock.render(self.format_time(self.black_time), True, Colors.WHITE)
        black_text_rect = black_text.get_rect(center=black_rect.center)
        surface.blit(black_text, black_text_rect)
        
        # Black label
        label = Fonts.medium.render("BLACK", True, Colors.TEXT_SECONDARY)
        surface.blit(label, (70, 360))

class ScreenUI:
    """Main screen UI controller"""
    
    def __init__(self, controller):
        self.controller = controller
        
        # Initialize pygame if not already done
        if not pygame.get_init():
            pygame.init()
        
        # Initialize font system specifically
        if not pygame.font.get_init():
            pygame.font.init()
        
        try:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            pygame.display.set_caption("Spectre Chess")
        except Exception as e:
            import logging
            logging.error(f"Failed to create display: {e}")
            logging.info("Attempting to create display without hardware acceleration...")
            import os
            os.environ['SDL_VIDEODRIVER'] = 'dummy'  # Fallback for headless systems
            pygame.display.init()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        self.clock = pygame.time.Clock()
        
        # Initialize fonts after pygame is ready
        Fonts.init()
        
        # Current screen
        self.current_screen = Screen.USER_SELECT
        
        # UI state
        self.selected_user = None
        self.selected_mode = None
        self.clock_time = 10
        self.clock_increment = 0
        
        # Chess clock
        self.chess_clock = ChessClockUI()
        
        # Error message
        self.error_message = None
        self.error_time = None
        
        # Initialize screens
        self._init_user_select()
        self._init_mode_select()
        self._init_settings()
        self._init_game_clock()
    
    def _init_user_select(self):
        """Initialize user selection screen"""
        self.user_buttons = []
        
        # Guest button
        self.user_buttons.append(
            Button(SCREEN_WIDTH//2 - 200, 200, 400, 80, "Play as Guest", Colors.PRIMARY)
        )
        
        # Recent users (will be populated from database)
        self.recent_users = ["Player 1", "Player 2", "Player 3"]
        y = 320
        for user in self.recent_users:
            self.user_buttons.append(
                Button(SCREEN_WIDTH//2 - 200, y, 400, 70, user, Colors.SECONDARY)
            )
            y += 90
        
        # New user button
        self.new_user_btn = Button(50, SCREEN_HEIGHT - 100, 200, 60, "New User", Colors.ACCENT)
    
    def _init_mode_select(self):
        """Initialize game mode selection screen"""
        self.mode_buttons = [
            Button(SCREEN_WIDTH//2 - 250, 150, 500, 100, "Play vs AI", Colors.PRIMARY),
            Button(SCREEN_WIDTH//2 - 250, 270, 500, 100, "Two Players", Colors.SECONDARY),
            Button(SCREEN_WIDTH//2 - 250, 390, 500, 100, "Online (Lichess)", Colors.ACCENT),
        ]
        self.back_btn = Button(50, SCREEN_HEIGHT - 100, 150, 60, "← Back", Colors.TEXT_SECONDARY)
    
    def _init_settings(self):
        """Initialize quick settings screen"""
        # Clock time buttons
        self.clock_buttons = [
            Button(100, 200, 120, 80, "3 min", Colors.PRIMARY),
            Button(240, 200, 120, 80, "5 min", Colors.PRIMARY),
            Button(380, 200, 120, 80, "10 min", Colors.PRIMARY),
            Button(520, 200, 120, 80, "15 min", Colors.PRIMARY),
            Button(660, 200, 120, 80, "30 min", Colors.PRIMARY),
        ]
        self.clock_times = [3, 5, 10, 15, 30]
        
        # Increment buttons
        self.increment_buttons = [
            Button(100, 350, 120, 80, "0 sec", Colors.SECONDARY),
            Button(240, 350, 120, 80, "2 sec", Colors.SECONDARY),
            Button(380, 350, 120, 80, "5 sec", Colors.SECONDARY),
            Button(520, 350, 120, 80, "10 sec", Colors.SECONDARY),
        ]
        self.increments = [0, 2, 5, 10]
        
        # Start game button
        self.start_game_btn = Button(SCREEN_WIDTH//2 - 200, 480, 400, 80, "Start Game →", Colors.ACTIVE_CLOCK)
        self.settings_back_btn = Button(50, SCREEN_HEIGHT - 100, 150, 60, "← Back", Colors.TEXT_SECONDARY)
    
    def _init_game_clock(self):
        """Initialize game clock screen"""
        self.pause_btn = Button(SCREEN_WIDTH - 200, SCREEN_HEIGHT - 100, 150, 60, "⏸ Pause", Colors.ACCENT)
        self.resign_btn = Button(50, SCREEN_HEIGHT - 100, 150, 60, "Resign", Colors.ERROR)
    
    def draw_user_select(self):
        """Draw user selection screen"""
        # Title
        title = Fonts.title.render("Select Player", True, Colors.PRIMARY)
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 80))
        self.screen.blit(title, title_rect)
        
        # Buttons
        for btn in self.user_buttons:
            btn.draw(self.screen)
        self.new_user_btn.draw(self.screen)
    
    def draw_mode_select(self):
        """Draw game mode selection screen"""
        # Title
        title = Fonts.title.render("Game Mode", True, Colors.PRIMARY)
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 80))
        self.screen.blit(title, title_rect)
        
        # User info
        user_text = Fonts.small.render(f"Player: {self.selected_user}", True, Colors.TEXT_SECONDARY)
        self.screen.blit(user_text, (SCREEN_WIDTH//2 - user_text.get_width()//2, 120))
        
        # Buttons
        for btn in self.mode_buttons:
            btn.draw(self.screen)
        self.back_btn.draw(self.screen)
    
    def draw_settings(self):
        """Draw quick settings screen"""
        # Title
        title = Fonts.large.render("Quick Setup", True, Colors.PRIMARY)
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 60))
        self.screen.blit(title, title_rect)
        
        # Clock time section
        label = Fonts.medium.render("Time Control", True, Colors.TEXT_PRIMARY)
        self.screen.blit(label, (100, 140))
        
        for i, btn in enumerate(self.clock_buttons):
            if self.clock_times[i] == self.clock_time:
                btn.color = Colors.ACTIVE_CLOCK
            else:
                btn.color = Colors.PRIMARY
            btn.draw(self.screen)
        
        # Increment section
        label = Fonts.medium.render("Increment", True, Colors.TEXT_PRIMARY)
        self.screen.blit(label, (100, 290))
        
        for i, btn in enumerate(self.increment_buttons):
            if self.increments[i] == self.clock_increment:
                btn.color = Colors.ACTIVE_CLOCK
            else:
                btn.color = Colors.SECONDARY
            btn.draw(self.screen)
        
        # Start button
        self.start_game_btn.draw(self.screen)
        self.settings_back_btn.draw(self.screen)
    
    def draw_game_clock(self):
        """Draw game clock screen"""
        # Draw chess clocks
        self.chess_clock.draw(self.screen)
        
        # Control buttons
        if self.chess_clock.paused:
            play_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 100, 200, 60, "▶ Resume", Colors.ACTIVE_CLOCK)
            play_btn.draw(self.screen)
        else:
            self.pause_btn.draw(self.screen)
        
        self.resign_btn.draw(self.screen)
        
        # Error message if present
        if self.error_message and self.error_time:
            elapsed = (datetime.now() - self.error_time).total_seconds()
            if elapsed < 3:  # Show for 3 seconds
                error_surf = pygame.Surface((SCREEN_WIDTH - 100, 80))
                error_surf.fill(Colors.ERROR)
                error_surf.set_alpha(int(255 * (1 - elapsed/3)))
                
                text = Fonts.medium.render(self.error_message, True, Colors.WHITE)
                text_rect = text.get_rect(center=(error_surf.get_width()//2, 40))
                error_surf.blit(text, text_rect)
                
                self.screen.blit(error_surf, (50, SCREEN_HEIGHT//2 - 40))
            else:
                self.error_message = None
    
    def show_error(self, message: str):
        """Display error message"""
        self.error_message = message
        self.error_time = datetime.now()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if self.current_screen == Screen.USER_SELECT:
                self._handle_user_select(event)
            elif self.current_screen == Screen.MODE_SELECT:
                self._handle_mode_select(event)
            elif self.current_screen == Screen.SETTINGS:
                self._handle_settings(event)
            elif self.current_screen == Screen.GAME_CLOCK:
                self._handle_game_clock(event)
        
        return True
    
    def _handle_user_select(self, event):
        """Handle user selection events"""
        for i, btn in enumerate(self.user_buttons):
            if btn.handle_event(event):
                if i == 0:
                    self.selected_user = "Guest"
                else:
                    self.selected_user = self.recent_users[i - 1]
                self.current_screen = Screen.MODE_SELECT
        
        if self.new_user_btn.handle_event(event):
            # TODO: Show keyboard for new user name
            pass
    
    def _handle_mode_select(self, event):
        """Handle mode selection events"""
        for i, btn in enumerate(self.mode_buttons):
            if btn.handle_event(event):
                game_modes = ["VS_ENGINE", "OFFLINE_PVP", "ONLINE_LICHESS"]
                self.selected_mode = game_modes[i]
                self.current_screen = Screen.SETTINGS
        
        if self.back_btn.handle_event(event):
            self.current_screen = Screen.USER_SELECT
    
    def _handle_settings(self, event):
        """Handle settings events"""
        for i, btn in enumerate(self.clock_buttons):
            if btn.handle_event(event):
                self.clock_time = self.clock_times[i]
        
        for i, btn in enumerate(self.increment_buttons):
            if btn.handle_event(event):
                self.clock_increment = self.increments[i]
        
        if self.start_game_btn.handle_event(event):
            # Start the game!
            asyncio.create_task(self._start_game())
        
        if self.settings_back_btn.handle_event(event):
            self.current_screen = Screen.MODE_SELECT
    
    def _handle_game_clock(self, event):
        """Handle game clock events"""
        if self.chess_clock.paused:
            play_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 100, 200, 60, "▶ Resume", Colors.ACTIVE_CLOCK)
            if play_btn.handle_event(event):
                self.chess_clock.start()
        else:
            if self.pause_btn.handle_event(event):
                self.chess_clock.pause()
        
        if self.resign_btn.handle_event(event):
            # TODO: Confirm resignation
            asyncio.create_task(self.controller.resign_game())
            self.current_screen = Screen.USER_SELECT
        
        # Tap clocks to switch turns
        if event.type == pygame.MOUSEBUTTONUP:
            white_clock_rect = pygame.Rect(50, 50, SCREEN_WIDTH - 100, 200)
            black_clock_rect = pygame.Rect(50, 350, SCREEN_WIDTH - 100, 200)
            
            if white_clock_rect.collidepoint(event.pos) or black_clock_rect.collidepoint(event.pos):
                self.chess_clock.toggle_turn()
    
    async def _start_game(self):
        """Start a new game"""
        # Configure chess clock
        self.chess_clock.reset(self.clock_time)
        
        # Start game in controller
        # TODO: Get user_id from database
        await self.controller.start_new_game(
            game_mode = self.selected_mode,
            user_id=None  # Guest for now
        )
        
        # Switch to game clock screen
        self.current_screen = Screen.GAME_CLOCK
        self.chess_clock.start()
    
    def update(self):
        """Update UI state"""
        if self.current_screen == Screen.GAME_CLOCK:
            self.chess_clock.update()
    
    def draw(self):
        """Draw current screen"""
        self.screen.fill(Colors.BACKGROUND)
        
        if self.current_screen == Screen.USER_SELECT:
            self.draw_user_select()
        elif self.current_screen == Screen.MODE_SELECT:
            self.draw_mode_select()
        elif self.current_screen == Screen.SETTINGS:
            self.draw_settings()
        elif self.current_screen == Screen.GAME_CLOCK:
            self.draw_game_clock()
        
        pygame.display.flip()
    
    def run_frame(self):
        """Run one frame of UI"""
        if not self.handle_events():
            return False
        
        self.update()
        self.draw()
        self.clock.tick(FPS)
        
        return True
    
    def quit(self):
        """Cleanup"""
        pygame.quit()


# ==================== STANDALONE TEST MODE ====================

if __name__ == "__main__":
    """Run screen UI standalone for testing"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Mock controller for testing
    class MockController:
        async def start_new_game(self, game_mode, user_id):
            print(f"Mock: Starting game - mode={game_mode}, user_id={user_id}")
        
        async def resign_game(self):
            print("Mock: Game resigned")
    
    # Initialize pygame
    pygame.init()
    pygame.font.init()
    
    # Create screen UI
    controller = MockController()
    ui = ScreenUI(controller)
    
    print("Screen UI Test Mode")
    print("- Click through user selection, mode, settings")
    print("- Test the chess clock")
    print("- Press ESC or close window to exit")
    
    # Run main loop
    running = True
    while running:
        running = ui.run_frame()
    
    ui.quit()
    print("Test completed")
