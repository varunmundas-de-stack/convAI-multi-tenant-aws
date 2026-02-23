"""
Create multi-schema DuckDB database for RBAC testing
Each client gets isolated schema with sample data
"""
import duckdb
from pathlib import Path
import random
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "cpg_multi_tenant.duckdb"


def create_multi_schema_db():
    """Create multi-tenant database with isolated schemas"""
    conn = duckdb.connect(str(DB_PATH))

    # Create schemas for each client
    schemas = ['client_nestle', 'client_unilever', 'client_itc']

    for schema in schemas:
        print(f"\n[*] Creating schema: {schema}")
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        # Create dimension tables
        create_dimensions(conn, schema)

        # Create fact table
        create_fact_table(conn, schema)

        # Insert sample data
        insert_sample_data(conn, schema)

        print(f"[OK] Schema {schema} created with sample data")

    conn.close()
    print(f"\n[OK] Multi-tenant database created at: {DB_PATH}")
    print(f"[OK] File size: {DB_PATH.stat().st_size / 1024:.2f} KB")


def create_dimensions(conn, schema):
    """Create dimension tables"""

    # dim_product
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_product (
            product_key INTEGER PRIMARY KEY,
            sku_code VARCHAR,
            sku_name VARCHAR,
            brand_name VARCHAR,
            category_name VARCHAR,
            pack_size VARCHAR
        )
    """)

    # dim_geography
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_geography (
            geography_key INTEGER PRIMARY KEY,
            state_name VARCHAR,
            district_name VARCHAR,
            town_name VARCHAR
        )
    """)

    # dim_customer
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_customer (
            customer_key INTEGER PRIMARY KEY,
            distributor_name VARCHAR,
            retailer_name VARCHAR,
            outlet_type VARCHAR
        )
    """)

    # dim_channel
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_channel (
            channel_key INTEGER PRIMARY KEY,
            channel_name VARCHAR
        )
    """)

    # dim_sales_hierarchy — required by the Push Insights engine
    conn.execute(f"""
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

    # dim_date
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.dim_date (
            date_key INTEGER PRIMARY KEY,
            date DATE,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            month_name VARCHAR,
            week INTEGER
        )
    """)


