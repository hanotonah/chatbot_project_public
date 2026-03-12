"""
Command-line chatbot system for terminal-based conversations. It initializes the chatbots,
handles user input, and manages the conversation flow without the Flask web interface.

This is the terminal-based version of the chatbot system. Users type messages and see
responses in the command line, with support for switching between chatbots and admin
diagnostics mode.

The file is organized into these main sections:
1. Setup and configuration - loading modules and setting up logging
2. Chatbot registry - accessing the available chatbots from the shared registry
3. Conversation initialization - setting up chatbots for a new session
4. Main conversation loop - the interactive chat interface with command handling
"""

import logging
from time import time

from config.conditions import ChatbotType
from config.runtime import CURRENT_CHAT_MODEL
from config.tunables import (
    CHUNKS_INCLUDED_IN_CONTEXT,
    MIN_TURNS_BEFORE_HANDOVER,
    RELEVANCE_THRESHOLD,
)
from src.chat.preprocessing.abbreviation_expander import expand_abbreviations
from src.chat.query_router import QueryRouter
from src.chatbot_core.registry import ChatbotRegistry

# ============================================================================
# LOGGING SETUP
# ============================================================================
# Set up logging so actions and errors are displayed on screen.
# When running normally, logs are set to WARNING level to keep the conversation clean.
# Toggle admin mode to see detailed INFO logs for debugging.

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CHATBOT REGISTRY
# ============================================================================
# The ChatbotRegistry is imported from src/chatbot_core/registry.py, where all
# chatbot metadata and initialization logic is centralized.
#
# The registry knows:
# - Which chatbots are available
# - How to initialize each chatbot
# - The name and role of each chatbot
# - Display names and greeting messages

registry = ChatbotRegistry()


def initialize_new_conversation(): # Currently set to teacher-study adviser handover scenario
    """
    Set up all chatbots for a new conversation.
    
    This function creates both the Study Adviser and Teacher chatbots and
    puts them in a dictionary so the main loop can easily switch between them.
    
    Returns:
        A tuple containing:
        - study_adviser: The initialized Study Adviser chatbot
        - teacher: The initialized Teacher chatbot  
        - chatbot_map: A dictionary mapping chatbot types to their instances
                      (used for switching between chatbots)
    """
    logger.info("Initializing new conversation")
    study_adviser = registry.initialize_bot_by_type(ChatbotType.STUDY_ADVISER)
    teacher = registry.initialize_bot_by_type(ChatbotType.TEACHER)
    
    chatbot_map = {
        ChatbotType.STUDY_ADVISER: study_adviser,
        ChatbotType.TEACHER: teacher,
    }
    
    return study_adviser, teacher, chatbot_map

# ============================================================================
# MAIN CONVERSATION LOOP
# ============================================================================
# This is the interactive chat interface that runs when you start the chatbot
# from the command line. It handles everything: displaying prompts, getting user
# input, routing messages to the right chatbot, and printing responses.
#
# Key features:
# - Switching between chatbots based on user questions
# - Special commands:
#       exit,       # Exit chat
#       admin,      # For debugging and diagnostics
#       history,    # See current conversation history
#       restart     # Restart conversation with current chatbot

