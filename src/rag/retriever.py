"""
Retriever module for fetching relevant chunks from a Chroma vector database.
Uses Langchain's Chroma integration to connect to the database and perform similarity searches.
"""

from typing import List
from langchain_chroma import Chroma


class ChromaRetriever:
    """
    Retriever class for fetching relevant chunks from a Chroma vector database.
    Uses Langchain's Chroma integration to connect to the database and perform similarity searches.
    """
    
    def __init__(self, db_path: str, embeddings_model):
        """
        Initialize the Chroma retriever with the database path and embeddings model.

        Args:
            db_path: Path to the Chroma vector database
            embeddings_model: Embeddings model used for similarity search
        """
        # Connect to the existing Chroma database
        self.db = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings_model
        )
    
    def retrieve(self, query: str, num_chunks: int, score_threshold: float) -> List[tuple]:
        """
        Retrieve relevant chunks from the Chroma database based on the query.

        Args:
            query: The user's query string
            num_chunks: Number of top relevant chunks to retrieve
            score_threshold: Maximum relevance score threshold for filtering chunks

        Returns:
            List of retrieved chunks as (Document, score) tuples
        """

        # Langchain's built-in similarity search with relevance scores
        all_docs = self.db.similarity_search_with_score( # Note: Lower scores are more relevant
            query=query,
            k=num_chunks
        )
        
        # Manually filter by relevance score threshold
        filtered_docs = [
            (doc, score) for doc, score in all_docs
            if score <= score_threshold
        ]
        
        return filtered_docs if filtered_docs else []
