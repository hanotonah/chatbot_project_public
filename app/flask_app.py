"""
Web-based chatbot system using Flask for multi-user conversations.

This module creates a web interface where users can log in and have conversations
with different chatbots through their browser. Users are assigned to different
study conditions which determine which chatbots they interact with. The system
handles user authentication, conversation management, switching between chatbots,
and logging all conversations for research purposes.

The file is organized into these main sections:
1. Flask app setup and global configuration
2. Cleanup and utility functions for session management
3. Chatbot registry - loads available chatbots from shared configuration
4. Helper functions for checking conversation history and initializing chatbots
5. Flask routes for web pages (login, chat, etc.)
6. API endpoints that handle chatbot interactions from the web interface
7. Handover helper functions for switching between chatbots
"""

import atexit
from datetime import datetime
import logging
from pathlib import Path
import secrets
from time import time
from typing import Optional
import winsound

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session

from config.config import Config
from config.conditions import get_condition_by_key
from config.runtime import (
    CURRENT_CHAT_MODEL,
    CURRENT_EMBEDDINGS_MODEL,
    CURRENT_SUMMARIZATION_MODEL,
)
from config.tunables import (
    CHUNKS_INCLUDED_IN_CONTEXT,
    ENABLE_RESPONSE_SUMMARIZATION,
    MIN_TURNS_BEFORE_HANDOVER,
    MIN_TURNS_AFTER_HANDOVER_FOR_ENDING,
    RELEVANCE_THRESHOLD,
    RESPONSE_SENTENCE_LIMIT,
)
from src.chat.chat_session import ChatSessionManager
from src.chat.conversation_logger import ConversationLogger, sanitize_filename
from src.chat.preprocessing.abbreviation_expander import expand_abbreviations
from src.chat.query_router import QueryRouter
from src.chat.response_validator import needs_summarization, summarize_response
from src.chatbot_core.registry import ChatbotRegistry
from storage.participants.participant_registry import (
    get_or_assign_participant_condition,
    get_participant_stats,
)

# Set up logging so actions and errors are displayed on screen
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APPLICATION SETUP
# ============================================================================
# Initialize the Flask app with custom folders for web templates and static files
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.config.from_object(Config)

# Set up server-side sessions (saved on disk in `storage/flask_session`)
Session(app)

# Initialize the session manager (keeps track of all active conversations)
# and conversation logger (records all interactions for research)
session_manager = ChatSessionManager()
conversation_logger = ConversationLogger()


# ============================================================================
# CLEANUP AND UTILITY FUNCTIONS
# ============================================================================

def cleanup_on_shutdown():
    """
    Clean up temporary session files when the Flask application stops.
    
    This function removes all temporary Flask session files from the server
    to ensure no incomplete sessions are left behind when the app shuts down.
    """
    try:
        session_dir = Path('storage/flask_session')
        if session_dir.exists():
            # Remove all session files
            for session_file in session_dir.iterdir():
                if session_file.is_file():
                    session_file.unlink()
                    logger.info(f"Cleaned up session file on shutdown: {session_file.name}")
            logger.info("All Flask session files cleaned up on shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}")


# Register cleanup function to run when the app exits
atexit.register(cleanup_on_shutdown)


def get_model_identifier(model_obj):
    """
    Convert a model object into a readable string identifier.
    
    This is used for logging and display purposes to show which LLMs
    are being used by the chatbot system.
    
    Args:
        model_obj: A model object or string that needs to be converted
    
    Returns:
        A string identifier for the model
    """
    if isinstance(model_obj, str):
        return model_obj
    return getattr(model_obj, "model", getattr(model_obj, "model_name", str(model_obj)))


# ============================================================================
# CHATBOT REGISTRY
# ============================================================================
# The ChatbotRegistry is imported from `src/chatbot_core/registry.py`, where all
# chatbot metadata and initialization logic is centralized.
#
# The registry knows:
# - Which chatbots are available (Teacher, Study Adviser, General)
# - How to initialize each chatbot
# - The name, role, and display name of each chatbot
# - Greeting messages for starting conversations

