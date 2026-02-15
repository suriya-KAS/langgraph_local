"""
MongoDB service for storing user sessions.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import secrets
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

from motor.motor_asyncio import AsyncIOMotorDatabase
from database.async_connection import get_async_database


class UserSessionsService:
    """Service for MongoDB user sessions operations."""
    
    def __init__(self):
        self._db: Optional[AsyncIOMotorDatabase] = None
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = await get_async_database()
        return self._db
    
    def generate_session_id(self) -> str:
        """Generate a session ID following the schema pattern: session_[alphanumeric]"""
        return f"session_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:16]}"
    
    def generate_sess_id(self) -> str:
        """Generate a sess ID following the schema pattern: sess_[alphanumeric]"""
        return f"sess_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:16]}"
    
    async def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        activity: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Create a new user session.
        
        Args:
            user_id: User identifier (must match pattern: user_[alphanumeric_underscore])
            session_id: Session identifier (sess_*). If not provided, will be generated.
            activity: Activity object (conversationIds, messageCount, agentsLaunched, etc.)
            timestamp: Creation timestamp (defaults to now)
            
        Returns:
            Session _id if successful, None otherwise
        """
        try:
            db = await self._get_db()
            _id = self.generate_session_id()
            sess_id = session_id or self.generate_sess_id()
            now = timestamp or datetime.now(timezone.utc)
            
            session_doc = {
                "_id": _id,
                "userId": user_id,
                "sessionId": sess_id,
                "timeRange": {
                    "startedAt": now
                },
                "createdAt": now
            }
            
            # Add optional activity field
            if activity:
                session_doc["activity"] = activity
            else:
                # Initialize default activity
                session_doc["activity"] = {
                    "conversationIds": [],
                    "messageCount": 0,
                    "agentsLaunched": [],
                    "intents": {},
                    "totalTokensUsed": 0
                }
            
            # Insert into user_sessions collection
            result = await db.user_sessions.insert_one(session_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Created user session: {_id} (user: {user_id}, sess: {sess_id})")
                return _id
            else:
                logger.error(f"Failed to create user session: {_id}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating user session: {e}", exc_info=True)
            return None
    
    async def update_session(
        self,
        session_id: str,
        activity: Optional[Dict[str, Any]] = None,
        end_session: bool = False,
        timezone: Optional[str] = None
    ) -> bool:
        """
        Update an existing user session.
        
        Args:
            session_id: Session _id or sessionId
            activity: Activity object to update (will be merged with existing)
            end_session: If True, end the session and calculate duration
            timezone: User timezone to add to activity
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await self._get_db()
            # Try to find by _id first, then by sessionId
            query = {"_id": session_id} if session_id.startswith("session_") else {"sessionId": session_id}
            
            now = datetime.now(timezone.utc)
            
            # Build update operations
            update_operations = {}
            set_updates = {}
            add_to_set_updates = {}
            inc_updates = {}
            
            if activity:
                # Handle different activity field types
                for key, value in activity.items():
                    if key == "conversationIds" and isinstance(value, list):
                        # Add to set (no duplicates)
                        add_to_set_updates["activity.conversationIds"] = {"$each": value}
                    elif key == "agentsLaunched" and isinstance(value, list):
                        # Add to set (no duplicates)
                        add_to_set_updates["activity.agentsLaunched"] = {"$each": value}
                    elif key == "intents" and isinstance(value, dict):
                        # Merge intents object - set each intent key
                        for intent_key, intent_value in value.items():
                            set_updates[f"activity.intents.{intent_key}"] = intent_value
                    elif key in ["messageCount", "totalTokensUsed"]:
                        # Increment numeric fields
                        if isinstance(value, (int, float)):
                            inc_updates[f"activity.{key}"] = value
                        else:
                            set_updates[f"activity.{key}"] = value
                    else:
                        # Set other fields
                        set_updates[f"activity.{key}"] = value
            
            if timezone:
                set_updates["activity.timezone"] = timezone
            
            # Handle end_session updates
            if end_session:
                # Get the session to calculate duration
                session = await db.user_sessions.find_one(query)
                if session and "timeRange" in session and "startedAt" in session["timeRange"]:
                    started_at = session["timeRange"]["startedAt"]
                    duration = int((now - started_at).total_seconds())
                    set_updates["timeRange.endedAt"] = now
                    set_updates["timeRange.durationSeconds"] = duration
            
            # Build final update operations
            if set_updates:
                update_operations["$set"] = set_updates
            if add_to_set_updates:
                update_operations["$addToSet"] = add_to_set_updates
            if inc_updates:
                update_operations["$inc"] = inc_updates
            
            if not update_operations:
                logger.warning(f"No fields to update for session: {session_id}")
                return False
            
            result = await db.user_sessions.update_one(query, update_operations)
            
            if result.modified_count > 0:
                logger.info(f"✓ Updated user session: {session_id}")
                return True
            else:
                logger.warning(f"No session updated: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error updating user session: {e}", exc_info=True)
            return False
    
    async def get_session(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session _id or sessionId
            
        Returns:
            Session document if found, None otherwise
        """
        try:
            db = await self._get_db()
            # Try to find by _id first, then by sessionId
            query = {"_id": session_id} if session_id.startswith("session_") else {"sessionId": session_id}
            
            session = await db.user_sessions.find_one(query)
            if session:
                logger.debug(f"Retrieved session: {session_id}")
            else:
                logger.debug(f"Session not found: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Unexpected error retrieving session: {e}", exc_info=True)
            return None
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get sessions for a user, ordered by start time.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            skip: Number of sessions to skip
            active_only: If True, only return active sessions (no endedAt)
            
        Returns:
            List of session documents
        """
        try:
            db = await self._get_db()
            query = {"userId": user_id}
            if active_only:
                query["timeRange.endedAt"] = None
            
            cursor = (
                db.user_sessions.find(query)
                .sort("timeRange.startedAt", -1)
                .skip(skip)
                .limit(limit)
            )
            sessions = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(sessions)} sessions for user: {user_id}")
            return sessions
        except Exception as e:
            logger.error(f"Unexpected error retrieving user sessions: {e}", exc_info=True)
            return []
    
    async def end_session(
        self,
        session_id: str
    ) -> bool:
        """
        End a session by setting endedAt and calculating duration.
        
        Args:
            session_id: Session _id or sessionId
            
        Returns:
            True if successful, False otherwise
        """
        return await self.update_session(session_id, end_session=True)


# Global instance (singleton pattern)
_user_sessions_service: Optional[UserSessionsService] = None


def get_user_sessions_service() -> UserSessionsService:
    """Get or create User Sessions service instance."""
    global _user_sessions_service
    if _user_sessions_service is None:
        _user_sessions_service = UserSessionsService()
    return _user_sessions_service


if __name__ == "__main__":
    """Test the user sessions service and create collection."""
    print("=" * 60)
    print("Testing User Sessions Service")
    print("=" * 60)
    
    try:
        # Initialize service (this will connect to MongoDB)
        service = get_user_sessions_service()
        print("✓ Connected to MongoDB")
        
        # Test creating a session (this will create the collection)
        test_user_id = "user_test_123"
        session_id = service.create_session(
            user_id=test_user_id
        )
        
        if session_id:
            print(f"✓ Created test session: {session_id}")
            print(f"✓ Collection 'user_sessions' is now created")
            
            # Clean up test session
            result = service.db.user_sessions.delete_one({"_id": session_id})
            if result.deleted_count > 0:
                print(f"✓ Cleaned up test session")
        else:
            print("✗ Failed to create test session")
        
        # Close connection
        service.close()
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)

