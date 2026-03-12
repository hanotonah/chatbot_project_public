"""
Runtime wiring for models and middleware.
Edit the model selections below to customize which LLMS to use.
"""

from langchain_ollama import OllamaEmbeddings, ChatOllama

# ============================================================================
# MODEL SELECTION
# ============================================================================
# These can be swapped with models you have downloaded locally.
# To use a different model, set the CURRENT version of that model to the new one.

EMBEDDINGS_MODEL = OllamaEmbeddings(model="qwen3-embedding:8b")

CHAT_MODEL_QWEN_1_7 = ChatOllama(model="qwen3:1.7b")
CHAT_MODEL_QWEN_4 = ChatOllama(model="qwen3:4b")
CHAT_MODEL_QWEN_8 = ChatOllama(model="qwen3:8b")
CHAT_MODEL_LLAMA_8 = ChatOllama(model="llama3.1:8b")

SUMMARIZATION_MODEL = ChatOllama(model="mistral:7b")

# CURRENT MODELS - edit these to change which models are used in the application
CURRENT_EMBEDDINGS_MODEL = EMBEDDINGS_MODEL
CURRENT_CHAT_MODEL = CHAT_MODEL_LLAMA_8
CURRENT_SUMMARIZATION_MODEL = SUMMARIZATION_MODEL
# ============================================================================

def build_default_middleware() -> list:
    """Return the default middleware stack used by all bots."""

    return []

    # If you want to add Langchain's SummarizationMiddleware to automatically summarize long conversation history, here is an example:
    # from langchain.agents.middleware import SummarizationMiddleware
    # return [
    #     # Summarize the conversation history when it exceeds a certain amount of tokens while keeping most recent messages
    #     SummarizationMiddleware(
    #         model=CURRENT_SUMMARIZATION_MODEL,
    #         trigger=("tokens", 4000),
    #         keep=("messages", 6)
    #     )
    # ]
