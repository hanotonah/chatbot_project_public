"""
Conversation logging utilities.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be safe for use as a filename.
    
    Removes or replaces characters that are invalid in filenames on Windows/Unix:
    < > : " / \\ | ? *
    
    Args:
        filename: The string to sanitize
        
    Returns:
        Sanitized string safe for use as a filename
    """
    # Replace invalid characters with underscores
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove any leading/trailing whitespace or dots (problematic on Windows)
    sanitized = sanitized.strip('. ')
    
    # Ensure the filename is not empty after sanitization
    if not sanitized:
        sanitized = 'error_sanitizing_filename'
    
    return sanitized


class ConversationLogger:
    """
    Logs conversations to JSON files with detailed turn information.
    Tracks information on:
    - Timestamps
    - User queries (expanded)
    - Chatbot responses
    - Handover events
    - Retrieved chunks
    - Processing times
    """

    def __init__(self, log_dir: str = 'storage/conversation_logs'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)

        # In-memory storage: session_id -> list of turn data
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}

    def log_message(
        self,
        session_id: str,
        speaker: str,
        ai_response: str,
        user_query: Optional[str] = None,
        expanded_query: Optional[str] = None,
        timestamp: datetime = None,
        handover_info: Optional[Dict[str, Any]] = None,
        chunks: Optional[List[Dict]] = None,
        processing_time: Optional[float] = None,
        summarization_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a single message turn in the conversation.

        Args:
            session_id: Session identifier
            speaker: Name of the speaker (bot name for bot messages)
            ai_response: The actual response/message content (after summarization if applicable) from the bot
            user_query: Original user query
            expanded_query: Query after abbreviation expansion (only logged if different from user_query)
            timestamp: When this message occurred
            handover_info: Dict with handover details if handover occurred
            chunks: Retrieved RAG chunks
            processing_time: Time taken to process query
            summarization_info: Dict with original_response and reason if summarization occurred
        """
        # Initialize conversation list if new session
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        # Build turn data structure
        turn_data = {
            'turn_number': len(self.conversations[session_id]) + 1,
            'timestamp': timestamp.isoformat(),
            'speaker': speaker,
        }

        # Add user query - log expanded_query only if different from user_query
        if user_query is not None:
            turn_data['user_query'] = user_query
            # Only log expanded_query if it's different from user_query
            if expanded_query and expanded_query != user_query:
                turn_data['expanded_query'] = expanded_query
            else:
                turn_data['expanded_query'] = None
        else:
            # For greeting messages where there's no user input
            turn_data['user_query'] = None
            turn_data['expanded_query'] = None

        # Add bot response
        turn_data['ai_response'] = ai_response

        # Add summarization info if present
        if summarization_info:
            turn_data['summarization'] = {
                'original_response': summarization_info.get('original_response'),
                'reason': summarization_info.get('reason')
            }

        # Add chunks if present
        if chunks:
            turn_data['chunks_retrieved'] = [
                {
                    'file': ch.get('file', 'unknown'),
                    'chunk_num': ch.get('chunk_num', '?'),
                    'score': ch.get('score', 0.0)
                }
                for ch in chunks
            ]

        # Add processing time if present
        if processing_time:
            turn_data['processing_time'] = f"{round(processing_time, 2)} seconds"

        # Add handover info if present
        if handover_info:
            turn_data['handover'] = handover_info

        self.conversations[session_id].append(turn_data)

        logger.debug(f"Logged turn {turn_data['turn_number']} for session {session_id}")

    def save_conversation(
        self,
        session_id: str,
        username: str,
        start_time: datetime,
        end_time: datetime,
        models_used: Optional[Dict[str, str]] = None,
        condition_key: Optional[str] = None
    ) -> Path:
        """
        Save complete conversation to JSON file.

        Args:
            session_id: Session identifier
            username: Participant code
            start_time: When conversation started
            end_time: When conversation ended
            models_used: Mapping of model roles to identifiers
            condition_key: The condition assigned to this participant

        Returns:
            Path to saved log file
        """
        if session_id not in self.conversations:
            logger.warning(f"No conversation data found for session {session_id}")
            turns = []
        else:
            turns = self.conversations[session_id]

        # Create log data structure
        log_data = {
            'conversation_id': session_id,
            'participant_code': username,
            'condition': condition_key,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': (end_time - start_time).total_seconds(),
            'total_turns': len(turns),
            'models_used': models_used or {},
            'turns': turns
        }

        # Retrieve handover statistics
        handover = [t for t in turns if t.get('handover', {}).get('triggered')]

        if handover:
            log_data['handover_keywords'] = [
                h['handover']['keyword'] for h in handover
            ]

        # Generate filename with participant code and timestamp
        # Sanitize username to prevent invalid filename characters
        sanitized_username = sanitize_filename(username)
        filename = f"{sanitized_username}_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.log_dir / filename

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved conversation log to {filepath}")

        # Clean up in-memory data
        if session_id in self.conversations:
            del self.conversations[session_id]

        return filepath

    def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get current conversation turns for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of turn dictionaries
        """
        return self.conversations.get(session_id, [])
