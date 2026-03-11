"""
Base chatbot module defining the BaseChatbot class.
Provides shared functionality for chatbot implementations using a common agent pattern.
"""

import logging
import re

from abc import ABC
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from ..instructions.prompts import HANDOVER_MESSAGE


logger = logging.getLogger(__name__)


class BaseChatbot(ABC):
    """
    Base class for chatbot implementations sharing a common agent pattern.
    """

    def __init__(
        self,
        name: str,
        llm_model: Any | None = None,
        retriever: Any | None = None,
        context_builder: Any | None = None,
        system_prompt: str | None = None,
        tools: Optional[List[Any]] = None,
        checkpointer: InMemorySaver | None = None,
        middleware: Optional[List[Any]] = None,
        thread_id: str = "default_thread",
    ) -> None:
        """
        Initialize shared chatbot components.

        Args:
            name: Name of the chatbot
            llm_model: LLM model for generating responses
            retriever: Retriever for querying the knowledge base
            context_builder: Context builder for formatting retrieved chunks
            system_prompt: System prompt defining chatbot behavior
            tools: List of tools available to the agent
            checkpointer: Checkpointer for conversation state
            middleware: List of middleware components for the agent
            thread_id: Identifier for the conversation thread
        """
        self.name = name

        # Core dependencies
        self.llm = llm_model
        self.retriever = retriever
        self.context_builder = context_builder
        self.system_prompt = system_prompt or ""

        # Conversation state
        self.checkpointer = checkpointer or InMemorySaver()
        self.thread_id = thread_id

        # Agent instance (created if LLM is provided)
        self.agent = None
        if self.llm is not None:
            self.agent = create_agent(
                self.llm,
                tools=tools or [],
                system_prompt=self.system_prompt,
                checkpointer=self.checkpointer,
                middleware=middleware or [],
            )

        logger.info(f"{self.name} initialized with thread_id: {self.thread_id}")


    # ---- Conversation helpers ----

    def get_persona(self) -> str | None:
        """
        Get the persona description for this chatbot.
        
        Returns:
            str: The persona description, or None if not defined
        """
        return None

    def get_history(self) -> List[Dict[str, str]]:
        """
        Retrieve the complete conversation history as a list of turns.

        Returns:
            List of dicts with 'context', 'human', and 'ai' keys
        """
        if self.checkpointer is None:
            return []
        
        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            complete_history = self.checkpointer.get(config=config)
        except Exception as e:
            logger.error(f"Error retrieving history for {self.name}: {e}", exc_info=True)
            return []

        if not complete_history or "channel_values" not in complete_history:
            return []
        
        message_history = complete_history["channel_values"].get("messages", [])
        
        # Group messages into turns
        turns = []
        current_turn = {"context": "", "human": "", "ai": ""}
        
        for message in message_history:
            msg_type = type(message).__name__
            content = getattr(message, 'content', '')
            
            if msg_type == "SystemMessage":
                # If we have a pending turn with content, save it first
                if current_turn["human"] or current_turn["ai"]:
                    turns.append(current_turn.copy())
                
                # Start new turn and extract context from between <Context> tags
                current_turn = {"context": "", "human": "", "ai": ""}
                match = re.search(r'<Context>(.*?)</Context>', content, re.DOTALL)
                if match:
                    current_turn["context"] = match.group(1).strip()
                    
            elif msg_type == "HumanMessage":
                current_turn["human"] = content
                
            elif msg_type == "AIMessage":
                current_turn["ai"] = content
        
        # Add the last turn if it has content
        if current_turn["human"] or current_turn["ai"]:
            turns.append(current_turn)
        
        return turns


    # ---- Chunk retrieval ----

    def retrieve_relevant_chunks(self, query: str, num_chunks: int, score_threshold: float) -> List[Dict]:
        """
        Retrieve relevant chunks from the retriever based on the query.

        Args:
            query: User's input query
            num_chunks: Number of chunks to retrieve
            score_threshold: Maximum relevance score threshold for filtering chunks

        Returns:
            List of retrieved chunks as dicts with content and metadata
        """

        if self.retriever is None:
            logger.warning(f"{self.name}: No retriever available")
            return []

        try:
            docs_with_scores = self.retriever.retrieve(
                query, num_chunks=num_chunks, score_threshold=score_threshold
            )

            chunks: List[Dict] = []
            for doc, score in docs_with_scores:
                chunk_data = {
                    "content": doc.page_content,
                    "score": score,
                    "file": doc.metadata.get("file", "unknown"),
                    "chunk_num": doc.metadata.get("chunk_num", "?"),
                }
                chunks.append(chunk_data)
                logger.debug(f"{self.name}: Retrieved chunk from {chunk_data['file']} (score: {score:.3f})")

            return chunks
        except Exception as e:
            logger.error(f"{self.name}: Error in retrieve_relevant_chunks: {e}", exc_info=True)
            return []


    # --- Message building ---

    def build_message(self, query: str, context_str: str) -> List[Dict[str, str]]:
        """
        Construct message for agent invocation based on the query and retrieved context.

        Args:
            query: User's input query
            context_str: Context string to provide to the agent

        Returns:
            List of message dicts for the agent
        """
        
        messages = []
        
        if context_str:
            # Add system message with retrieved context
            messages.append({
                "role": "system",
                "content": f"""For this specific query, you have been provided relevant reference material from the knowledge base:

                    <Knowledge Base Material>
                    {context_str}
                    </Knowledge Base Material>

                    Use this material to inform your answer. If the material doesn't address the question, rely on your general knowledge while being honest about limitations.

                    RESPONSE CONSTRAINTS
                    - Length: 1-5 sentences (concise but complete)

                    """
                })
        else:
            # No context available - provide a system message to guide the agent anyway
            messages.append({
                "role": "system",
                "content": """For this specific query, no relevant knowledge base materials were found. 
                Please provide your best answer based on your general knowledge while being honest about any limitations.
                    
                    RESPONSE CONSTRAINTS
                    - Length: 1-5 sentences (concise but complete)
                    """
                })
        
        # Always append the user query
        messages.append({"role": "user", "content": query})
            
        return messages
    
    def build_context_str(self, chunks: List[Dict] | None) -> str:
        """
        Build a context string from retrieved chunks using the context builder.

        Args:
            chunks: List of retrieved chunks as dicts

        Returns:
            Formatted context string for LLM prompt
        """
        if not chunks or self.context_builder is None:
            return ""
        
        try:
            # Extract content and metadata separately
            chunk_contents = [c["content"] for c in chunks]
            chunk_metadata = [{"file": c.get("file", "unknown"), "chunk_num": c.get("chunk_num", "?"), "score": c.get("score", "N/A")} for c in chunks]
            
            # Build context with metadata
            built_context = self.context_builder.build_context(chunk_contents, metadata=chunk_metadata)

            return built_context
        except Exception as e:
            logger.error(f"{self.name}: Error building context string: {e}", exc_info=True)
            # Fallback to simple join
            return "\n\n---\n\n".join([c["content"] for c in chunks])


    # ---- Agent invocation ----

    def invoke_agent(self, query: str, context_str: str = "") -> Any:
        """
        Invoke the agent with the given query and context.

        Args:
            query: User's input query
            context_str: Context string to provide to the agent

        Returns:
            Agent result
        """
        if self.agent is None:
            logger.error(f"{self.name}: Agent not initialized when invoke_agent was called")
            raise RuntimeError(
                "Agent not initialized. Provide an LLM or call create_or_update_agent()."
            )

        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}
        message = {"messages": self.build_message(query, context_str)}

        logger.debug(f"{self.name}: Invoking agent with query: {query[:50]}...")
        
        try:
            result = self.agent.invoke(message, config=config)
            logger.debug(f"{self.name}: Agent invocation successful")
            return result
        except Exception as e:
            logger.error(f"{self.name}: Error during agent invocation: {e}", exc_info=True)
            raise
    
    def process_query(self, query: str, num_chunks: int = 3, score_threshold: float = 0.5, skip_retrieval: bool = False, handover_context: str = None) -> Tuple:
        """
        Process a user query by retrieving relevant context and invoking the agent.

        Args:
            query: User's input query
            num_chunks: Number of chunks to retrieve for context
            score_threshold: Minimum relevance score for retrieved chunks
            skip_retrieval: If True, skip retrieval and use no context
            handover_context: If provided, use this conversation history for handover processing

        Returns:
            Tuple containing:
            - Agent result
            - List of retrieved chunks
            - Context level indicator ("no_context", "low_context", "ok", "retrieval_error", "retrieval_skipped", "error")
        """
        logger.info(f"{self.name}: Processing query: {query[:100]}...")
        
        context_level = "no_context"
        
        if skip_retrieval:
            chunks = []
            context_level = "retrieval_skipped"
            context_str = ""
            logger.debug(f"{self.name}: Skipping retrieval as requested")
        else:
            try:
                chunks = self.retrieve_relevant_chunks(query, num_chunks, score_threshold)
                logger.info(f"{self.name}: Retrieved {len(chunks)} chunks")

                if 0 < len(chunks) < num_chunks:
                    context_level = "low_context"
                    logger.warning(f"{self.name}: Low context - only {len(chunks)}/{num_chunks} chunks retrieved")
                elif len(chunks) >= num_chunks:
                    context_level = "ok"

                context_str = self.build_context_str(chunks)
            except Exception as e:
                logger.error(f"{self.name}: Error during retrieval: {e}", exc_info=True)
                chunks = []
                context_str = ""
                context_level = "retrieval_error"

        # Invoke the agent with the query and relevant context
        try:
            if handover_context: # --- Handover processing ---
                result = self.handover_invocation(query, context_str, handover_context)
            else: # --- Normal processing --- 
                result = self.invoke_agent(query, context_str)
            
            logger.info(f"{self.name}: Query processed successfully")
            return result, chunks, context_level
        
        except Exception as e:
            logger.error(f"{self.name}: Error in agent execution: {e}", exc_info=True)
            fallback = AIMessage(content="I encountered an error processing your query. Please try again.")
            return {"messages": [fallback]}, [], "error"


    # ---- Handover helpers ----

    def prepare_handover_context(self) -> str:
        """
        Prepare conversation history for handover to another chatbot.

        Returns:
            Formatted conversation history string
        """
        history = self.get_history()
        
        if not history:
            logger.info(f"{self.name}: No history available for handover")
            return "No prior conversation history."
        
        logger.info(f"{self.name}: Prepared handover context")
        return str(history)
    
    def handover_invocation(self, query: str, context_str: str, handover_context: str) -> Any:
        """
        Invoke the agent during a handover with separate prompt and additional conversation history.

        Args:
            query: User's input query
            context_str: Context string to provide to the agent
            handover_context: Conversation history to include for handover

        Returns:
            Agent result
        """
        if self.agent is None:
            logger.error(f"{self.name}: Agent not initialized for handover")
            raise RuntimeError("Agent not initialized.")

        logger.info(f"{self.name}: Processing handover invocation")

        handover_prompt = f"""{HANDOVER_MESSAGE}

            Conversation history:
            {handover_context}

            Retrieved context for the current query:
            {context_str}
            """

        handover_message = {
                    "messages": [
                        {"role": "system", "content": handover_prompt},
                        {"role": "user", "content": query},
                    ]
                }
        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            result = self.agent.invoke(handover_message, config=config)
            logger.info(f"{self.name}: Handover invocation successful")
            return result
        except Exception as e:
            logger.error(f"{self.name}: Error during handover invocation: {e}", exc_info=True)
            raise
