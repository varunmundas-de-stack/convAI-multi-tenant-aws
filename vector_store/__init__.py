"""
Vector Store Module for Conv-AI Project
Provides ChromaDB integration for semantic search and vector storage.
"""

from .chromadb_client import ChromaDBClient, get_chroma_client

__all__ = ['ChromaDBClient', 'get_chroma_client']