def create_fact_table(conn, schema):
    """Create fact table"""
    conn.execute(f"""
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


def insert_sample_data(conn, schema):
    """Insert sample data"""
    client_suffix = schema.split('_')[1]

    # Insert products (10 products per client)
    brands = ['Brand-A', 'Brand-B', 'Brand-C', 'Brand-D', 'Brand-E']
    categories = ['Beverages', 'Snacks', 'Personal Care']

    for i in range(10):
        brand = brands[i % len(brands)]
        category = categories[i % len(categories)]
        conn.execute(f"""
            INSERT INTO {schema}.dim_product VALUES (
                {i + 1},
                'SKU{i+1:03d}-{client_suffix}',
                'Product-{i+1}-{client_suffix}',
                '{brand}-{client_suffix}',
                '{category}',
                '100g'
            )
        """)

    # Insert geography (5 states)
    states = [
        ('Tamil Nadu', 'Chennai', 'T Nagar'),
        ('Karnataka', 'Bangalore', 'Koramangala'),
        ('Maharashtra', 'Mumbai', 'Andheri'),
        ('Delhi', 'New Delhi', 'Connaught Place'),
        ('Gujarat', 'Ahmedabad', 'Navrangpura')
    ]

    for i, (state, district, town) in enumerate(states):
        conn.execute(f"""
            INSERT INTO {schema}.dim_geography VALUES (
                {i + 1},
                '{state}',
                '{district}',
                '{town}'
            )
        """)

    # Insert customers (5 customers)
    outlet_types = ['GT', 'MT', 'E-Com']
    for i in range(5):
        outlet = outlet_types[i % len(outlet_types)]
        conn.execute(f"""
            INSERT INTO {schema}.dim_customer VALUES (
                {i + 1},
                'Distributor-{i+1}-{client_suffix}',
                'Retailer-{i+1}-{client_suffix}',
                '{outlet}'
            )
        """)

    # Insert channels
    channels = ['GT', 'MT', 'E-Com', 'IWS', 'Pharma']
    for i, channel in enumerate(channels):
        conn.execute(f"""
            INSERT INTO {schema}.dim_channel VALUES (
                {i + 1},
                '{channel}'
            )
        """)

    # Insert sales hierarchy (NSM > ZSM > ASM > SO)
    hierarchy_rows = [
        # key, so_code,  so_name,        asm_code,       asm_name,        zsm_code, zsm_name,    nsm_code, nsm_name,  zone,   region
        (1, 'ZSM01_ASM1_SO01', 'SO North 1',  'ZSM01_ASM1',   'ASM North 1',   'ZSM01',  'ZSM North', 'NSM01',  'NSM India', 'North', 'North'),
        (2, 'ZSM01_ASM1_SO02', 'SO North 2',  'ZSM01_ASM1',   'ASM North 1',   'ZSM01',  'ZSM North', 'NSM01',  'NSM India', 'North', 'North'),
        (3, 'ZSM01_ASM2_SO01', 'SO North 3',  'ZSM01_ASM2',   'ASM North 2',   'ZSM01',  'ZSM North', 'NSM01',  'NSM India', 'North', 'North'),
        (4, 'ZSM02_ASM1_SO01', 'SO South 1',  'ZSM02_ASM1',   'ASM South 1',   'ZSM02',  'ZSM South', 'NSM01',  'NSM India', 'South', 'South'),
        (5, 'ZSM02_ASM1_SO02', 'SO South 2',  'ZSM02_ASM1',   'ASM South 1',   'ZSM02',  'ZSM South', 'NSM01',  'NSM India', 'South', 'South'),
    ]
    for row in hierarchy_rows:
        conn.execute(f"""
            INSERT INTO {schema}.dim_sales_hierarchy VALUES (
                {row[0]},
                '{row[1]}', '{row[2]}',
                '{row[3]}', '{row[4]}',
                '{row[5]}', '{row[6]}',
                '{row[7]}', '{row[8]}',
                '{row[9]}', '{row[10]}'
            )
        """)

    # Insert dates — use rolling 90 days ending today so "last 4 weeks" filters always return data
    start_date = datetime.now() - timedelta(days=89)
    for i in range(90):
        date = start_date + timedelta(days=i)
        conn.execute(f"""
            INSERT INTO {schema}.dim_date VALUES (
                {i + 1},
                '{date.strftime('%Y-%m-%d')}',
                {date.year},
                {(date.month - 1) // 3 + 1},
                {date.month},
                '{date.strftime('%B')}',
                {date.isocalendar()[1]}
            )
        """)

    # Insert sales transactions (200 transactions spread over the 90-day window)
    random.seed(hash(schema))  # Different data per schema

    for i in range(200):
        product_key       = random.randint(1, 10)
        geo_key           = random.randint(1, 5)
        customer_key      = random.randint(1, 5)
        channel_key       = random.randint(1, 5)
        date_key          = random.randint(1, 90)
        hierarchy_key     = random.randint(1, 5)

        invoice_value = random.randint(5000, 50000)
        discount_pct = random.uniform(5, 15)
        discount_amt = invoice_value * discount_pct / 100
        net_value = invoice_value - discount_amt
        quantity = random.randint(10, 100)
        margin_pct = random.uniform(10, 25)
        margin_amt = net_value * margin_pct / 100

        date = start_date + timedelta(days=date_key - 1)

        conn.execute(f"""
            INSERT INTO {schema}.fact_secondary_sales VALUES (
                {i + 1},
                '{date.strftime('%Y-%m-%d')}',
                {product_key},
                {geo_key},
                {customer_key},
                {channel_key},
                {date_key},
                {hierarchy_key},
                'INV{i+1:04d}-{client_suffix}',
                {invoice_value},
                {discount_amt:.2f},
                {discount_pct:.2f},
                {net_value:.2f},
                {quantity},
                {margin_amt:.2f},
                {margin_pct:.2f},
                FALSE
            )
        """)


if __name__ == "__main__":
    print("Creating multi-schema DuckDB database...")
    create_multi_schema_db()
    print("\n[OK] Setup complete! Each client has isolated data.")
