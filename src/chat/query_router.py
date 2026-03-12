"""
Query router module for directing user queries to the appropriate chatbot.

The QueryRouter class holds a list of routing rules. Each rule defines which chatbot
is currently active, which detection method to use, and which chatbot to switch to
when the rule triggers. route_query() works through the list until a rule matches;
if none match, the current chatbot keeps the conversation.

Currently the only detection method is 'keyword' (regex-based keyword matching), but
the router is designed so that new methods can be added without restructuring existing
code. To add a new detection method:

    1. Add a new branch in _check_rule_match() that handles your method name
    2. Create routing rules that set 'method' to that name and include whatever
       fields the new method needs

See the routing_rules list in __init__ for an example of how rules are structured.
"""
import re
from typing import Optional, Tuple

# Import ChatbotType from conditions to maintain single source of truth
from config.conditions import ChatbotType


class QueryRouter:

    def __init__(self):
        # ---- Add or edit routing rules here ----
        #
        # Each rule is a dictionary with at least these three fields:
        #   'from_bot' — the chatbot that must currently be active for this rule to apply
        #   'to_bot'   — the chatbot to hand over to when the rule triggers
        #   'method'   — the detection method used to decide whether the rule triggers
        #
        # The remaining fields depend on the chosen method:
        #
        #   method 'keyword':
        #       'keywords' — a list of regex patterns; if any one of them matches
        #                    the user's message, the rule triggers
        #
        # To add a new routing rule, copy the block below and adjust the values.
        # To add a new keyword to an existing rule, append a pattern to its 'keywords' list.
        # To use a completely different detection method, see the docstring of
        # _check_rule_match() for instructions.
        self.routing_rules = [
            {
                'from_bot': ChatbotType.TEACHER,
                'to_bot':   ChatbotType.STUDY_ADVISER,
                'method':   'keyword',
                'keywords': [
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
            }
        ]

    # ---- Detection method handlers ----

    def _check_rule_match(self, rule: dict, query_lower: str) -> bool:
        """
        Check whether a single routing rule matches the query.
        
        This method dispatches to the appropriate detection logic based on the
        rule's 'method' field. To add a new detection method:
        
            1. Choose a name for the method (e.g. 'sentiment')
            2. Add an `elif method == 'sentiment':` branch below
            3. Implement the detection logic, reading any extra fields you need
               from the rule dict (e.g. rule['threshold'])
            4. Create routing rules in __init__ that set 'method' to your new name
               and include the fields your handler expects
        
        Args:
            rule:        A single routing rule dictionary.
            query_lower: The user query in lowercase.
        
        Returns:
            True if the rule's detection method matched, False otherwise.
        """
        method = rule.get('method', 'keyword')

        if method == 'keyword':
            return any(
                re.search(pattern, query_lower, re.IGNORECASE)
                for pattern in rule['keywords']
            )

        # Add new detection methods here. For example:
        #
        # elif method == 'sentiment':
        #     return analyze_sentiment(query_lower) >= rule['threshold']

        return False

    # ---- Public interface ----

    def get_triggered_keyword(self, query_lower: str) -> Optional[str]:
        """
        Return the first keyword that matches the query across all keyword-type
        routing rules, or None if no keyword matches.

        This is used both to identify what triggered a handover (for logging) and
        to detect that a handover-relevant topic was mentioned even in conditions
        where routing is disabled (to start the session ending countdown).

        Only inspects rules whose method is 'keyword'; other rule types are skipped.

        Args:
            query_lower: The user query in lowercase.

        Returns:
            The exact matched word/phrase from the query, or None if none found.
        """
        for rule in self.routing_rules:
            if rule.get('method', 'keyword') != 'keyword':
                continue
            for pattern in rule['keywords']:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    return match.group(0)
        return None

    def route_query(self, query: str, current_bot: ChatbotType) -> Tuple[ChatbotType, bool]:
        """
        Determine which chatbot should handle the query based on the routing rules.

        Works through the routing_rules list in order. The first rule whose
        'from_bot' matches the current bot AND whose detection method matches the
        query determines the target chatbot. If no rule matches, the current
        chatbot keeps the conversation.

        Args:
            query:       The user query (will be lowercased internally).
            current_bot: The chatbot currently handling the conversation.

        Returns:
            A tuple of (target_chatbot_type, switch_needed).
            switch_needed is True only when a rule matched and the target differs
            from the current bot.
        """
        query_lower = query.lower()

        for rule in self.routing_rules:
            if current_bot != rule['from_bot']:
                continue

            if self._check_rule_match(rule, query_lower):
                return rule['to_bot'], True

        # No rule matched — keep the current chatbot
        return current_bot, False


