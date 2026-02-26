#!/usr/bin/env sh
# Database initialisation dispatcher.
# Called by the Docker CMD before Flask starts.
set -e

# ── Always ensure users.db exists ─────────────────────────────────────────────
if [ ! -f database/users.db ]; then
    echo "[init] Creating users.db..."
    PYTHONHASHSEED=0 python database/create_user_db.py
fi

DB_ENGINE="${DB_ENGINE:-duckdb}"

if [ "$DB_ENGINE" = "postgresql" ]; then
    echo "[init] DB_ENGINE=postgresql — waiting for PostgreSQL to be ready..."

    # Python poll loop: try every 2 s for up to 60 s
    PYTHONHASHSEED=0 python - <<'PYEOF'
import os, sys, time

host     = os.getenv('POSTGRES_HOST', 'postgres')
port     = int(os.getenv('POSTGRES_PORT', '5432'))
dbname   = os.getenv('POSTGRES_DB', 'cpg_analytics')
user     = os.getenv('POSTGRES_USER', 'postgres')
password = os.getenv('POSTGRES_PASSWORD', '')

import psycopg2
for attempt in range(30):
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname,
            user=user, password=password,
            connect_timeout=3,
        )
        conn.close()
        print(f"[init] PostgreSQL ready after {attempt + 1} attempt(s)")
        sys.exit(0)
    except Exception as exc:
        print(f"[init] Waiting for PostgreSQL ({attempt + 1}/30): {exc}")
        time.sleep(2)

print("[init] ERROR: PostgreSQL not ready after 60 seconds")
sys.exit(1)
PYEOF

    echo "[init] Seeding PostgreSQL schemas..."
    PYTHONHASHSEED=0 python database/create_multi_schema_pg.py

else
    echo "[init] DB_ENGINE=duckdb (default)"
    if [ ! -f database/cpg_multi_tenant.duckdb ]; then
        echo "[init] Creating DuckDB database..."
        PYTHONHASHSEED=0 python database/create_multi_schema_demo.py
    else
        echo "[init] DuckDB database already exists — skipping seed"
    fi
fi

echo "[init] Initialisation complete"
