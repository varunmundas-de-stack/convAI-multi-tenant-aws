"""
Query Executor - Executes SQL queries against DuckDB or PostgreSQL
"""
import os
import duckdb
import threading
import time
import decimal
from typing import List, Dict, Any
from pathlib import Path
from semantic_layer.models import QueryResult

DB_ENGINE = os.getenv('DB_ENGINE', 'duckdb').lower()

# PostgreSQL connection pool — created lazily on first use
_pg_pool = None
_pg_pool_lock = threading.Lock()


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        with _pg_pool_lock:
            if _pg_pool is None:
                import psycopg2.pool as _pg_pool_mod
                _pg_pool = _pg_pool_mod.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    host=os.getenv('POSTGRES_HOST', 'postgres'),
                    port=int(os.getenv('POSTGRES_PORT', '5432')),
                    dbname=os.getenv('POSTGRES_DB', 'cpg_analytics'),
                    user=os.getenv('POSTGRES_USER', 'postgres'),
                    password=os.getenv('POSTGRES_PASSWORD', ''),
                )
    return _pg_pool


class QueryExecutor:
    """Execute SQL queries and return results"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._local = threading.local()  # one connection per thread — thread-safe

    def _get_conn(self):
        """Return (or lazily open) the per-thread DuckDB connection."""
        if DB_ENGINE == 'postgresql':
            return None  # PG path uses the pool directly in execute()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = duckdb.connect(str(self.db_path), read_only=True)
            self._local.conn = conn
        return conn

    # ── kept for backward-compat (context-manager usage) ──────────────────
    def connect(self):
        self._get_conn()

    def disconnect(self):
        conn = getattr(self._local, 'conn', None)
        if conn:
            conn.close()
            self._local.conn = None

    def execute(self, sql: str) -> QueryResult:
        """
        Execute SQL query and return results
        """
        start_time = time.time()

        try:
            if DB_ENGINE == 'postgresql':
                pool = _get_pg_pool()
                pg_conn = pool.getconn()
                try:
                    cur = pg_conn.cursor()
                    cur.execute(sql)
                    rows = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    cur.close()
                finally:
                    pool.putconn(pg_conn)
            else:
                result = self._get_conn().execute(sql)
                rows = result.fetchall()
                columns = [desc[0] for desc in result.description]

            # Convert to list of dicts, normalizing non-JSON-safe types
            data = []
            for row in rows:
                row_dict = {}
                for col, val in zip(columns, row):
                    if isinstance(val, decimal.Decimal):
                        val = float(val)
                    row_dict[col] = val
                data.append(row_dict)

            execution_time = (time.time() - start_time) * 1000  # ms

            return QueryResult(
                data=data,
                columns=columns,
                row_count=len(data),
                sql_query=sql,
                execution_time_ms=round(execution_time, 2)
            )

        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}\nSQL: {sql}")

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a table"""
        if not self.conn:
            self.connect()

        # Get row count
        count_result = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        row_count = count_result[0] if count_result else 0

        # Get column info
        columns_result = self.conn.execute(f"DESCRIBE {table_name}").fetchall()
        columns = [
            {
                'name': col[0],
                'type': col[1],
                'null': col[2]
            }
            for col in columns_result
        ]

        return {
            'table_name': table_name,
            'row_count': row_count,
            'columns': columns
        }

    def list_tables(self) -> List[str]:
        """List all tables in the database"""
        if not self.conn:
            self.connect()

        result = self.conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in result]

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
