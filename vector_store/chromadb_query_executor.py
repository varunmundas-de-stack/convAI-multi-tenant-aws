"""
ChromaDB Query Executor for Conv-AI Project
Handles semantic queries on ChromaDB with result formatting similar to DuckDB.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from typing import List, Dict, Any, Optional
from vector_store.chromadb_client import get_chroma_client
import json

logger = logging.getLogger(__name__)


class ChromaDBQueryExecutor:
    """
    Execute semantic queries on ChromaDB and format results.

    Provides similar interface to DuckDB QueryExecutor for consistency.
    """

    def __init__(self):
        """Initialize ChromaDB query executor."""
        self.client = get_chroma_client()
        logger.info("ChromaDB Query Executor initialized")

    def execute_semantic_query(
        self,
        question: str,
        n_results: int = 10,
        collection_filter: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a semantic search query across ChromaDB collections.

        Args:
            question: Natural language question
            n_results: Number of results to return (default: 10)
            collection_filter: Optional collection name to search (searches all if None)
            metadata_filter: Optional metadata filter (e.g., {"table": "dim_product"})

        Returns:
            Dict with query results:
            {
                "success": bool,
                "results": List[Dict],
                "count": int,
                "query": str,
                "execution_time_ms": float
            }
        """
        import time
        start_time = time.time()

        try:
            # Determine which collections to search
            if collection_filter:
                collections_to_search = [collection_filter]
            else:
                # Search all duckdb collections
                all_collections = self.client.list_collections()
                collections_to_search = [c for c in all_collections if c.startswith('duckdb_')]

            logger.info(f"Searching collections: {collections_to_search}")

            # Aggregate results from all collections
            all_results = []

            for collection_name in collections_to_search:
                try:
                    results = self.client.query_similar(
                        collection_name=collection_name,
                        query_text=question,
                        n_results=n_results,
                        where=metadata_filter
                    )

                    # Process results
                    for i, (doc_id, document, metadata, distance) in enumerate(zip(
                        results['ids'][0],
                        results['documents'][0],
                        results['metadatas'][0],
                        results['distances'][0]
                    )):
                        result_row = {
                            "id": doc_id,
                            "document": document,
                            "collection": collection_name,
                            "similarity_score": 1 / (1 + distance),  # Convert distance to similarity (0-1)
                            "distance": distance,
                            **metadata  # Include all metadata fields
                        }
                        all_results.append(result_row)

                except Exception as e:
                    logger.warning(f"Error searching collection '{collection_name}': {e}")

            # Sort by similarity score (highest first)
            all_results.sort(key=lambda x: x['similarity_score'], reverse=True)

            # Limit to n_results
            all_results = all_results[:n_results]

            execution_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "results": all_results,
                "count": len(all_results),
                "query": question,
                "collections_searched": collections_to_search,
                "execution_time_ms": round(execution_time, 2)
            }

        except Exception as e:
            logger.error(f"Error executing semantic query: {e}")
            execution_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": str(e),
                "query": question,
                "execution_time_ms": round(execution_time, 2)
            }

    def execute_table_query(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Query a specific table (collection) with optional filters.

        Args:
            table_name: Table name (e.g., "dim_product")
            filters: Metadata filters (e.g., {"category_name": "Noodles"})
            limit: Max results

        Returns:
            Query results dict
        """
        collection_name = f"duckdb_{table_name}"

        # Use a generic query to get all results, then filter by metadata
        generic_query = f"Show me data from {table_name}"

        return self.execute_semantic_query(
            question=generic_query,
            n_results=limit,
            collection_filter=collection_name,
            metadata_filter=filters
        )

    def get_similar_queries(
        self,
        question: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar past queries from the query patterns collection.

        Args:
            question: User's question
            n_results: Number of similar queries to return

        Returns:
            List of similar queries with metadata
        """
        try:
            results = self.client.query_similar(
                collection_name="test_queries",  # Update to actual query patterns collection
                query_text=question,
                n_results=n_results
            )

            similar_queries = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ), 1):
                similar_queries.append({
                    "rank": i,
                    "query": doc,
                    "similarity": 1 / (1 + distance),
                    "distance": distance,
                    "metadata": metadata
                })

            return similar_queries

        except Exception as e:
            logger.error(f"Error finding similar queries: {e}")
            return []

    def format_results_as_table(self, results: List[Dict[str, Any]]) -> str:
        """
        Format results as an HTML table (similar to DuckDB results).

        Args:
            results: List of result dictionaries

        Returns:
            HTML table string
        """
        if not results:
            return "<p>No results found.</p>"

        # Get all unique keys across all results
        all_keys = set()
        for result in results:
            all_keys.update(result.keys())

        # Remove internal fields
        display_keys = [k for k in all_keys if k not in ['id', 'source']]

        # Build HTML table
        html = '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">'

        # Header
        html += '<thead><tr style="background-color: #f0f0f0;">'
        for key in display_keys:
            html += f'<th>{key.replace("_", " ").title()}</th>'
        html += '</tr></thead>'

        # Body
        html += '<tbody>'
        for result in results:
            html += '<tr>'
            for key in display_keys:
                value = result.get(key, '')
                # Format floats
                if isinstance(value, float):
                    value = f"{value:.4f}"
                html += f'<td>{value}</td>'
            html += '</tr>'
        html += '</tbody>'

        html += '</table>'
        return html

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about available collections."""
        collections = self.client.list_collections()

        info = {
            "total_collections": len(collections),
            "collections": []
        }

        for col_name in collections:
            stats = self.client.get_collection_stats(col_name)
            info["collections"].append(stats)

        return info


# Singleton instance
_executor: Optional[ChromaDBQueryExecutor] = None


def get_chromadb_executor() -> ChromaDBQueryExecutor:
    """
    Get or create singleton ChromaDB query executor.

    Returns:
        ChromaDBQueryExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = ChromaDBQueryExecutor()
    return _executor


