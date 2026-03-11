/*
==============================================================================
CHAT.JS - Chat Interface Controller
==============================================================================

This file manages all interactions in the chat interface. It handles:
- Initializing the chat when the page loads
- Sending user messages and receiving bot responses
- Managing handovers between different chatbots
- Ending conversations and saving logs
- Preventing users from accidentally leaving mid-conversation


==============================================================================
*/

/* ============================================================================
   1. DOM REFERENCES - Getting HTML elements
   ============================================================================
   These variables hold references to the HTML elements
   */

// Main chat areas
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const endConversationButton = document.getElementById('endConversationButton');
const loadingIndicator = document.getElementById('loadingIndicator');

// Modal dialogs (popups)
const endModal = document.getElementById('endModal');
const confirmEndButton = document.getElementById('confirmEndButton');
const cancelEndButton = document.getElementById('cancelEndButton');
const leaveWarningModal = document.getElementById('leaveWarningModal');
const confirmLeaveButton = document.getElementById('confirmLeaveButton');
const cancelLeaveButton = document.getElementById('cancelLeaveButton');

/* ============================================================================
   2. STATE VARIABLES - Tracking what's happening
   ============================================================================
   These variables keep track of the current state of the conversation and UI.
   */

let isProcessing = false;              
let currentBotName = '';               
let currentBotDisplayName = '';        // Displayname also includes the VA role (e.g. "Jaimy (Study Adviser)")
let conversationEnded = false;         
let shouldShowLeaveWarning = true;     
let pendingNavigation = null;         
let hasHandoverOccurred = false;
let isWaitingForHandoverStart = false;


/* ============================================================================
   3. INITIALIZATION - Setting up chat on page load
   ============================================================================
   When the page first loads, initialize chat and set up all listeners.
   */

/**
 * Run when page finishes loading
 */
document.addEventListener('DOMContentLoaded', function() {
    history.pushState({ page: 'chat' }, '', ''); // Push initial state to enable back button interception
    
    initializeChat();
    setupEventListeners();
});

/**
 * Initialize chat by getting bot greeting and setting up the interface
 */
async function initializeChat() {
    try {
        // Call backend to initialize chat
        const response = await fetch('/api/init_chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to initialize chat');
        }
        
        const data = await response.json();
        currentBotName = data.bot_name;
        currentBotDisplayName = data.bot_display_name;
        
        // Update VA name in subheader
        const vaNameElement = document.querySelector('.va-subheader .va-name');
        if (vaNameElement) {
            vaNameElement.textContent = data.bot_display_name;
        }
        
        loadingIndicator.remove();
           
        // Delay before displaying first greeting to make it feel more natural
        const typingIndicator = showTypingIndicator();
        await new Promise(resolve => setTimeout(resolve, 4000));
        typingIndicator.remove();
        addMessage('bot', data.bot_name, data.greeting, data.bot_display_name);
        
        // Enable input
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        
    } catch (error) {
        console.error('Error initializing chat:', error);
        loadingIndicator.textContent = 'Error initializing chat. Please refresh the page.';
        loadingIndicator.style.color = '#dc3545';
    }
}


/* ============================================================================
   4. EVENT LISTENERS - Responding to user actions
   ============================================================================
   These listeners respond to user interactions: clicking buttons, typing,
   pressing keys, navigating away, etc.
   */

/**
 * Set up all event listeners for user interactions
 */
function setupEventListeners() {
    setupMessageSending();
    setupModalInteractions();
    setupPageNavigationWarnings();
}

/**
 * Message sending listeners
 * Responds to: send button clicks, Enter key, textarea resizing
 */
function setupMessageSending() {
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Shift+Enter
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea as user types (grows but max 120px)
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}

/**
 * Modal dialog listeners
 * Responds to: end conversation button, modal buttons, clicks outside modal
 */
function setupModalInteractions() {
    // -------- End conversation modal --------
    // Show modal when user clicks end button
    endConversationButton.addEventListener('click', function() {
        endModal.classList.add('active');
    });
    
    // Close modal on confirm or cancel
    confirmEndButton.addEventListener('click', endConversation);
    cancelEndButton.addEventListener('click', function() {
        endModal.classList.remove('active');
    });
    
    // Close modal if user clicks outside the dialog
    endModal.addEventListener('click', function(e) {
        if (e.target === endModal) {
            endModal.classList.remove('active');
        }
    });
    
    // -------- Leave warning modal --------
    // Close modal on confirm or cancel
    confirmLeaveButton.addEventListener('click', confirmLeave);
    cancelLeaveButton.addEventListener('click', function() {
        leaveWarningModal.classList.remove('active');
        pendingNavigation = null;
        // Re-push state to prevent back navigation
        history.pushState({ page: 'chat' }, '', '');
    });
    
    // Close modal if user clicks outside the dialog
    leaveWarningModal.addEventListener('click', function(e) {
        if (e.target === leaveWarningModal) {
            leaveWarningModal.classList.remove('active');
            pendingNavigation = null;
            // Re-push state to prevent back navigation
            history.pushState({ page: 'chat' }, '', '');
        }
    });
}

