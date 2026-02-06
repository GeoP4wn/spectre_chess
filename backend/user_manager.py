"""
User Manager for the Smart Chess Board.
Handles user authentication, profiles, and settings.
"""
import logging
from typing import Optional, Dict, Any
from database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class UserManager:
    """Manages user accounts and settings"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.current_user_id: Optional[int] = None
    
    async def login(self, username: str, password: Optional[str] = None) -> Optional[int]:
        """
        Log in a user.
        
        Args:
            username: Username
            password: Password (optional for now - auth not implemented)
            
        Returns:
            user_id if successful, None otherwise
        """
        user = await self.db.get_user_by_username(username)
        
        if user:
            self.current_user_id = user['user_id']
            logger.info(f"User logged in: {username} (ID: {user['user_id']})")
            
            # Update last login time
            # await self.db.connection.execute(
            #     "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
            #     (user['user_id'],)
            # )
            # await self.db.connection.commit()
            
            return user['user_id']
        
        logger.warning(f"Login failed for username: {username}")
        return None
    
    async def create_user(self, username: str, display_name: Optional[str] = None,
                         email: Optional[str] = None) -> Optional[int]:
        """
        Create a new user account.
        
        Returns:
            user_id if successful, None if username taken
        """
        try:
            user_id = await self.db.create_user(
                username=username,
                display_name=display_name,
                email=email
            )
            logger.info(f"Created new user: {username} (ID: {user_id})")
            return user_id
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return None
    
    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings"""
        settings = await self.db.get_user_settings(user_id)
        return settings or {}
    
    async def update_setting(self, user_id: int, setting_name: str, value: Any):
        """Update a single user setting"""
        await self.db.update_user_settings(user_id, {setting_name: value})
        logger.info(f"Updated setting for user {user_id}: {setting_name} = {value}")
    
    async def logout(self):
        """Log out the current user"""
        if self.current_user_id:
            logger.info(f"User {self.current_user_id} logged out")
            self.current_user_id = None
