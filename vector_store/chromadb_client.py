"""
ChromaDB Client for Conv-AI Project
Handles semantic search and vector storage for query patterns and business data.
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """
    Wrapper for ChromaDB operations with persistent storage.

    Features:
    - Persistent storage in database/chroma/
    - Auto-embedding using sentence-transformers
    - Multiple collections for different data types
    - Semantic similarity search
    """

    def __init__(self, persist_directory: str = "database/chroma"):
        """
        Initialize ChromaDB client with persistent storage.

        Args:
            persist_directory: Path to store ChromaDB data (default: database/chroma/)
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Use sentence-transformers for embedding
        # all-MiniLM-L6-v2: 384 dimensions, fast, accurate (86% similarity accuracy)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        logger.info(f"ChromaDB initialized with persistent storage at: {self.persist_directory}")

    def create_collection(self, name: str, overwrite: bool = False) -> chromadb.Collection:
        """
        Create or get a collection.

        Args:
            name: Collection name
            overwrite: If True, delete existing collection and create new one

        Returns:
            ChromaDB Collection object
        """
        if overwrite:
            try:
                self.client.delete_collection(name=name)
                logger.info(f"Deleted existing collection: {name}")
            except Exception as e:
                logger.debug(f"Collection {name} does not exist: {e}")

        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_function,
            metadata={"description": f"Collection for {name}"}
        )

        logger.info(f"Collection '{name}' ready (count: {collection.count()})")
        return collection

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """
        Add documents to a collection with auto-embedding.

        Args:
            collection_name: Name of the collection
            documents: List of text documents to embed
            metadatas: Optional list of metadata dicts (same length as documents)
            ids: Optional list of IDs (auto-generated if not provided)

        Returns:
            Dict with status and count of documents added
        """
        collection = self.create_collection(collection_name)

        # Auto-generate IDs if not provided
        if ids is None:
            start_id = collection.count()
            ids = [f"{collection_name}_{i}" for i in range(start_id, start_id + len(documents))]

        # Add documents (embeddings are generated automatically)
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        count = collection.count()
        logger.info(f"Added {len(documents)} documents to '{collection_name}'. Total: {count}")

        return {"status": "success", "added": len(documents), "total": count}

    def query_similar(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query for similar documents using semantic search.

        Args:
            collection_name: Name of the collection to search
            query_text: Query text to find similar documents
            n_results: Number of results to return (default: 5)
            where: Optional metadata filter (e.g., {"source": "duckdb"})

        Returns:
            Dict with results:
            {
                "ids": List[List[str]],
                "documents": List[List[str]],
                "metadatas": List[List[Dict]],
                "distances": List[List[float]]
            }
        """
        collection = self.client.get_collection(
            name=collection_name,
            embedding_function=self.embedding_function
        )

        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )

        logger.info(f"Query '{query_text}' returned {len(results['ids'][0])} results from '{collection_name}'")
        return results

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dict with collection statistics
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            return {
                "name": collection_name,
                "count": collection.count(),
                "metadata": collection.metadata
            }
        except Exception as e:
            logger.error(f"Error getting stats for collection '{collection_name}': {e}")
            return {"name": collection_name, "count": 0, "error": str(e)}

    def list_collections(self) -> List[str]:
        """
        List all available collections.

        Returns:
            List of collection names
        """
        collections = self.client.list_collections()
        names = [col.name for col in collections]
        logger.info(f"Available collections: {names}")
        return names

    def delete_collection(self, collection_name: str) -> Dict[str, str]:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            Dict with status
        """
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return {"status": "success", "message": f"Collection '{collection_name}' deleted"}
        except Exception as e:
            logger.error(f"Error deleting collection '{collection_name}': {e}")
            return {"status": "error", "message": str(e)}

    def peek_collection(self, collection_name: str, limit: int = 5) -> Dict[str, Any]:
        """
        Peek at a few documents in a collection.

        Args:
            collection_name: Name of the collection
            limit: Number of documents to peek (default: 5)

        Returns:
            Dict with sample documents
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            peek_data = collection.peek(limit=limit)
            return {
                "name": collection_name,
                "count": collection.count(),
                "sample": peek_data
            }
        except Exception as e:
            logger.error(f"Error peeking collection '{collection_name}': {e}")
            return {"name": collection_name, "error": str(e)}


# Singleton instance
_chroma_client: Optional[ChromaDBClient] = None


def get_chroma_client(persist_directory: str = "database/chroma") -> ChromaDBClient:
    """
    Get or create singleton ChromaDB client instance.

    Args:
        persist_directory: Path to store ChromaDB data

    Returns:
        ChromaDBClient instance
    """
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaDBClient(persist_directory=persist_directory)
    return _chroma_client


if __name__ == "__main__":
    # Test the ChromaDB client
    logging.basicConfig(level=logging.INFO)

    print("=== Testing ChromaDB Client ===\n")

    # Initialize client
    client = get_chroma_client()

    # Create test collection
    print("1. Creating test collection...")
    result = client.add_documents(
        collection_name="test_queries",
        documents=[
            "Show top 5 brands by sales",
            "Display revenue by state",
            "What are the declining brands?",
            "Show inventory levels by product"
        ],
        metadatas=[
            {"intent": "RANKING", "metric": "sales"},
            {"intent": "SNAPSHOT", "metric": "revenue"},
            {"intent": "TREND", "metric": "sales"},
            {"intent": "SNAPSHOT", "metric": "inventory"}
        ]
    )
    print(f"Result: {result}\n")

    # Test semantic search
    print("2. Testing semantic search...")
    query = "Which brands are performing best?"
    results = client.query_similar("test_queries", query, n_results=3)

    print(f"Query: '{query}'")
    print("Similar queries found:")
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    ), 1):
        print(f"  {i}. {doc}")
        print(f"     Metadata: {metadata}")
        print(f"     Distance: {distance:.4f}\n")

    # List collections
    print("3. Listing collections...")
    collections = client.list_collections()
    print(f"Collections: {collections}\n")

    # Get stats
    print("4. Collection stats...")
    stats = client.get_collection_stats("test_queries")
    print(f"Stats: {stats}\n")

    print("=== Test Complete ===")
