"""
Tunable settings, including parameters for database creation, retrieval, conversation behavior, and response validation.
"""

# --- DATABASE CREATION SETTINGS --- #
# Target chunk size when creating chunks
MAX_CHARS: int = 2500 
MIN_CHARS: int = 1250  

# --- RETRIEVAL SETTINGS --- #
CHUNKS_INCLUDED_IN_CONTEXT: int = 2  # Number of top relevant chunks to include in context
RELEVANCE_THRESHOLD: float = 1.1  # Minimum relevance score for at least one chunk for the retriever to retrieve chunks. Note: Lower scores are more relevant, so this is a maximum threshold.

# --- CONVERSATION BEHAVIOR --- #
MIN_TURNS_BEFORE_HANDOVER = 0  # Require this many turns before a bot handover is allowed
ENABLE_RESPONSE_SUMMARIZATION = False  # Keep response validator available but disabled by default

# --- RESPONSE VALIDATION --- #
RESPONSE_SENTENCE_LIMIT = 10  # Maximum sentences before triggering summarization
MARKDOWN_HEADER_PATTERN = r'(?:^|\s)(?:#{2,}|\*{2,})'  # Regex pattern to detect markdown headers (##) or bold (**); kept for potential future use in response validation
