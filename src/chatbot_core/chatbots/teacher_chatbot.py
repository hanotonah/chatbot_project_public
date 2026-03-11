"""
Teacher chatbot module specializing in course-specific guidance.
Has access to database containing information about the D4E course and the teacher manual.

Used in the scenario with handover to Study Adviser chatbot when a predetermined keyword is detected in the user query.
"""

import logging
from time import time
from typing import List

from config.paths import CHROMA_DB_PATH_TEACHER
from config.runtime import CURRENT_EMBEDDINGS_MODEL
from .base_chatbot import BaseChatbot
from ...rag.context_builder import ContextBuilder
from ...rag.retriever import ChromaRetriever
from ..instructions.personas import TEACHER_PERSONA
from ..instructions.prompts import TEACHER_CHATBOT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class Teacher(BaseChatbot):
    """
    Teacher specializing in course-specific guidance.
    """
    
    def __init__(self, name: str, llm_model, tools: list, middleware: list):
        """
        Initialize the Teacher chatbot.

        Args:
            name: Name of the chatbot
            llm_model: LLM model for generating responses
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
        """
        logger.info("Initializing Teacher Chatbot...")
        super().__init__(
            name=name,
            llm_model=llm_model,
            retriever=ChromaRetriever(str(CHROMA_DB_PATH_TEACHER), CURRENT_EMBEDDINGS_MODEL),
            context_builder=ContextBuilder(),
            system_prompt=TEACHER_CHATBOT_SYSTEM_PROMPT,
            tools=tools,
            middleware=middleware,
            thread_id=f"teacher_{int(time())}"
        )

    @staticmethod  
    def initialize_teacher(name: str, chat_model: str, tools: List, middleware: List):
        """
        Initialize and configure a Teacher chatbot instance.
        
        Args:
            name: Name of the chatbot
            chat_model: The LLM model to use for chat
            tools: List of tools available to the agent
            middleware: List of middleware components for the agent
            
        Returns:
            Configured Teacher instance
        """
        teacher = Teacher(
            name,
            chat_model,
            tools=tools,
            middleware=middleware,
        )

        logger.info("Teacher chatbot initialized")
        
        return teacher
    
    def get_persona(self) -> str:
        """
        Get the persona description for the teacher chatbot.
        
        Returns:
            str: The teacher persona description
        """
        return TEACHER_PERSONA