if __name__ == "__main__":
    # Test the query executor
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("ChromaDB Query Executor Test")
    print("=" * 60 + "\n")

    executor = get_chromadb_executor()

    # Test 1: Semantic search
    print("1. Testing semantic search...")
    print("Query: 'Show me Maggi products'\n")

    results = executor.execute_semantic_query(
        question="Show me Maggi products",
        n_results=5
    )

    if results['success']:
        print(f"Found {results['count']} results in {results['execution_time_ms']}ms")
        print(f"Collections searched: {results['collections_searched']}\n")

        for i, result in enumerate(results['results'][:3], 1):
            print(f"{i}. Similarity: {result['similarity_score']:.4f}")
            print(f"   Collection: {result['collection']}")
            print(f"   Document: {result['document'][:100]}...")
            print()
    else:
        print(f"Error: {results.get('error')}")

    # Test 2: Table query
    print("\n2. Testing table query...")
    print("Table: dim_product\n")

    table_results = executor.execute_table_query(
        table_name="dim_product",
        limit=5
    )

    if table_results['success']:
        print(f"Found {table_results['count']} results")
        print(executor.format_results_as_table(table_results['results'][:3]))

    # Test 3: Similar queries
    print("\n3. Testing similar query search...")
    print("Query: 'Which brands are doing well?'\n")

    similar = executor.get_similar_queries(
        question="Which brands are doing well?",
        n_results=3
    )

    for query in similar:
        print(f"{query['rank']}. {query['query']}")
        print(f"   Similarity: {query['similarity']:.4f}")
        print(f"   Metadata: {query['metadata']}\n")

    # Test 4: Collection info
    print("\n4. Collection information...")
    info = executor.get_collection_info()
    print(f"Total collections: {info['total_collections']}")
    for col in info['collections']:
        print(f"  - {col['name']}: {col['count']} documents")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60 + "\n")