registry = ChatbotRegistry()

# A keyword detector is kept ready at all times so that handover keywords can be
# recognised in every study condition — including the single-chatbot condition where
# the router is disabled and no actual handover takes place.
_keyword_detector = QueryRouter()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
# These utility functions handle common tasks needed throughout the web interface,
# such as checking if someone has already participated and initializing conversations
# based on their assigned study condition.

def check_existing_conversation_log(participant_code: str) -> Optional[Path]:
    """
    Check if a conversation log already exists for a given participant code.
    If a conversation log exists, warn the user and ask if they want to continue.
    
    Args:
        participant_code: The unique participant ID to check (assumed to be already sanitized)
    
    Returns:
        The path to an existing conversation log file, or None if no log exists
    """
    log_dir = Path('storage/conversation_logs')
    if not log_dir.exists():
        return None
    
    # Look for any file starting with the participant code
    for log_file in log_dir.glob(f"{participant_code}_*.json"):
        return log_file
    
    return None


# ============================================================================
# CONVERSATION INITIALIZATION
# ============================================================================
# This function initializes chatbots based on the study condition assigned to
# each participant. Different conditions might require different chatbots.

def initialize_new_conversation(condition_key: str):
    """
    Set up chatbots for a participant's assigned study condition.
    
    Each participant is randomly assigned one of several study conditions when
    they log in. This function reads their condition and initializes the chatbots
    that are configured for that condition.
    
    Args:
        condition_key: A unique identifier for the study condition
                       (this determines which chatbots are available)
    
    Returns:
        A tuple containing:
        - starting_bot: The chatbot that should start the conversation
        - chatbot_map: A dictionary mapping chatbot types to their instances
                       (used for switching between chatbots)
        - condition: The condition object with metadata about this configuration
    """
    # Get the condition configuration for this participant
    condition = get_condition_by_key(condition_key)
    logger.info(f"Initializing conversation for condition: {condition.name}")
    
    # Initialize chatbots based on what's configured for this condition
    chatbot_map = {}
    
    for bot_type in condition.chatbots:
        if bot_type not in registry._registry:
            logger.error(f"Unknown chatbot type: {bot_type}")
            raise ValueError(f"Unknown chatbot type: {bot_type}")
        chatbot_map[bot_type] = registry.initialize_bot_by_type(bot_type)
    
    # Get the starting bot from the map (the one that says hello first)
    starting_bot = chatbot_map[condition.starting_bot]
    
    logger.info(f"Initialized {len(chatbot_map)} chatbot(s): {[bot.value for bot in chatbot_map.keys()]}")
    logger.info(f"Starting bot: {condition.starting_bot.value}")
    
    return starting_bot, chatbot_map, condition


# ============================================================================
# ROUTES - Web pages that users see in their browser
# ============================================================================
# These functions handle the different web pages in the chatbot system.
# When a user navigates to a URL (like /login or /chat), Flask calls the
# corresponding function to display the right page or handle the interaction.

