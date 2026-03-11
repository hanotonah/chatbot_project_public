"""
Study adviser chatbot module specializing in general programme guidance.
Has access to database containing information about the UT, CreaTe, and study adviser resources.

Used in the scenario with handover from Teacher chatbot when a predetermined keyword is detected in the user query.
"""

import logging
from time import time
from typing import List

from config.paths import CHROMA_DB_PATH_STUDY_ADVISER
from config.runtime import CURRENT_EMBEDDINGS_MODEL
from .base_chatbot import BaseChatbot
from ...rag.context_builder import ContextBuilder
from ...rag.retriever import ChromaRetriever
from ..instructions.personas import STUDY_ADVISER_PERSONA
from ..instructions.prompts import STUDY_ADVISER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class StudyAdviser(BaseChatbot):
    """
    Study adviser specializing in general programme guidance.
    """
    
    def __init__(self, name: str, llm_model, tools: list, middleware: list):
        """
        Initialize the Study Adviser chatbot.
        
        Args:
            name: Name of the chatbot
            llm_model: LLM model for generating responses
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
        """
        logger.info("Initializing Study Adviser Chatbot...")
        super().__init__(
            name=name,
            llm_model=llm_model,
            retriever=ChromaRetriever(str(CHROMA_DB_PATH_STUDY_ADVISER), CURRENT_EMBEDDINGS_MODEL),
            context_builder=ContextBuilder(),
            system_prompt=STUDY_ADVISER_SYSTEM_PROMPT,
            tools=tools,
            middleware=middleware,
            thread_id=f"adviser_{int(time())}"
        )
    
    @staticmethod
    def initialize_adviser(name: str, chat_model: str, tools: List, middleware: List):
        """
        Initialize and configure a Study Adviser chatbot instance.
        
        Args:
            name: Name of the chatbot
            chat_model: The LLM model to use for chat
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
            
        Returns:
            Configured StudyAdviser instance
        """
        study_adviser = StudyAdviser(
            name,
            chat_model,
            tools=tools,
            middleware=middleware,
        )

        logger.info("Study Adviser chatbot initialized")
        
        return study_adviser
    
    def get_persona(self) -> str:
        """
        Get the persona description for the study adviser chatbot.
        
        Returns:
            str: The study adviser persona description
        """
        return STUDY_ADVISER_PERSONA
