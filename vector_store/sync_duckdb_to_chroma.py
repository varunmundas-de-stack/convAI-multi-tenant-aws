"""
Sync DuckDB data to ChromaDB for semantic search capabilities.

This script:
1. Reads all fact and dimension tables from DuckDB
2. Converts rows to text documents
3. Embeds and stores them in ChromaDB
4. Preserves metadata (table, columns, keys)

Goal: Enable semantic search on business data while maintaining
      ability to return identical results to DuckDB queries.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import duckdb
import logging
from typing import List, Dict, Any
from vector_store.chromadb_client import get_chroma_client
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DuckDBToChromaSync:
    """Synchronize DuckDB data to ChromaDB for semantic search."""

    def __init__(self, duckdb_path: str = "database/cpg_olap.duckdb"):
        """
        Initialize sync manager.

        Args:
            duckdb_path: Path to DuckDB database file
        """
        self.duckdb_path = Path(duckdb_path)
        if not self.duckdb_path.exists():
            raise FileNotFoundError(f"DuckDB database not found: {duckdb_path}")

        self.conn = duckdb.connect(str(self.duckdb_path), read_only=True)
        self.chroma_client = get_chroma_client()

        logger.info(f"Connected to DuckDB: {duckdb_path}")

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in DuckDB."""
        query = "SHOW TABLES"
        result = self.conn.execute(query).fetchall()
        tables = [row[0] for row in result]
        logger.info(f"Found {len(tables)} tables: {tables}")
        return tables

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Get schema information for a table."""
        query = f"DESCRIBE {table_name}"
        result = self.conn.execute(query).fetchall()
        schema = [
            {"column_name": row[0], "column_type": row[1]}
            for row in result
        ]
        return schema

    def get_table_data(self, table_name: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get all data from a table as list of dicts.

        Args:
            table_name: Name of the table
            limit: Optional limit on number of rows

        Returns:
            List of row dictionaries
        """
        query = f"SELECT * FROM {table_name}"
        if limit:
            query += f" LIMIT {limit}"

        result = self.conn.execute(query).fetchdf()
        return result.to_dict('records')

    def row_to_document(self, row: Dict[str, Any], table_name: str, schema: List[Dict[str, str]]) -> str:
        """
        Convert a database row to a text document for embedding.

        Format: Natural language description of the row with key-value pairs.

        Example:
        "Product: Maggi Noodles, Brand: Maggi, Category: Noodles,
         Pack Size: 250g, MRP: 50.0, Status: Active"

        Args:
            row: Row dictionary
            table_name: Name of the source table
            schema: Table schema information

        Returns:
            Text document representing the row
        """
        # Create natural language representation
        parts = []

        for col_info in schema:
            col_name = col_info['column_name']
            value = row.get(col_name)

            if value is not None:
                # Format column name (remove underscores, title case)
                display_name = col_name.replace('_', ' ').title()
                parts.append(f"{display_name}: {value}")

        # Join all parts
        document = ", ".join(parts)

        # Add table context at the beginning
        document = f"[{table_name}] {document}"

        return document

    def sync_table_to_chroma(self, table_name: str, collection_name: str = None, limit: int = None) -> Dict[str, int]:
        """
        Sync a single table from DuckDB to ChromaDB.

        Args:
            table_name: Name of the DuckDB table
            collection_name: Optional ChromaDB collection name (defaults to table_name)
            limit: Optional limit on number of rows to sync

        Returns:
            Dict with sync statistics
        """
        if collection_name is None:
            collection_name = f"duckdb_{table_name}"

        logger.info(f"Syncing table '{table_name}' to collection '{collection_name}'...")

        # Get schema and data
        schema = self.get_table_schema(table_name)
        rows = self.get_table_data(table_name, limit=limit)

        if not rows:
            logger.warning(f"Table '{table_name}' is empty. Skipping.")
            return {"status": "skipped", "reason": "empty_table"}

        logger.info(f"Converting {len(rows)} rows to documents...")

        # Convert rows to documents
        documents = []
        metadatas = []
        ids = []

        for i, row in enumerate(tqdm(rows, desc=f"Processing {table_name}")):
            # Create document text
            doc_text = self.row_to_document(row, table_name, schema)
            documents.append(doc_text)

            # Create metadata (preserve original data structure)
            metadata = {
                "source": "duckdb",
                "table": table_name,
                **{k: str(v) if v is not None else "" for k, v in row.items()}
            }
            metadatas.append(metadata)

            # Create unique ID
            ids.append(f"{table_name}_{i}")

        # Add to ChromaDB (in batches to avoid memory issues)
        batch_size = 100
        total_added = 0

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            result = self.chroma_client.add_documents(
                collection_name=collection_name,
                documents=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids
            )
            total_added += result['added']

        logger.info(f"✓ Synced {total_added} rows from '{table_name}' to ChromaDB")

        return {
            "status": "success",
            "table": table_name,
            "collection": collection_name,
            "rows_synced": total_added
        }

    def sync_all_tables(self, limit_per_table: int = None) -> List[Dict[str, Any]]:
        """
        Sync all tables from DuckDB to ChromaDB.

        Args:
            limit_per_table: Optional limit on rows per table

        Returns:
            List of sync results for each table
        """
        tables = self.get_all_tables()
        results = []

        logger.info(f"Starting sync of {len(tables)} tables...")

        for table_name in tables:
            try:
                result = self.sync_table_to_chroma(
                    table_name=table_name,
                    limit=limit_per_table
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error syncing table '{table_name}': {e}")
                results.append({
                    "status": "error",
                    "table": table_name,
                    "error": str(e)
                })

        return results

    def get_sync_summary(self) -> Dict[str, Any]:
        """Get summary of synced data in ChromaDB."""
        collections = self.chroma_client.list_collections()

        summary = {
            "total_collections": len(collections),
            "collections": []
        }

        for collection_name in collections:
            if collection_name.startswith("duckdb_"):
                stats = self.chroma_client.get_collection_stats(collection_name)
                summary["collections"].append(stats)

        return summary

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("DuckDB connection closed")


def main():
    """Main sync script."""
    print("\n" + "=" * 60)
    print("DuckDB to ChromaDB Sync Script")
    print("=" * 60 + "\n")

    # Initialize sync manager
    sync_manager = DuckDBToChromaSync()

    try:
        # Sync all tables (no limit for full sync, use limit for testing)
        print("Starting synchronization...\n")
        results = sync_manager.sync_all_tables(limit_per_table=None)  # Set to 100 for testing

        # Print results
        print("\n" + "=" * 60)
        print("Sync Results:")
        print("=" * 60 + "\n")

        for result in results:
            if result['status'] == 'success':
                print(f"✓ {result['table']}: {result['rows_synced']} rows synced")
            elif result['status'] == 'skipped':
                print(f"⊘ {result['table']}: {result['reason']}")
            else:
                print(f"✗ {result['table']}: {result.get('error', 'Unknown error')}")

        # Get summary
        print("\n" + "=" * 60)
        print("ChromaDB Summary:")
        print("=" * 60 + "\n")

        summary = sync_manager.get_sync_summary()
        print(f"Total collections: {summary['total_collections']}")
        print("\nCollections:")
        for col in summary['collections']:
            print(f"  - {col['name']}: {col['count']} documents")

        print("\n" + "=" * 60)
        print("Sync Complete!")
        print("=" * 60 + "\n")

    finally:
        sync_manager.close()


if __name__ == "__main__":
    main()