@app.route('/')
def index():
    """
    Home page: Redirect to the appropriate starting page.
    
    If the user is already logged in, they go to the initialization page.
    If not, they go to the login page to enter their participant code.
    """
    if session.get('authenticated'):
        return redirect(url_for('init'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page: Handle participant sign-in with a participant code.
    """
    if request.method == 'POST':
        participant_code = request.form.get('participant_code', '').strip()
        
        if not participant_code:
            return render_template('login.html', error="Please enter a student ID")
        
        # Sanitize the participant code to prevent filesystem issues
        participant_code = sanitize_filename(participant_code)
        
        try:
            # Check if conversation log already exists for this participant code
            existing_log = check_existing_conversation_log(participant_code)
            
            if existing_log:
                # Log already exists - ask user for confirmation
                session['pending_participant_code'] = participant_code
                return redirect(url_for('duplicate_id_warning'))
            
            # Get or assign a study condition for this participant
            condition_key = get_or_assign_participant_condition(participant_code)
            
            # Create a new session ID (unique identifier for this conversation)
            session_id = secrets.token_hex(16)
            logger.info(f"Participant {participant_code} starting new chat session with condition: {condition_key}")
            
            # Save their info in the session (cookie stored on their computer)
            session['authenticated'] = True
            session['participant_code'] = participant_code
            session['condition_key'] = condition_key
            session['session_id'] = session_id
            
            return redirect(url_for('init'))
            
        except ValueError as e:
            logger.error(f"Condition assignment error: {e}")
            return render_template('login.html', error="System configuration error. Please contact the researcher.")
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return render_template('login.html', error="An error occurred. Please try again.")
    
    return render_template('login.html')

@app.route('/duplicate_id_warning', methods=['GET', 'POST'])
def duplicate_id_warning():
    """
    Warning page: Indicate that the participant ID already has a conversation log.
    """
    participant_code = session.get('pending_participant_code')
    
    if not participant_code:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        
        if action == 'go_back':
            # User wants to use a different code
            session.pop('pending_participant_code', None)
            return redirect(url_for('login'))
        
        elif action == 'continue':
            # User wants to continue (delete old conversation log)
            existing_log = check_existing_conversation_log(participant_code)
            if existing_log:
                try:
                    existing_log.unlink()
                    logger.info(f"Deleted old conversation log for participant {participant_code}: {existing_log}")
                except Exception as e:
                    logger.error(f"Error deleting old log file: {e}")
            
            # Proceed with login
            try:
                condition_key = get_or_assign_participant_condition(participant_code)
                session_id = secrets.token_hex(16)
                
                # Clear the temporary code
                session.pop('pending_participant_code', None)
                
                # Save their info in the session
                session['authenticated'] = True
                session['participant_code'] = participant_code
                session['condition_key'] = condition_key
                session['session_id'] = session_id
                
                logger.info(f"Participant {participant_code} continuing after deleting old log, new session: {session_id}")
                return redirect(url_for('init'))
                
            except Exception as e:
                logger.error(f"Error during continue action: {e}", exc_info=True)
                return render_template('duplicate_id_warning.html', 
                                     participant_code=participant_code,
                                     error="An error occurred. Please try again.")
    
    return render_template('duplicate_id_warning.html', participant_code=participant_code)

@app.route('/init')
def init():
    """
    Initialization page: Loading screen while chatbots are being initialized.
    """
    if not session.get('authenticated'): # Extra check to prevent unauthorized access
        return redirect(url_for('login'))
    
    return render_template('init.html')

@app.route('/chat')
def chat():
    """
    Chat page: Main conversation interface.
    
    This is where the user types messages and sees responses from the chatbot.
    It expects the chatbots to already be initialized (done by the `/api/init_session` API).
    """
    if not session.get('authenticated'): # Extra check to prevent unauthorized access
        return redirect(url_for('login'))
    
    session_id = session.get('session_id')
    
    # Check if the backend has initialized the chatbots
    if not session_manager.has_session(session_id):
        logger.warning(f"Chat accessed without initialization for session {session_id}")
        return redirect(url_for('init'))
    
    return render_template('chat.html', participant_code=session.get('participant_code'))


@app.route('/logout')
def logout():
    """
    Logout page: End the conversation and show closing message.
    """
    session_id = session.get('session_id')
    
    if session_id:
        # Save their conversation
        session_manager.end_session(session_id, conversation_logger)
    
    logger.info("User logged out")
    # Show conversation ended page instead of redirecting to login
    return render_template('conversation_ended.html')


@app.route('/admin/stats')
def admin_stats():
    """
    Admin page: View research study statistics.
    
    This page (only for researchers) shows how many participants have been
    assigned to each study condition to monitor progression.
    """
    stats = get_participant_stats()
    return jsonify(stats)


# ============================================================================
# API ENDPOINTS - Backend functions called by the web interface
# ============================================================================
# These are JSON endpoints that the JavaScript on the web page calls when the user
# interacts with the chatbot. They handle the actual chatbot processing and return
# JSON responses that the JavaScript updates on the page.

@app.route('/api/init_session', methods=['POST'])
def api_init_session():
    """
    Initialize backend chatbots for a user's session.
    
    This endpoint is called when the user first loads the chat page.
    It sets up the chatbots on the server side based on their assigned condition,
    creates the session data structures, and prepares everything for the conversation.
    """
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    condition_key = session.get('condition_key')
    participant_code = session.get('participant_code')
    
    try:
        # Only initialize if not already done
        if not session_manager.has_session(session_id):
            starting_bot, chatbot_map, condition = initialize_new_conversation(condition_key)
            models_used = {
                'chat_model': get_model_identifier(CURRENT_CHAT_MODEL),
                'summarization_model': get_model_identifier(CURRENT_SUMMARIZATION_MODEL),
                'embedding_model': get_model_identifier(CURRENT_EMBEDDINGS_MODEL)
            }
            
            session_manager.create_session(
                session_id=session_id,
                username=participant_code,
                chatbot_map=chatbot_map,
                current_bot=starting_bot,
                current_bot_type=condition.starting_bot,
                router=QueryRouter() if condition.enable_routing else None,
                models_used=models_used,
                condition_key=condition_key
            )
            
            logger.info(f"Created new chat session: {session_id} with condition: {condition.name}")
        
        return jsonify({
            'success': True,
            'message': 'Initialization complete'
        })
    except Exception as e:
        logger.error(f"Error during initialization: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to initialize chatbots'
        }), 500


@app.route('/api/init_chat', methods=['POST'])
def api_init_chat():
    """
    Get and display the starting greeting from the chatbot.
    """
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    chat_session = session_manager.get_session(session_id)
    
    if not chat_session:
        return jsonify({'error': 'Session not found'}), 404
    
    bot_name = chat_session['current_bot'].name
    
    # Get the greeting message
    greeting = registry.get_greeting(chat_session['current_bot_type'])
    
    # Record the greeting in the conversation log
    conversation_logger.log_message(
        session_id=session_id,
        speaker=bot_name,
        ai_response=greeting,
        user_query=None,
        expanded_query=None,
        timestamp=datetime.now(),
        handover_info=None,
        chunks=None,
        processing_time=None,
        summarization_info=None
    )
    
    return jsonify({
        'bot_name': bot_name,
        'bot_display_name': registry.get_bot_display_name(chat_session['current_bot_type']),
        'greeting': greeting
    })


@app.route('/api/message', methods=['POST'])
def api_message():
    """
    Process a user message and return the chatbot's response.
    
    This is the main endpoint that handles all conversation. When the user
    types a message and clicks send, the JavaScript calls this endpoint.
    
    The function handles these steps:
    1. Gets the user's message from the web page
    2. Expands any abbreviations (e.g., "CT" becomes "Creative Technology")
    3. Records whether a handover keyword was mentioned for the first time
       (needed to determine when the session's ending phase should begin)
    4. Checks if the message should trigger a handover
    5. Checks if enough turns have passed since the handover event to trigger
       the session ending (if so, the ending messages replace the bot response)
    6. Gets the chatbot's response
    7. Checks if the response is too long and summarizes it if needed
    8. Logs the message and response to the conversation history
    9. Returns the response back to the web page for display
    """
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_query = data.get('message', '').strip()
    is_handover_followup = data.get('is_handover_followup', False)
    
    if not user_query:
        return jsonify({'error': 'Empty message'}), 400
    
    session_id = session.get('session_id')
    chat_session = session_manager.get_session(session_id)
    
    if not chat_session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Get the current state
    current_bot = chat_session['current_bot']
    current_bot_type = chat_session['current_bot_type']
    chatbot_map = chat_session['chatbot_map']
    router = chat_session['router']
    turn_count = chat_session['turn_count']
    
    # Convert abbreviations to full words
    expanded_query = expand_abbreviations(user_query)
    
    # --- Record the first time a handover keyword is mentioned ---
    # This starts the ending countdown regardless of whether an actual handover
    # takes place (in the single-chatbot condition there is no handover, but the
    # same keywords still signal the relevant moment in the conversation).
    # The check is skipped for handover follow-ups because the original keyword
    # message has already been recorded.
    if (not is_handover_followup
            and chat_session.get('handover_event_turn') is None
            and turn_count >= MIN_TURNS_BEFORE_HANDOVER
            and _keyword_detector.get_triggered_keyword(expanded_query.lower())):
        chat_session['handover_event_turn'] = turn_count
        logger.info(
            f"Handover keyword detected at turn {turn_count}. "
            f"Ending will trigger after {MIN_TURNS_AFTER_HANDOVER_FOR_ENDING} more turns."
        )

    # Check if this message should hand over to a different chatbot
    if not is_handover_followup:
        handover_needed, target_bot_type, triggered_keyword = check_handover_needed(
            router, expanded_query, current_bot_type, turn_count
        )
        
        # If handover needed, return handover message and don't process the message yet
        if handover_needed:
            return create_handover_response(
                session_id, current_bot, target_bot_type,
                expanded_query, triggered_keyword, user_query
            )
    
    # --- Check whether the session ending phase should begin ---
    # Like handover, this intercepts the user's message before the chatbot
    # processes it. The ending is triggered after a handover keyword was
    # detected AND enough additional turns have passed (both thresholds are
    # set in config/tunables.py).
    handover_event_turn = chat_session.get('handover_event_turn')

    if (not is_handover_followup
            and handover_event_turn is not None
            and turn_count - handover_event_turn >= MIN_TURNS_AFTER_HANDOVER_FOR_ENDING):

        # ---- Edit the ending messages here ----
        # These messages are shown to the student once the conversation phase
        # is complete. 'text' messages appear as normal chat bubbles; the
        # 'link' message shows a clickable link to the planning template page.
        ending_messages = [
            {
                'type': 'text',
                'text': "Some students who struggle with time management find it useful to discuss their planning with other students. We run a small study help group where students bring and discuss a weekly plan that everyone prepares beforehand."
            },
            {
                'type': 'text',
                'text': "For now, I would suggest that you try creating a weekly plan, and to join the study help group if you think it could be useful for you."
            },
            {
                'type': 'link',
                'text': "You can find a template weekly planning here: ",
                'link_url': '/planning',
                'link_text': "Template weekly planning"
            }
        ]
        # ---- End of ending messages ----

        logger.info(
            f"Session ending triggered at turn {turn_count} "
            f"({turn_count - handover_event_turn} turns after handover event at turn {handover_event_turn})."
        )

        # Keep session turn_count aligned with the logged turn
        session_manager.update_session(
            session_id=session_id,
            current_bot=current_bot,
            current_bot_type=current_bot_type,
            turn_count=turn_count + 1
        )

        # Store ending messages in the log as one combined assistant response
        ending_message_text = "\n\n".join(
            (msg['text'] + msg['link_text'] + " (" + msg['link_url'] + ")")
            if msg.get('type') == 'link'
            else msg['text']
            for msg in ending_messages
        )

        conversation_logger.log_message(
            session_id=session_id,
            speaker=current_bot.name,
            ai_response=ending_message_text,
            user_query=user_query,
            expanded_query=expanded_query,
            timestamp=datetime.now(),
            handover_info={'session_ending': True},
            chunks=None,
            processing_time=None,
            summarization_info=None
        )

        return jsonify({
            'bot_name': current_bot.name,
            'bot_display_name': registry.get_bot_display_name(current_bot_type),
            'session_ending': True,
            'ending_messages': ending_messages
        })

    # If we're in the middle of a handover, get the new bot and context
    handover_context = None
    if chat_session.get('pending_handover'):
        current_bot, current_bot_type, expanded_query, handover_context = process_handover_followup(
            chat_session, chatbot_map
        )
    
    # Process query (send to the chatbot and get response)
    time_start = time()
    
    try:
        result, chunks, status = current_bot.process_query(
            expanded_query,
            num_chunks=CHUNKS_INCLUDED_IN_CONTEXT,
            score_threshold=RELEVANCE_THRESHOLD,
            handover_context=handover_context,
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        return jsonify({'error': 'Error processing your message'}), 500
    
    time_end = time()
    
    # Extract the response text
    response = result["messages"][-1]
    try:
        response_text = response.content
    except AttributeError:
        response_text = str(response)
    
    # Safety check: make sure we have a response
    if not response_text.strip():
        logger.warning(f"Empty response detected for query: {expanded_query[:100]}...")
        response_text = "I apologize, but I wasn't able to respond at this moment. Please try again."
    
    summarization_info = None

    if ENABLE_RESPONSE_SUMMARIZATION:
        # Check if the response is too long and should be summarized
        should_summarize, reason = needs_summarization(response_text, sentence_limit=RESPONSE_SENTENCE_LIMIT)
        original_response = response_text

        if should_summarize:
            logger.info(f"Response needs summarization. Reason: {reason}")

            # Get the conversation history and bot personality
            chat_history = current_bot.get_history()
            bot_persona = current_bot.get_persona()

            # Try to summarize the response
            try:
                response_text = summarize_response(
                    llm_model=CURRENT_SUMMARIZATION_MODEL,
                    original_response=response_text,
                    chat_history=chat_history,
                    persona=bot_persona
                )
                logger.info(f"Response successfully summarized (reason: {reason})")

                # Store summarization info for logging
                summarization_info = {
                    'original_response': original_response,
                    'reason': reason
                }
            except Exception as e:
                logger.error(f"Failed to summarize response: {e}", exc_info=True)
                # Keep original response if summarization fails
                response_text = original_response
    
    # Record this message and response in the conversation log
    conversation_logger.log_message(
        session_id=session_id,
        speaker=current_bot.name,
        ai_response=response_text,
        user_query=user_query,
        expanded_query=expanded_query,
        timestamp=datetime.now(),
        handover_info=None,
        chunks=chunks,
        processing_time=time_end - time_start,
        summarization_info=summarization_info
    )
    
    # Update the session with current state (new turn count, current bot, etc.)
    session_manager.update_session(
        session_id=session_id,
        current_bot=current_bot,
        current_bot_type=current_bot_type,
        turn_count=turn_count + 1
    )

    # Prepare the response to send back to the web page
    response_data = {
        'bot_name': current_bot.name,
        'bot_display_name': registry.get_bot_display_name(current_bot_type),
        'bot_role': registry.get_bot_role(current_bot_type),
        'response': response_text,
        'handover_occurred': False
    }
    
    return jsonify(response_data)


@app.route('/api/end_conversation', methods=['POST'])
def api_end_conversation():
    """
    End the conversation and save all logs.
    """
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    
    if session_id:
        # If the chat session was already ended earlier, treat this as a valid
        # no-op. This avoids duplicate-end warnings when the user clicks
        # "End Conversation" after an automatic end.
        if not session_manager.has_session(session_id):
            logger.info(f"Conversation already ended for session {session_id}")
            return jsonify({
                'message': 'Conversation was already ended',
                'log_file': None,
                'redirect': '/conversation_ended'
            })

        # Save the conversation
        log_file = session_manager.end_session(session_id, conversation_logger)
        logger.info(f"Conversation ended and saved to {log_file}")
        
        return jsonify({
            'message': 'Conversation ended successfully',
            'log_file': str(log_file),
            'redirect': '/conversation_ended'
        })
    
    return jsonify({'error': 'No active session'}), 404


@app.route('/conversation_ended')
def conversation_ended():
    """
    Conversation ended page: Show closing message to the user.
    """
    return render_template('conversation_ended.html')


@app.route('/planning')
def planning():
    """
    Planning page: Shown to the participant at the end of the study session.
    """
    return render_template('planning.html')


@app.route('/api/play_notification', methods=['POST'])
def play_notification():
    """
    Play a notification sound on the server machine.

    Called from the client when the participant clicks the planning link,
    so that nearby researchers hear that the participant has reached this point.
    """
    sound_path = Path(__file__).parent / 'static' / 'sounds' / 'notification_sound.wav'
    if sound_path.exists():
        # SND_FILENAME: play from file, SND_ASYNC: return immediately
        winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    return jsonify({'status': 'ok'})


@app.route('/api/cleanup_session', methods=['POST'])
def cleanup_session():
    """
    Delete temporary session data when user closes the closing page.
    """
    # Delete the Flask session file
    delete_flask_session_file()
    
    # Clear the session
    session.clear()
    
    logger.info("Session cleaned up after user closed end page")
    return jsonify({'message': 'Session cleaned up'})


@app.route('/api/cleanup_session_on_exit', methods=['POST'])
def cleanup_session_on_exit():
    """
    Emergency cleanup if user navigates away without ending conversation properly.
    
    If a user closes the chat page or navigates away without clicking
    "End Conversation", this function saves their conversation log
    before cleaning up the session.
    """
    try:
        # Track which session we're cleaning up
        session_id = session.get('session_id', 'unknown')
        
        # If there's an active session, save it
        if session_id != 'unknown':
            chat_session = session_manager.get_session(session_id)
            if chat_session:
                # Save the conversation
                log_file = session_manager.end_session(session_id, conversation_logger)
                logger.info(f"Conversation ended and saved (user left page) to {log_file}")
        
        # Clean up temporary files
        delete_flask_session_file()
        
        # Clear the session
        session.clear()
        
        logger.info(f"Session {session_id} cleaned up after user left page")
        return '', 204  # Return 204 No Content response
    except Exception as e:
        logger.error(f"Error cleaning up session on exit: {e}")
        return '', 204  # Still return 204 even on error


# ============================================================================
# HELPER FUNCTIONS - Supporting functions for backend operations
# ============================================================================

def delete_flask_session_file() -> None:
    """
    Delete the temporary Flask session file.
    
    Flask creates temporary files to store session data on the server.
    This function deletes those files to clean up after a conversation.
    """
    try:
        # Get Flask's session cookie value
        session_cookie = request.cookies.get(app.config['SESSION_COOKIE_NAME'])
        
        if session_cookie:
            # Flask-Session uses the cookie value as the filename
            session_file = Path('storage/flask_session') / session_cookie
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Deleted flask session file: {session_file}")
            else:
                logger.debug(f"Session file not found: {session_file}")
        else:
            logger.debug("No session cookie found for deletion")
    except Exception as e:
        logger.warning(f"Could not delete session file: {e}")


# ============================================================================
# HANDOVER HELPER FUNCTIONS - Manage switching between chatbots
# ============================================================================
# Handover is when the conversation is switched from one chatbot to another.
# Currently, this is keyword-based. If a keyword is detected and enough turns
# have passed, the system will inform the user that they will hand over the 
# conversation to a different chatbot and prepare for the switch. 

def check_handover_needed(router, expanded_query, current_bot_type, turn_count):
    """
    Determine if the user's message should trigger a handover to a different chatbot.
    Currently based on keyword detection and minimum turn count to avoid early handovers.
        
    Args:
        router: The QueryRouter that decides which chatbot should answer
               (or None if routing is disabled)
        expanded_query: The user's message with abbreviations expanded
        current_bot_type: Which chatbot is currently talking to the user
        turn_count: How many turns have happened so far in the conversation
    
    Returns:
        A tuple with:
        - handover_needed: True if we should trigger a handover
        - target_bot_type: Which chatbot to hand over to (if handover needed)
        - triggered_keyword: What keyword triggered the handover (if handover needed)
    """
    # If no router, routing is disabled for this study condition
    if router is None:
        return False, current_bot_type, None
    
    # Ask the router which chatbot should handle this message
    chatbot_type, switch_needed = router.route_query(expanded_query, current_bot_type)
    
    # Only allow handover after enough turns have passed
    handover_allowed = turn_count >= MIN_TURNS_BEFORE_HANDOVER
    
    # Both conditions must be true to actually hand over
    handover_needed = switch_needed and handover_allowed
    
    # Get the keyword that triggered this handover (if one occurred)
    triggered_keyword = None
    if handover_needed:
        triggered_keyword = router.get_triggered_keyword(expanded_query.lower())
    
    return handover_needed, chatbot_type, triggered_keyword


def create_handover_response(session_id, current_bot, target_bot_type, expanded_query, triggered_keyword, user_query):
    """
    Create the handover notification message and prepare for the handover.
    
    When a handover is triggered, this function:
    1. Creates a message explaining why the handover is happening
    2. Gets the current conversation context from the current bot
    3. Stores the handover info for the next request
    
    Args:
        session_id: The unique identifier for this conversation session
        current_bot: The chatbot currently handling the conversation
        target_bot_type: Which chatbot to hand over to
        expanded_query: The user's message with abbreviations expanded
        triggered_keyword: The specific keyword that triggered the handover
        user_query: The original user message (before expansion)
    
    Returns:
        A JSON response to send to the web page with the handover messages
    """    
    # Get information about the target bot for the handover message
    target_bot_name = registry.get_bot_name(target_bot_type)
    target_bot_role = registry.get_bot_role(target_bot_type)

    logger.info(f"Handover triggered from {current_bot.name} to {target_bot_name} (keyword: {triggered_keyword})")
    
    # Create the two handover messages shown before the switch
    handover_messages = [
        f"From what you're saying, I believe that it would be best to talk to {target_bot_name}, the {target_bot_role} of Creative Technology. They can help you further. I will summarise our conversation and hand it over.",
        f"Please wait for a bit while I hand over the conversation to {target_bot_name}..."
    ]
    
    # Record the handover messages in the conversation log as one combined entry
    conversation_logger.log_message(
        session_id=session_id,
        speaker=current_bot.name,
        ai_response="\n\n".join(handover_messages),
        user_query=user_query,
        expanded_query=expanded_query,
        timestamp=datetime.now(),
        handover_info={
            'triggered': True,
            'keyword': triggered_keyword
        },
        chunks=None,
        processing_time=None,
        summarization_info=None
    )
    
    # Store the handover information so the next request can process it
    chat_session = session_manager.get_session(session_id)
    chat_session['pending_handover'] = {
        'to_bot_type': target_bot_type,
        'query': user_query,
        'expanded_query': expanded_query
    }
    
    # Send response to web page
    return jsonify({
        'handover_occurred': True,
        'handover_messages': handover_messages,
        'bot_name': current_bot.name,
        'bot_display_name': registry.get_bot_display_name(target_bot_type),
        'target_bot_name': target_bot_name,
        'requires_followup': True,
        'clear_messages': True
    })


def process_handover_followup(chat_session, chatbot_map):
    """
    Retrieve handover information, prepare handover context using 
    conversation history, and switch to the new chatbot.
    """
    # Get the handover information that was stored
    pending = chat_session['pending_handover']
    target_bot_type = pending['to_bot_type']
    expanded_query = pending['expanded_query']
    
    # Get context from the current bot about the conversation so far
    current_bot = chat_session['current_bot']
    handover_context = current_bot.prepare_handover_context()
    
    # Switch to the target bot
    new_bot = chatbot_map[target_bot_type]
    new_bot_type = target_bot_type
    
    # Clean up the handover flag since we've processed it
    del chat_session['pending_handover']
    
    return new_bot, new_bot_type, expanded_query, handover_context


# ============================================================================
# RUN APPLICATION - Start the web server
# ============================================================================

if __name__ == '__main__':
    # Create necessary directories if they don't exist
    # These directories store conversations and temporary session data
    Path('storage/conversation_logs').mkdir(exist_ok=True, parents=True)
    Path('storage/flask_session').mkdir(exist_ok=True, parents=True)
    
    # Start the Flask server
    # - port=5000 is the network port where the app runs
    # - debug=True enables auto-reloading when code changes
    app.run(
        port=5000,
        debug=True 
    )
