"""
Study Condition Configuration

This module defines the different experimental conditions used in a study.
Each condition specifies which chatbots are available, which one starts the conversation,
and whether routing/handover between chatbots is enabled.

How to use this file:
1. Review the CONDITIONS dictionary to see all available study conditions
2. To add a new condition: create a new Condition object and add it to the CONDITIONS dict
"""

from enum import Enum


class ChatbotType(Enum):
    """Enumeration of available chatbots."""
    TEACHER = "teacher"
    STUDY_ADVISER = "study_adviser"
    GENERAL = "general"


class Condition:
    """
    Configuration for a study condition.
    
    A condition defines the chatbot behavior for a specific experimental setup.
    
    Attributes:
        name (str): Human-readable name for the condition
        description (str): Detailed description of what this condition does
        chatbots (list[ChatbotType]): List of chatbot types to initialize for this condition
        starting_bot (ChatbotType): Which chatbot should start the conversation
        enable_routing (bool): Whether to enable routing/handover between chatbots
    
    Example:
        condition = Condition(
            name='Teacher Only',
            description='Student only interacts with the teacher chatbot',
            chatbots=[ChatbotType.TEACHER],
            starting_bot=ChatbotType.TEACHER,
            enable_routing=False
        )
    """
    
    def __init__(self, name: str, description: str, chatbots: list, 
                 starting_bot: ChatbotType, enable_routing: bool):
        self.name = name
        self.description = description
        self.chatbots = chatbots
        self.starting_bot = starting_bot
        self.enable_routing = enable_routing
    
    def __repr__(self):
        return f"Condition(name='{self.name}', chatbots={[bot.value for bot in self.chatbots]}, starting_bot={self.starting_bot.value})"


# ============================================================================
# AVAILABLE CONDITIONS
# ============================================================================
# Define all possible study conditions here. Each condition is identified by
# a unique key (string) and contains a Condition object.
#
# To add a new condition:
# 1. Add a new entry to this dictionary with a unique key and Condition object with appropriate parameters
# 2. Ensure the required chatbot types exist in `src/chatbot_core/chatbots`
# 3. Make sure the routing logic in `src/chat/query_router.py` can handle the specified chatbots and routing behavior

CONDITIONS = {
    'teacher_to_adviser': Condition(
        name='Teacher with Handover to Study Adviser',
        description=("""Student starts conversation with the teacher chatbot.
        If the student mentions keyword related to personal issues (stress, anxiety, ADHD, etc.),
        the teacher hands over the conversation to the study adviser chatbot."""
        ),
        chatbots=[ChatbotType.TEACHER, ChatbotType.STUDY_ADVISER],
        starting_bot=ChatbotType.TEACHER,
        enable_routing=True
    ),
    
    'general': Condition(
        name='General Chatbot',
        description=("""Student interacts with a single general chatbot that has access to all data.
            The general chatbot can answer both course-related questions and provide
            study advice without any handover mechanism."""
        ),
        chatbots=[ChatbotType.GENERAL],
        starting_bot=ChatbotType.GENERAL,
        enable_routing=False
    ),
}


# ============================================================================
# STUDY CONFIGURATION
# ============================================================================

# STUDY_CONDITIONS: List of condition keys to include in the study
# Participants will be randomly assigned to one of these conditions.
# Must be valid keys from the CONDITIONS dictionary above.
#
# To configure your study:
# 1. List all conditions you want to include in the study
# 2. Participants will be randomly assigned to one of these at login
#
# Example for a 1-condition study (no randomization):
# STUDY_CONDITIONS = ['teacher_to_adviser']
#
# Example for a 3-condition study:
# STUDY_CONDITIONS = ['teacher_to_adviser', 'general', 'study_adviser_only']

STUDY_CONDITIONS = ['teacher_to_adviser', 'general']

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_condition_by_key(condition_key: str) -> Condition:
    """
    Get a specific condition by its key.
    
    Args:
        condition_key (str): The key of the condition to retrieve
    
    Returns:
        Condition: The requested condition object
    
    Raises:
        ValueError: If condition_key is not found in CONDITIONS dictionary
    """
    if condition_key not in CONDITIONS:
        raise ValueError(
            f"Invalid condition key: '{condition_key}'. "
            f"Must be one of: {list(CONDITIONS.keys())}"
        )
    return CONDITIONS[condition_key]


def list_all_conditions() -> dict:
    """
    Get a summary of all available conditions.
    
    Returns:
        dict: Dictionary mapping condition keys to their names and descriptions
    """
    return {
        key: {
            'name': condition.name,
            'description': condition.description
        }
        for key, condition in CONDITIONS.items()
    }
