"""
Create multi-schema PostgreSQL database for RBAC testing.
Mirror of create_multi_schema_demo.py — same schemas, tables, and seed data.
"""
import os
import psycopg2
import random
from datetime import datetime, timedelta


def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'cpg_analytics'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
    )


def create_multi_schema_db():
    """Create multi-tenant database with isolated schemas"""
    conn = get_conn()
    conn.autocommit = True  # DDL doesn't need a transaction wrapper
    cur = conn.cursor()

    schemas = ['client_nestle', 'client_unilever', 'client_itc']
    pg_user = os.getenv('POSTGRES_USER', 'postgres')

    for schema in schemas:
        print(f"\n[*] Creating schema: {schema}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        create_dimensions(cur, schema)
        create_fact_table(cur, schema)
        insert_sample_data(cur, schema)

        # Allow Cube.js pre-aggregation tables to be written into this schema
        cur.execute(f"GRANT CREATE ON SCHEMA {schema} TO {pg_user}")

        print(f"[OK] Schema {schema} created with sample data")

    cur.close()
    conn.close()
    print("\n[OK] Multi-tenant PostgreSQL database ready")


def create_dimensions(cur, schema):
    """Create dimension tables"""

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_product (
            product_key INTEGER PRIMARY KEY,
            sku_code VARCHAR,
            sku_name VARCHAR,
            brand_name VARCHAR,
            category_name VARCHAR,
            pack_size VARCHAR
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_geography (
            geography_key INTEGER PRIMARY KEY,
            state_name VARCHAR,
            district_name VARCHAR,
            town_name VARCHAR
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_customer (
            customer_key INTEGER PRIMARY KEY,
            distributor_name VARCHAR,
            retailer_name VARCHAR,
            outlet_type VARCHAR
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_channel (
            channel_key INTEGER PRIMARY KEY,
            channel_name VARCHAR
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_sales_hierarchy (
            hierarchy_key   INTEGER PRIMARY KEY,
            so_code         VARCHAR,
            so_name         VARCHAR,
            asm_code        VARCHAR,
            asm_name        VARCHAR,
            zsm_code        VARCHAR,
            zsm_name        VARCHAR,
            nsm_code        VARCHAR,
            nsm_name        VARCHAR,
            zone_name       VARCHAR,
            region_name     VARCHAR
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_date (
            date_key    INTEGER PRIMARY KEY,
            date        DATE,
            year        INTEGER,
            quarter     INTEGER,
            month       INTEGER,
            month_name  VARCHAR,
            week        INTEGER
        )
    """)


def create_fact_table(cur, schema):
    """Create fact table"""
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.fact_secondary_sales (
            invoice_key         INTEGER PRIMARY KEY,
            invoice_date        DATE,
            product_key         INTEGER,
            geography_key       INTEGER,
            customer_key        INTEGER,
            channel_key         INTEGER,
            date_key            INTEGER,
            sales_hierarchy_key INTEGER,
            invoice_number      VARCHAR,
            invoice_value       DECIMAL(12,2),
            discount_amount     DECIMAL(12,2),
            discount_percentage DECIMAL(5,2),
            net_value           DECIMAL(12,2),
            invoice_quantity    INTEGER,
            margin_amount       DECIMAL(12,2),
            margin_percentage   DECIMAL(5,2),
            return_flag         BOOLEAN DEFAULT FALSE
        )
    """)


def insert_sample_data(cur, schema):
    """Insert sample data — idempotent via ON CONFLICT DO NOTHING"""
    client_suffix = schema.split('_')[1]

    # Products (10 per client)
    brands = ['Brand-A', 'Brand-B', 'Brand-C', 'Brand-D', 'Brand-E']
    categories = ['Beverages', 'Snacks', 'Personal Care']
    for i in range(10):
        brand = brands[i % len(brands)]
        category = categories[i % len(categories)]
        cur.execute(f"""
            INSERT INTO {schema}.dim_product VALUES (
                %s, %s, %s, %s, %s, %s
            ) ON CONFLICT DO NOTHING
        """, (
            i + 1,
            f'SKU{i+1:03d}-{client_suffix}',
            f'Product-{i+1}-{client_suffix}',
            f'{brand}-{client_suffix}',
            category,
            '100g',
        ))

    # Geography (5 states)
    states = [
        ('Tamil Nadu',   'Chennai',   'T Nagar'),
        ('Karnataka',    'Bangalore', 'Koramangala'),
        ('Maharashtra',  'Mumbai',    'Andheri'),
        ('Delhi',        'New Delhi', 'Connaught Place'),
        ('Gujarat',      'Ahmedabad', 'Navrangpura'),
    ]
    for i, (state, district, town) in enumerate(states):
        cur.execute(f"""
            INSERT INTO {schema}.dim_geography VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (i + 1, state, district, town))

    # Customers (5)
    outlet_types = ['GT', 'MT', 'E-Com']
    for i in range(5):
        outlet = outlet_types[i % len(outlet_types)]
        cur.execute(f"""
            INSERT INTO {schema}.dim_customer VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            i + 1,
            f'Distributor-{i+1}-{client_suffix}',
            f'Retailer-{i+1}-{client_suffix}',
            outlet,
        ))

    # Channels
    channels = ['GT', 'MT', 'E-Com', 'IWS', 'Pharma']
    for i, channel in enumerate(channels):
        cur.execute(f"""
            INSERT INTO {schema}.dim_channel VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (i + 1, channel))

    # Sales hierarchy (NSM > ZSM > ASM > SO)
    hierarchy_rows = [
        (1, 'ZSM01_ASM1_SO01', 'SO North 1', 'ZSM01_ASM1', 'ASM North 1', 'ZSM01', 'ZSM North', 'NSM01', 'NSM India', 'North', 'North'),
        (2, 'ZSM01_ASM1_SO02', 'SO North 2', 'ZSM01_ASM1', 'ASM North 1', 'ZSM01', 'ZSM North', 'NSM01', 'NSM India', 'North', 'North'),
        (3, 'ZSM01_ASM2_SO01', 'SO North 3', 'ZSM01_ASM2', 'ASM North 2', 'ZSM01', 'ZSM North', 'NSM01', 'NSM India', 'North', 'North'),
        (4, 'ZSM02_ASM1_SO01', 'SO South 1', 'ZSM02_ASM1', 'ASM South 1', 'ZSM02', 'ZSM South', 'NSM01', 'NSM India', 'South', 'South'),
        (5, 'ZSM02_ASM1_SO02', 'SO South 2', 'ZSM02_ASM1', 'ASM South 1', 'ZSM02', 'ZSM South', 'NSM01', 'NSM India', 'South', 'South'),
    ]
    for row in hierarchy_rows:
        cur.execute(f"""
            INSERT INTO {schema}.dim_sales_hierarchy VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT DO NOTHING
        """, row)

    # Dates — rolling 90 days ending today
    start_date = datetime.now() - timedelta(days=89)
    for i in range(90):
        date = start_date + timedelta(days=i)
        cur.execute(f"""
            INSERT INTO {schema}.dim_date VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            i + 1,
            date.strftime('%Y-%m-%d'),
            date.year,
            (date.month - 1) // 3 + 1,
            date.month,
            date.strftime('%B'),
            date.isocalendar()[1],
        ))

    # Sales transactions (200) — random.seed(schema) for portable determinism
    random.seed(schema)

    for i in range(200):
        product_key   = random.randint(1, 10)
        geo_key       = random.randint(1, 5)
        customer_key  = random.randint(1, 5)
        channel_key   = random.randint(1, 5)
        date_key      = random.randint(1, 90)
        hierarchy_key = random.randint(1, 5)

        invoice_value = random.randint(5000, 50000)
        discount_pct  = random.uniform(5, 15)
        discount_amt  = invoice_value * discount_pct / 100
        net_value     = invoice_value - discount_amt
        quantity      = random.randint(10, 100)
        margin_pct    = random.uniform(10, 25)
        margin_amt    = net_value * margin_pct / 100

        date = start_date + timedelta(days=date_key - 1)

        cur.execute(f"""
            INSERT INTO {schema}.fact_secondary_sales VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, FALSE
            ) ON CONFLICT DO NOTHING
        """, (
            i + 1,
            date.strftime('%Y-%m-%d'),
            product_key,
            geo_key,
            customer_key,
            channel_key,
            date_key,
            hierarchy_key,
            f'INV{i+1:04d}-{client_suffix}',
            invoice_value,
            round(discount_amt, 2),
            round(discount_pct, 2),
            round(net_value, 2),
            quantity,
            round(margin_amt, 2),
            round(margin_pct, 2),
        ))


if __name__ == "__main__":
    print("Creating multi-schema PostgreSQL database...")
    create_multi_schema_db()
    print("\n[OK] Setup complete! Each client has isolated data.")
