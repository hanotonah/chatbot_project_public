"""
General chatbot.
Has access to all databases and provides general assistance.

Used in the scenario without handover.
"""

import logging
from time import time
from typing import List

from config.paths import CHROMA_DB_PATH_ALL
from config.runtime import CURRENT_EMBEDDINGS_MODEL
from .base_chatbot import BaseChatbot
from ...rag.context_builder import ContextBuilder
from ...rag.retriever import ChromaRetriever
from ..instructions.personas import GENERAL_PERSONA
from ..instructions.prompts import GENERAL_CHATBOT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeneralBot(BaseChatbot):
    """
    General virtual assistant for Creative Technology students.
    """
    
    def __init__(self, name: str, llm_model, tools: list, middleware: list):
        """
        Initialize the GeneralBot.

        Args:
            name: Name of the chatbot
            llm_model: LLM model for generating responses
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
        """
        logger.info("Initializing General Chatbot...")
        super().__init__(
            name=name,
            llm_model=llm_model,
            retriever=ChromaRetriever(str(CHROMA_DB_PATH_ALL), CURRENT_EMBEDDINGS_MODEL),
            context_builder=ContextBuilder(),
            system_prompt=GENERAL_CHATBOT_SYSTEM_PROMPT,
            tools=tools,
            middleware=middleware,
            thread_id=f"general_{int(time())}"
        )
    
    @staticmethod
    def initialize_general_bot(name: str, chat_model: str, tools: List, middleware: List):
        """
        Initialize and return a GeneralBot instance.

        Args:
            name: Name of the chatbot
            chat_model: The LLM model to use for chat
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
            
        Returns:
            Configured GeneralBot instance
        """
        general_bot = GeneralBot(
            name,
            chat_model,
            tools=tools,
            middleware=middleware,
        )

        logger.info("General chatbot initialized")
        
        return general_bot
    
    def get_persona(self) -> str:
        """
        Get the persona description for the general chatbot.
        
        Returns:
            str: The general persona description
        """
        return GENERAL_PERSONA
