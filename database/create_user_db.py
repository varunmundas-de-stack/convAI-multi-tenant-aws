"""
Create user database for RBAC
Users are mapped to clients and can only query their assigned schema
"""
import sqlite3
import bcrypt
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


def create_user_database():
    """Create user database with authentication tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            client_id TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT DEFAULT 'analytics',
            sales_hierarchy_level TEXT,
            so_code TEXT,
            asm_code TEXT,
            zsm_code TEXT,
            nsm_code TEXT,
            territory_codes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # Insights table — stores hierarchy-targeted nudges
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            insight_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            hierarchy_level TEXT NOT NULL,  -- SO, ASM, ZSM, NSM, all
            so_code TEXT,
            asm_code TEXT,
            zsm_code TEXT,
            nsm_code TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            insight_type TEXT NOT NULL,  -- trend, anomaly, alert, recommendation, opportunity
            priority TEXT NOT NULL,      -- high, medium, low
            metric_value REAL,
            metric_change_pct REAL,
            suggested_action TEXT,
            suggested_query TEXT,        -- pre-filled chat query the user can click
            data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    """)

    # Per-user read tracking (separate so one insight can be delivered to multiple users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insight_reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(insight_id, user_id)
        )
    """)

    # Clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            database_path TEXT NOT NULL,
            config_path TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            client_id TEXT NOT NULL,
            question TEXT NOT NULL,
            sql_query TEXT,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    return conn


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_sample_data(conn):
    """Create sample clients and users for testing"""
    cursor = conn.cursor()

    # Sample clients
    clients = [
        ('nestle', 'Nestlé India', 'client_nestle',
         'database/cpg_multi_tenant.duckdb',
         'semantic_layer/configs/client_nestle.yaml'),
        ('unilever', 'Unilever India', 'client_unilever',
         'database/cpg_multi_tenant.duckdb',
         'semantic_layer/configs/client_unilever.yaml'),
        ('itc', 'ITC Limited', 'client_itc',
         'database/cpg_multi_tenant.duckdb',
         'semantic_layer/configs/client_itc.yaml'),
    ]

    for client in clients:
        cursor.execute("""
            INSERT OR IGNORE INTO clients
            (client_id, client_name, schema_name, database_path, config_path)
            VALUES (?, ?, ?, ?, ?)
        """, client)

    # Sample users with department and sales hierarchy info
    users = [
        # Nestle users
        ('nestle_admin', 'admin123', 'admin@nestle.com',
         'Nestle Admin', 'nestle', 'admin', 'analytics', None, None, None, None, None, None),
        ('nestle_analyst', 'analyst123', 'analyst@nestle.com',
         'Nestle Analyst', 'nestle', 'analyst', 'analytics', None, None, None, None, None, None),

        # Unilever users
        ('unilever_admin', 'admin123', 'admin@unilever.com',
         'Unilever Admin', 'unilever', 'admin', 'analytics', None, None, None, None, None, None),
        ('unilever_analyst', 'analyst123', 'analyst@unilever.com',
         'Unilever Analyst', 'unilever', 'analyst', 'marketing', None, None, None, None, None, None),

        # ITC users
        ('itc_admin', 'admin123', 'admin@itc.com',
         'ITC Admin', 'itc', 'admin', 'analytics', None, None, None, None, None, None),
        ('itc_analyst', 'analyst123', 'analyst@itc.com',
         'ITC Analyst', 'itc', 'analyst', 'finance', None, None, None, None, None, None),

        # Sales Hierarchy users (Nestle)
        ('nsm_rajesh', 'nsm123', 'rajesh@nestle.com',
         'Rajesh Kumar (NSM)', 'nestle', 'NSM', 'sales', 'NSM', None, None, None, 'NSM01', None),
        ('zsm_amit', 'zsm123', 'amit@nestle.com',
         'Amit Shah (ZSM North)', 'nestle', 'ZSM', 'sales', 'ZSM', None, None, 'ZSM01', None, None),
        ('asm_rahul', 'asm123', 'rahul@nestle.com',
         'Rahul Verma (ASM)', 'nestle', 'ASM', 'sales', 'ASM', None, 'ZSM01_ASM1', None, None, None),
        ('so_field1', 'so123', 'field1@nestle.com',
         'Field Officer 1', 'nestle', 'SO', 'sales', 'SO', 'ZSM01_ASM1_SO01', None, None, None, None),
    ]

    for username, password, email, full_name, client_id, role, department, sales_hierarchy_level, so_code, asm_code, zsm_code, nsm_code, territory_codes in users:
        password_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users
            (username, password_hash, email, full_name, client_id, role, department,
             sales_hierarchy_level, so_code, asm_code, zsm_code, nsm_code, territory_codes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash=excluded.password_hash,
                email=excluded.email,
                full_name=excluded.full_name,
                client_id=excluded.client_id,
                role=excluded.role,
                department=excluded.department,
                sales_hierarchy_level=excluded.sales_hierarchy_level,
                so_code=excluded.so_code,
                asm_code=excluded.asm_code,
                zsm_code=excluded.zsm_code,
                nsm_code=excluded.nsm_code,
                territory_codes=excluded.territory_codes
        """, (username, password_hash, email, full_name, client_id, role, department,
              sales_hierarchy_level, so_code, asm_code, zsm_code, nsm_code, territory_codes))

    conn.commit()
    print("[OK] User database created successfully!")
    print("\n" + "="*90)
    print("SAMPLE USERS CREATED")
    print("="*90)
    print(f"{'Username':<20} {'Password':<15} {'Client':<15} {'Role':<10} {'Department':<12}")
    print("="*90)
    for username, password, _, _, client_id, role, department, *_ in users:
        print(f"{username:<20} {password:<15} {client_id:<15} {role:<10} {department:<12}")
    print("="*90)
    print("\nSales Hierarchy Users:")
    print("-" * 90)
    for username, password, _, _, client_id, role, department, sales_hierarchy_level, so_code, asm_code, zsm_code, nsm_code, territory_codes in users:
        if sales_hierarchy_level:
            hierarchy_info = f"{sales_hierarchy_level}: "
            if nsm_code:
                hierarchy_info += nsm_code
            elif zsm_code:
                hierarchy_info += zsm_code
            elif asm_code:
                hierarchy_info += asm_code
            elif so_code:
                hierarchy_info += so_code
            print(f"{username:<20} {role:<10} {hierarchy_info}")
    print("="*90)


if __name__ == "__main__":
    print("Creating user database for RBAC...")
    conn = create_user_database()
    create_sample_data(conn)
    conn.close()
    print(f"\n[OK] Database created at: {DB_PATH}")
    print(f"[OK] File size: {DB_PATH.stat().st_size / 1024:.2f} KB")
