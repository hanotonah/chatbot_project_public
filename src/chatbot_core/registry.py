"""
Chatbot registry for managing available chatbot configurations.

To add and use a new chatbot type:
1. Create a new Chatbot class in `src/chatbot_core/chatbots/`
2. Add an entry to this registry with the chatbot's metadata
3. Add the new ChatbotType to your preferred condition in `config/conditions.py`
"""

import logging
from config.conditions import ChatbotType
from config.runtime import CURRENT_CHAT_MODEL, build_default_middleware
from src.chatbot_core.chatbots import StudyAdviser, Teacher, GeneralBot

logger = logging.getLogger(__name__)


class ChatbotRegistry:
    """
    Registry that manages all available chatbots and their properties.
    
    This registry stores information about each chatbot including:
    - Its name (how it introduces itself)
    - Its role (its position in the system)
    - Its display name (how it appears in the web interface)
    - Its greeting message (what it says when the conversation starts)
    - How to initialize it (what function creates it)
    
    The chatbots that are used within conversations depend on their assigned
    study condition.
    """
    
    def __init__(self):
        """Set up the registry with all available chatbots and their information."""
        self._registry = {
            ChatbotType.TEACHER: {
                "class": Teacher,
                "initializer": Teacher.initialize_teacher,
                "name": "Robin",
                "role": "Designing for Experience teacher",
                "display_name": "{name} (D4E Teacher)",
                "greeting": "Hello! I'm {name}, the virtual teacher of the Designing for Experience course. I understand you're working on assignment 4. Could you briefly describe the installation you're planning to evaluate?"
            },
            ChatbotType.STUDY_ADVISER: {
                "class": StudyAdviser,
                "initializer": StudyAdviser.initialize_adviser,
                "name": "Jaimie",
                "role": "study adviser",
                "display_name": "{name} (Study Adviser)",
                "greeting": "Hello! I'm {name}, the virtual study adviser for Creative Technology. How can I assist you today?"
            },
            ChatbotType.GENERAL: {
                "class": GeneralBot,
                "initializer": GeneralBot.initialize_general_bot,
                "name": "Robin",
                "role": "virtual assistant",
                "display_name": "{name}",
                "greeting": "Hello! I'm {name}, the virtual assistant for Creative Technology. I understand you're working on assignment 4 of D4E. Could you briefly describe the installation you're planning to evaluate?"
            }
        }
    
    def get_greeting(self, bot_type: ChatbotType) -> str:
        """
        Get the greeting message for a specific chatbot type.
        
        Args:
            bot_type: Which chatbot you want the greeting for
        
        Returns:
            The greeting message with the chatbot's name filled in
        """
        config = self._registry[bot_type]
        name = config["name"]
        greeting_template = config["greeting"]
        return greeting_template.format(name=name)
    
    def initialize_bot(self, bot_type: ChatbotType, chat_model, tools: list, middleware: list):
        """
        Create and set up a chatbot of the specified type.
        
        Args:
            bot_type: Which type of chatbot to create (TEACHER, STUDY_ADVISER, or GENERAL)
            chat_model: The AI language model to use for the chatbot
            tools: List of tools the chatbot can use (empty for now)
            middleware: Processing steps the chatbot uses (set up by the system)
            
        Returns:
            A fully initialized and ready-to-use chatbot instance
        """
        config = self._registry[bot_type]
        initializer = config["initializer"]
        return initializer(config["name"], chat_model, tools, middleware)
    
    def initialize_bot_by_type(self, bot_type: ChatbotType):
        """
        Initialize and return a chatbot of the specified type with standard settings.
        
        Args:
            bot_type: Which type of chatbot to initialize
            
        Returns:
            A ready-to-use chatbot instance
        """
        logger.info(f"Initializing {bot_type.value} bot")
        return self.initialize_bot(bot_type, CURRENT_CHAT_MODEL, tools=[], middleware=build_default_middleware())
    
    def get_bot_name(self, bot_type: ChatbotType) -> str:
        """
        Get the name of a chatbot (used in greetings).
        
        Args:
            bot_type: Which chatbot to get the name for
            
        Returns:
            The chatbot's name
        """
        return self._registry[bot_type]["name"]
    
    def get_bot_display_name(self, bot_type: ChatbotType) -> str:
        """
        Get the display name for a chatbot (shown in interface headers).
        
        Args:
            bot_type: Which chatbot to get the display name for
            
        Returns:
            A formatted display name with the chatbot's name and role
        """
        config = self._registry[bot_type]
        name = config["name"]
        display_template = config["display_name"]
        return display_template.format(name=name)
    
    def get_bot_role(self, bot_type: ChatbotType) -> str:
        """
        Get the role description for a chatbot (used in handover messages).
        
        Args:
            bot_type: Which chatbot to get the role for
            
        Returns:
            A description of what the chatbot does
        """
        return self._registry[bot_type]["role"]