/**
 * Page navigation warning listeners
 * Prevents user from accidentally leaving mid-conversation
 */
function setupPageNavigationWarnings() {
    // Intercept back button navigation
    window.addEventListener('popstate', function(e) {
        if (!conversationEnded && shouldShowLeaveWarning) {
            // Show custom warning modal
            leaveWarningModal.classList.add('active');
            // Re-push the state so we can intercept again if user cancels
            history.pushState({ page: 'chat' }, '', '');
        }
    });
    
    // Warn user before closing tab or window
    window.addEventListener('beforeunload', function(e) {
        // Don't show warning if conversation has already ended
        if (conversationEnded || !shouldShowLeaveWarning) {
            return;
        }
        
        // Prevent page from unloading and trigger browser's built-in warning
        e.preventDefault();
        // Note: Custom messages are no longer supported in modern browsers
        // The browser will show its own generic warning message
    });
    
    // Clean up session when user actually closes the page/tab
    window.addEventListener('pagehide', function(e) {
        // Only clean up if conversation hasn't been properly ended AND if the page is being unloaded (not just navigating away)
        if (!conversationEnded && e.persisted === false) {
            navigator.sendBeacon('/api/cleanup_session_on_exit');
        }
    });
}

/* ============================================================================
   5. CHAT FUNCTIONS - Core functionality
   ============================================================================
   These functions handle sending messages, receiving responses, and 
   managing the conversation flow, including handovers.
   */

/**
 * Send user message to backend and receive response
 */
async function sendMessage() {
    const message = userInput.value.trim();
    
    // Don't send if empty or already processing
    if (!message || isProcessing) {
        return;
    }
    
    // Display user message immediately
    addMessage('user', 'You', message);
    
    // Clear input field
    userInput.value = '';
    userInput.style.height = 'auto';
    
    // Prevent sending multiple messages at once
    isProcessing = true;
    userInput.disabled = true;
    sendButton.disabled = true;
    
    // Show typing indicator while waiting for response
    const typingIndicator = showTypingIndicator();
    
    try {
        // Send message to backend
        const response = await fetch('/api/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });
        
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        typingIndicator.remove();
        
        // Handle handover if it occurred
        if (data.handover_occurred && data.handover_message) {
            await handleHandover(data, message);
        } else {
            // No handover - just display response normally
            currentBotName = data.bot_name;
            addMessage('bot', data.bot_name, data.response, data.bot_display_name);
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        typingIndicator.remove();
        addMessage('system', 'System', 'Sorry, there was an error processing your message. Please try again.');
    } finally {
        isProcessing = false;

        // Re-enable input unless we're waiting for explicit handover start
        if (!isWaitingForHandoverStart) {
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    }
}

/**
 * Handle handover between chatbots
 * Shows handover message, preloads the new bot response, and completes handover after user confirmation
 */
async function handleHandover(data, originalMessage) {
    // Delay displaying handover message to make it feel more natural
    const handoverTypingIndicator = showTypingIndicator();
    await new Promise(resolve => setTimeout(resolve, 4000));
    handoverTypingIndicator.remove();
    addMessage('bot', currentBotDisplayName, data.handover_message);

    // Lock chatting with current bot until user explicitly starts the handover
    isWaitingForHandoverStart = true;
    userInput.disabled = true;
    sendButton.disabled = true;
    
    // Update current bot name
    currentBotName = data.bot_name;
    currentBotDisplayName = data.bot_display_name;
    hasHandoverOccurred = true;
    
    // Prepare the new bot response in the background
    let followupData = null;
    let followupError = null;

    const followupPromise = (async function() {
        try {
            const followupResponse = await fetch('/api/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: originalMessage,
                    is_handover_followup: true
                })
            });

            if (!followupResponse.ok) {
                throw new Error('Failed to get followup response');
            }

            followupData = await followupResponse.json();
        } catch (error) {
            followupError = error;
        }
    })();

    // Show typing activity while waiting to display the handover-start action
    const preButtonTypingIndicator = showTypingIndicator();
    await new Promise(resolve => setTimeout(resolve, 9000));
    preButtonTypingIndicator.remove();

    const targetBotName = data.target_bot_name || 'The next assistant';
    await showHandoverStartButton(targetBotName);

    // If background generation is still running, show a waiting indicator until it's done
    const waitingIndicator = showTypingIndicator();
    await followupPromise;
    waitingIndicator.remove();

    if (followupError || !followupData) {
        console.error('Error getting followup response:', followupError);
        addMessage('system', 'System', 'Sorry, there was an error getting the response from the new assistant. Please try sending your message again.');
        isWaitingForHandoverStart = false;
        userInput.placeholder = 'Type your message here...';
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        return;
    }
    
    // Clear chat history if requested
    if (data.clear_messages) {
        clearMessages();
        
        // Update bot state and VA name after clearing
        currentBotName = followupData.bot_name;
        currentBotDisplayName = followupData.bot_display_name;
        updateHandoverTheme();
        const vaNameElement = document.querySelector('.va-subheader .va-name');
        if (vaNameElement) {
            vaNameElement.textContent = followupData.bot_display_name;
        }
    }
    
    // Show greeting message from new bot
    const greetingTypingIndicator = showTypingIndicator();
    await new Promise(resolve => setTimeout(resolve, 2500));
    greetingTypingIndicator.remove();
    addMessage('bot', followupData.bot_display_name, "Hello! I'm " + followupData.bot_name + ", the virtual " + followupData.bot_role + " for Creative Technology. I just received a summary of your conversation with " + data.bot_name + ".");
        
    // Delay before showing the response to make it feel more natural
    const responseTypingIndicator = showTypingIndicator();
    await new Promise(resolve => setTimeout(resolve, 6000));
    responseTypingIndicator.remove();
    addMessage('bot', followupData.bot_name, followupData.response, followupData.bot_display_name);

    // Unlock normal chatting after handover completes
    isWaitingForHandoverStart = false;
    userInput.placeholder = 'Type your message here...';
}

