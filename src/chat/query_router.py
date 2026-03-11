"""
Query router module for directing user queries to the appropriate chatbot.
Implements a QueryRouter class that uses keyword-based rules to determine the best-suited chatbot.

Currently only supports routing from Teacher to Study Adviser based on the presence of certain keywords in the user query.
"""
import re
from typing import Optional, Tuple

# Import ChatbotType from conditions to maintain single source of truth
from config.conditions import ChatbotType


class QueryRouter:

    def __init__(self):
        """
        Initialize the QueryRouter.
        """
        # Regex patterns that trigger handover from teacher to study adviser
        self.adviser_keywords = [
            # Time management & Motivation
            r"\b(?:time\s*-?\s*management|manag(?:e|ing)\s+time)\b",
            r"\b(?:overwhelm(?:ed|ing)?\s+with\s+(?:this\s+)?course)\b",
            r"\bmotivat(?:e|ed|ing|ion)\b",
            r"\b(piling\s+up)\b",
            r"\b(?:balance|balancing)\b",
            r"\bprocrastinat(?:e|ed|ing|ion)?\b",
            r"\b(?:work|study|heavy|over)[\s_-]*load(?:ed)?\b",
            r"\b(deadlines?|assignments?|due\s+dates?)\b",
            r"\b(not\s+enough\s+time|no\s+time|out\s+of\s+time)\b",
            r"\b(?:planning?|schedul(?:e|ed|ing)|prioriti[sz](?:e|ed|ing|ation)|organi[sz](?:e|ed|ing|ation))\b",
            r"\b(?:need\s+help|help(?:\s+me)?)(?:\s+with\s+(?:time\s*-?\s*management|planning|work\s*load|study\s+load|prioriti[sz]ing|procrastination))?\b",
            r"\b(catch\s+up)\b",

            # Emotional/Mental health
            r"\b(?:burn\s*out|burning\s+out)\b",
            r"\bstress(?:ed|ing|or|ful)?\b",
            r"\banx(?:iety|ious|ieties)\b",
            r"\bpanic(?:king|ked)?\b",
            r"\bdepress(?:ion|ed|ing|ive)?\b",
            r"\bsad(?:ness)?\b",
            r"\bfrustrat(?:ed|ing|ion)\b",
            r"\boverwhelm(?:ed|ing)?\b",
            r"\b(?:(?:mental|emotional)\s+health|well-?being)\b",
            r"\bpressur(?:e|ed|ing)\b",
            r"\b(?:can(?:'|\s+)?t\s+keep\s+up|cannot\s+keep\s+up|(?:fall(?:ing)?|get(?:ting)?)\s+behind|behind\s+schedule)(?:\s+on\s+(?:my\s+)?(?:work|coursework|assignments?))?\b",
            r"\b(?:cope|coping(?:\s+mechanism)?)\b",

            # Social
            r"\blonel(?:y|iness)\b",
            r"\bisolat(?:e|ed|ing|ion)?\b",

            # Sleep issues
            r"\b(?:sleep|tired|exhausted|sleep\s+depriv(?:ation|ed))\b",

            # Accessibility/Disability
            r"\b(?:adhd|autis(?:m|tic)|dyslexia|disability|accessibility)\b",

            # Focus/Concentration
            r"\bconcentrat(?:e|ing|ion)\b",
            r"\bfocus(?:ed|ing)?\b",

            # Support services
            r"\b(?:counsel(?:or|ing)|counsell(?:or|ing)|therap(?:ist|y)|psychologist)\b",

            # General concerns/worries
            r"\bconcern(?:ed)?\b",
            r"\bworr(?:y|ied|ies|ying)\b",
            r"\bpersonal\s+(?:issues|matters)\b",
            r"\bstruggl(?:e|ing)\s+(?:with\s+)?(?:stress|time|planning|work\s*load|study\s+load|procrastination)\b",
            r"\bdifficulty\s+(?:with\s+)?(?:time|planning|work\s*load|study\s+load|procrastination)\b",

            # Academic/Career
            r"\b(career|job|internship|graduation|graduate)\b",
            r"\b(study\s+plan|course\s+selection|academic\s+advice)\b",

            # Financial
            r"\b(financial\s+aid|scholarship|finances|money)\b",

        ]

    def get_triggered_keyword(self, query_lower: str) -> Optional[str]:
        """
        Get the exact word/phrase that triggered handover in the query.

        Args:
            query_lower: The user query in lowercase.

        Returns:
            The exact matched word/phrase from the query, or None if none found.
        """
        for pattern in self.adviser_keywords:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(0)  # Return the actual matched text
        return None

    def handover_from_teacher_to_adviser_needed(self, query_lower: str) -> bool:
        """
        Determine if a handover from Teacher to Study Adviser is needed based on the query content.

        Args:
            query_lower: The user query in lowercase.
            
        Returns:
            bool: True if handover is needed, False otherwise.
        """
        return any(re.search(pattern, query_lower, re.IGNORECASE) for pattern in self.adviser_keywords)

    def route_query(self, query: str, current_bot: ChatbotType) -> Tuple[ChatbotType, bool]:
        """Route the query to the appropriate chatbot based on content.

        Args:
            query (str): The user query.
            current_bot (ChatbotType): The current chatbot handling the conversation.
        Returns:
            Tuple[ChatbotType, bool]: The selected chatbot type and a flag indicating if a switch is needed.
        """
        query_lower = query.lower()

        # Routing logic based on current chatbot and query content
        # Change based on scenario and condition configuration

        # Scenario: Teacher detects more general problems/questions --> handover to Study Adviser
        if current_bot == ChatbotType.TEACHER:
            if self.handover_from_teacher_to_adviser_needed(query_lower):
                return ChatbotType.STUDY_ADVISER, True
            else:
                # No handover needed
                return current_bot, False
        else:
            # Not teacher, no handover
            return current_bot, False
        
