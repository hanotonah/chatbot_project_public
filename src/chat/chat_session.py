"""
Chat session management.
This module defines the ChatSessionManager class, which is responsible for 
creating, retrieving, updating, and ending chat sessions for users. It keeps
track of session state, including the current chatbot, turn counts, and messages.
The session manager also handles saving conversation logs when sessions end.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    Manages chat sessions for users.
    Keep track of session state, current bot, turn counts, and messages.
    """

    def __init__(self):
        # Sessions are kept in-memory only; restarting the server clears them
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # Mapping of participant_code to session_id for session persistence
        self.participant_sessions: Dict[str, str] = {}

    def get_session_by_participant(self, participant_code: str) -> Optional[Dict[str, Any]]:
        """
        Get session data by participant code.

        Args:
            participant_code: The participant's code

        Returns:
            Session data if found, None otherwise
        """
        session_id = self.participant_sessions.get(participant_code)
        if session_id:
            return self.sessions.get(session_id)
        return None

    def get_session_id_by_participant(self, participant_code: str) -> Optional[str]:
        """
        Get session ID for a participant if they have an active session.

        Args:
            participant_code: The participant's code

        Returns:
            Session ID if found, None otherwise
        """
        return self.participant_sessions.get(participant_code)

    def create_session(
        self,
        session_id: str,
        username: str,
        chatbot_map: Dict,
        current_bot: Any,
        current_bot_type: Any,
        router: Any,
        models_used: Optional[Dict[str, str]] = None,
        condition_key: Optional[str] = None
    ) -> None:
        """
        Create a new chat session for a user.

        Args:
            session_id: Unique session identifier
            username: Username of the authenticated user
            chatbot_map: Dictionary mapping bot types to bot instances
            current_bot: Initially active chatbot
            current_bot_type: Type of initially active chatbot
            router: Query router instance (None if routing is disabled)
            models_used: Mapping of model roles to identifiers
            condition_key: The study condition key assigned to this session
        """
        self.sessions[session_id] = {
            'session_id': session_id,
            'username': username,
            'chatbot_map': chatbot_map,
            'current_bot': current_bot,
            'current_bot_type': current_bot_type,
            'router': router,
            'turn_count': 0,
            'start_time': datetime.now(),
            'models_used': models_used or {},
            'condition_key': condition_key,  # Store condition info
            'messages': []  # Store all messages for this session
        }

        # Map participant to this session for persistence
        self.participant_sessions[username] = session_id

        logger.info(f"Created session {session_id} for user {username} with condition: {condition_key}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session ID."""
        return self.sessions.get(session_id)

    def has_session(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self.sessions

    def update_session(
        self,
        session_id: str,
        current_bot: Any = None,
        current_bot_type: Any = None,
        turn_count: int = None
    ) -> None:
        """
        Update session state after processing a message.

        Args:
            session_id: Session to update
            current_bot: New current bot (if changed)
            current_bot_type: New current bot type (if changed)
            turn_count: New turn count
        """
        if session_id not in self.sessions:
            logger.error(f"Attempted to update non-existent session: {session_id}")
            return

        session = self.sessions[session_id]

        if current_bot is not None:
            session['current_bot'] = current_bot
        if current_bot_type is not None:
            session['current_bot_type'] = current_bot_type
        if turn_count is not None:
            session['turn_count'] = turn_count

    def end_session(
        self,
        session_id: str,
        conversation_logger: ConversationLogger
    ) -> Optional[Path]:
        """
        End a session and save conversation log.

        Args:
            session_id: Session to end
            conversation_logger: Logger instance to save conversation

        Returns:
            Path to saved log file, or None if session not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Attempted to end non-existent session: {session_id}")
            return None

        session = self.sessions[session_id]
        username = session['username']

        # Save conversation log
        log_file = conversation_logger.save_conversation(
            session_id=session_id,
            username=username,
            start_time=session['start_time'],
            end_time=datetime.now(),
            models_used=session.get('models_used'),
            condition_key=session.get('condition_key')
        )

        # Remove session from memory and participant mapping
        del self.sessions[session_id]
        if username in self.participant_sessions:
            del self.participant_sessions[username]

        logger.info(f"Ended session {session_id}, log saved to {log_file}")
        return log_file