/**
 * Show an in-chat button that lets the user start chatting with the new bot.
 */
function showHandoverStartButton(targetBotName) {
    return new Promise(function(resolve) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';

        messageDiv.innerHTML = `
            <div class="message-bubble handover-action-bubble">
                <div>${escapeHtml(targetBotName)} is ready for you. Click here to start chatting: <button type="button" class="handover-start-button">Start chatting</button> </div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        const startButton = messageDiv.querySelector('.handover-start-button');
        startButton.addEventListener('click', function() {
            startButton.disabled = true;
            resolve();
        });
    });
}

/**
 * Clear all messages from the chat display
 * Used when switching between chatbots
 */
function clearMessages() {
    // Remove all child elements from chat messages area
    while (chatMessages.firstChild) {
        chatMessages.removeChild(chatMessages.firstChild);
    }
}

/* ============================================================================
   6. UI UTILITIES - Helper functions for display
   ============================================================================
   These functions handle the visual elements of the chat:
   messages, typing indicators, scrolling, text safety, etc.
   */

/**
 * Add a message to the chat display
 * Creates the HTML for a message bubble and adds it to the chat
 */
function addMessage(type, sender, text, displayName = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    // Get current time for message timestamp
    const timestamp = new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    // Use displayName for header if provided, otherwise use sender
    const headerName = displayName || sender;
    
    // Create message structure: header (name), bubble (text), timestamp
    messageDiv.innerHTML = `
        <div class="message-header">${headerName}</div>
        <div class="message-bubble">${escapeHtml(text)}</div>
        <div class="message-timestamp">${timestamp}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Show typing indicator animation
 * Returns the indicator element so it can be removed later
 */
function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    
    // Three dots that bounce
    indicator.innerHTML = ` 
        <span></span> 
        <span></span>
        <span></span>
    `;
    chatMessages.appendChild(indicator);
    scrollToBottom();
    return indicator;
}

/**
 * Scroll chat messages to the bottom
 * Used after adding new messages so the latest message is visible
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Escape HTML special characters to ensure safe display
 * Converts < > & " ' to safe HTML entities
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    // Also convert newlines to <br> tags for proper display
    return div.innerHTML.replace(/\n/g, '<br>');
}

/**
 * Apply handover theme when switching to Jaimy
 */
function updateHandoverTheme() {
    document.body.classList.toggle('handover-theme');
}

/* ============================================================================
   7. CONVERSATION MANAGEMENT - Ending chats and user leaving
   ============================================================================
   These functions handle when the user ends the conversation or
   tries to leave the page unexpectedly.
   */

/**
 * End conversation when user clicks "End Conversation"
 * Saves the conversation log and redirects to summary page
 */
async function endConversation() {
    // Close the confirmation modal
    endModal.classList.remove('active');
    
    // Disable input to prevent more messages
    userInput.disabled = true;
    sendButton.disabled = true;
    endConversationButton.disabled = true;
    
    try {
        // Send end conversation request to backend
        const response = await fetch('/api/end_conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to end conversation');
        }
        
        // Mark conversation as ended to prevent warnings
        conversationEnded = true;
        shouldShowLeaveWarning = false;
        
        // Show goodbye message
        addMessage('bot', currentBotDisplayName, 'Bye!');
        
        // Redirect to conversation ended page
        setTimeout(function() {
            window.location.href = '/conversation_ended';
        }, 1500);
        
    } catch (error) {
        console.error('Error ending conversation:', error);
        alert('There was an error saving your conversation. Please contact the researcher.');
    }
}

/**
 * Confirm user wants to leave the page without ending conversation
 * Used when back button is clicked or page is being closed
 */
async function confirmLeave() {
    // Close the warning modal
    leaveWarningModal.classList.remove('active');
    
    // Disable further warnings
    shouldShowLeaveWarning = false;
    conversationEnded = true;
    
    // Save and end the conversation
    try {
        await fetch('/api/cleanup_session_on_exit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    } catch (error) {
        console.error('Error cleaning up session:', error);
        // Continue navigation even if cleanup fails
    }
    
    // Navigate to login page
    window.location.href = '/login';
}
