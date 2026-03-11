"""
Flask application configuration.
Contains settings for sessions, logging, and application behavior.
"""

import os
import secrets
from pathlib import Path
from datetime import timedelta


class Config:
    """
    Base configuration class for Flask application.
    Contains default settings for sessions, logging, and application behavior.
    """
    
    # Secret key for session encryption
    # Optionally set via SECRET_KEY environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Session configuration
    SESSION_TYPE = 'filesystem'  # Store sessions on disk
    SESSION_FILE_DIR = 'storage/flask_session'  # Directory for session files
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)  # Auto-logout after 1 hour
    SESSION_COOKIE_NAME = 'chat_session_d4e'
    SESSION_COOKIE_HTTPONLY = True  # Security: prevent JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'  # Security: CSRF protection
    
    # Logging configuration
    LOG_DIR = Path('storage/conversation_logs')
    LOG_DIR.mkdir(exist_ok=True, parents=True)
    
    # Application settings
    MAX_CONTENT_LENGTH = 16 * 1024  # Max request size: 16KB (enough for text chat)
    JSON_SORT_KEYS = False  # Preserve JSON key order in responses