def main():
    """
    Run the command-line chatbot interface.
    
    This function handles the main conversation loop and includes:
    - Setting up both chatbots at the start
    - Displaying user prompts and bot responses
    - Routing user questions to the appropriate chatbot
    - Handling special commands like 'exit' and 'admin'
    - Switching between chatbots when the user's topic changes
    """
    
    # Initialize the chatbots
    study_adviser, teacher, chatbot_map = initialize_new_conversation()
    
    # Initialize the router that decides which chatbot should answer each question
    router = QueryRouter()
    
    # Start the conversation with the Teacher bot
    current_bot = teacher
    current_bot_type = ChatbotType.TEACHER

    admin_mode = False  # Toggle for showing diagnostic information
    turn_count = 0      # Track how many turns have passed (to prevent early handover)

    # After initialization, suppress INFO logs to reduce console clutter during conversation
    # Re-enable logging by toggling admin mode
    logging.getLogger().setLevel(logging.WARNING)

    # Display welcome message with available commands
    print("\n============================")
    print(f"Chatbots initialized with model {CURRENT_CHAT_MODEL.model}. Commands:")
    print("'exit'/'quit' to end conversation")
    print("'admin' to toggle admin mode")
    print("'history' to view conversation history")
    print("'restart' to start a new conversation")
    print("============================" + "\n")

    # Display the first chatbot's greeting
    bot_display_name = registry.get_bot_display_name(current_bot_type)
    print(f"{bot_display_name}:")
    conversation_starter = registry.get_greeting(current_bot_type)
    print(conversation_starter)
    print("-" * 60)

    # Main conversation loop - keep asking for input until user exits
    while True:
        user_query = input("You: ").strip()

        # ================================================================
        # HANDLE SPECIAL COMMANDS
        # ================================================================
        # Users can type special commands instead of questions
        
        # Exit the program
        if user_query.lower() in {"exit", "quit"}:
            logger.info("User exited conversation")
            print("\nGoodbye!")
            break

        # Toggle admin mode to see diagnostic information
        if user_query.lower() == "admin":
            admin_mode = not admin_mode
            status = "ON" if admin_mode else "OFF"
            # Enable detailed logging in admin mode, suppress in normal mode
            if admin_mode:
                logging.getLogger().setLevel(logging.INFO)
            else:
                logging.getLogger().setLevel(logging.WARNING)
            print(f"(admin mode {status})")
            logger.info(f"Admin mode toggled: {status}")
            continue    

        # Show conversation history
        if user_query.lower() == "history":
            history = current_bot.get_history()
            print("Current conversation history:")
            for msg in history:
                print(msg)
                print("-" * 20)
            continue

        # Start a fresh conversation with new chatbots
        if user_query.lower() == "restart":
            study_adviser, teacher, chatbot_map = initialize_new_conversation()
            current_bot = chatbot_map[current_bot_type]
            turn_count = 0

            print("Started a new conversation.")
            bot_display_name = registry.get_bot_display_name(current_bot_type)
            print(f"{bot_display_name}:")
            conversation_starter = registry.get_greeting(current_bot_type)
            print(conversation_starter)
            print("-" * 60)
            continue
        
        # ================================================================
        # VALIDATE AND PROCESS USER INPUT
        # ================================================================
        
        # Skip empty inputs
        if not user_query:
            print("Please enter something or type 'exit'.")
            continue

        # Convert any predetermined abbreviations in the user's message to full words
        expanded_query = expand_abbreviations(user_query)

        # ================================================================
        # DECIDE IF CHATBOT SHOULD SWITCH
        # ================================================================
        # Analyze the user's question to see if it would be better answered 
        # by the other chatbot. Only switch if MIN_TURNS_BEFORE_HANDOVER has passed.
        
        # Ask the router which chatbot should answer this question
        chatbot_type, switch_needed = router.route_query(expanded_query, current_bot_type)
        
        # Only allow switching after a certain number of turns (to avoid switching too early)
        handover_allowed = turn_count >= MIN_TURNS_BEFORE_HANDOVER
        
        # Decide if we actually need to switch
        handover_needed = switch_needed and handover_allowed
               
        # ================================================================
        # HANDLE CHATBOT SWITCHING
        # ================================================================
        # If handover is needed, notify user and switch.
        
        handover_context = None
        if handover_needed:
            logger.info(f"Handover triggered from {current_bot.name} to {chatbot_type.value}")
            
            # Get information about the target bot for the handover message
            target_bot_name = registry.get_bot_name(chatbot_type)
            target_bot_role = registry.get_bot_role(chatbot_type)
            current_bot_display_name = registry.get_bot_display_name(current_bot_type)
            
            # Display the handover message to the user
            print("-" * 60)
            print(f"{current_bot_display_name}:")
            print(f"""From what you're saying, I believe that it would be best to talk to {target_bot_name}, the {target_bot_role} of Creative Technology. They can help you further. I will summarise our conversation and hand it over.

Please wait for a bit while I hand over the conversation to {target_bot_name}...""")

            # Give the new chatbot context about the previous conversation
            handover_context = current_bot.prepare_handover_context()
            
            # Switch to the other chatbot
            current_bot = chatbot_map[chatbot_type]
            current_bot_type = chatbot_type

        # ================================================================
        # GET BOT RESPONSE
        # ================================================================
        # Send the user's question to the current chatbot and get a response
        
        time_process_query_start = time()

        try:
            # Process the user's question and get a response
            result, chunks, status = current_bot.process_query(
                expanded_query,
                num_chunks=CHUNKS_INCLUDED_IN_CONTEXT,
                score_threshold=RELEVANCE_THRESHOLD,
                handover_context=handover_context,
            )  
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            print("Chatbot: Sorry, something went wrong. Please try again.")
            continue
        
        time_process_query_end = time()
        
        # ================================================================
        # ADMIN MODE - Show diagnostic information if enabled
        # ================================================================
        # In admin mode, show extra technical details about how the response was generated
        
        if admin_mode:
            print("-" * 60)
            print("--- Admin ---")
            print(f"Expanded query:   {expanded_query}")
            print(f"Processed query in {format(time_process_query_end - time_process_query_start, '.2f')} seconds")
            print(f"Turn count: {1+turn_count}. Handover was possible: {'Yes' if turn_count >= MIN_TURNS_BEFORE_HANDOVER else 'No'}.")
            print("\nRetrieved chunks:")
            for i, ch in enumerate(chunks, start=1):
                score = ch.get("score", 0.0)
                file = ch.get("file", "unknown")
                chunk_num = ch.get("chunk_num", "?")
                print(f"[Chunk {i}] | Score={score:.2f} | File={file} [chunk {chunk_num}]")

        # ================================================================
        # EXTRACT AND DISPLAY RESPONSE
        # ================================================================
        
        # Get the response text from the bot's result
        response = result["messages"][-1]
        try:
            response_text = response.content
        except AttributeError:
            response_text = str(response)
        
        # Check if the response quality is low (only log in admin mode)
        if admin_mode:
            if status == "no_context":
                logger.warning("Low confidence response: no relevant context")
            elif status == "low_context":
                logger.warning("Low confidence response: limited relevant context")

        # Display the bot's response to the user
        bot_display_name = registry.get_bot_display_name(current_bot_type)
        print("-" * 60)
        print(f"{bot_display_name}:")
        print(response_text)
        print("-" * 60)
        
        # Increase the turn counter
        turn_count += 1
    

if __name__ == "__main__":
    main()