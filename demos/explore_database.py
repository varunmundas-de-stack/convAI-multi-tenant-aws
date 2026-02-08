"""
Database Explorer - Show metadata, row counts, and sample data
Use this to show technical details to developers and data engineers
"""
import duckdb
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

def explore_database(db_path="database/cpg_olap.duckdb"):
    """Explore database structure and content"""

    console.print(Panel.fit(
        "[bold cyan]CPG Database Explorer[/bold cyan]\n"
        "Database Metadata & Sample Data",
        border_style="cyan"
    ))

    # Connect to database
    conn = duckdb.connect(db_path, read_only=True)

    # 1. List all tables
    console.print("\n[bold yellow]1. Database Tables[/bold yellow]\n")

    tables_query = """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """

    tables = conn.execute(tables_query).fetchall()

    tables_table = Table(title="Tables in Database", show_header=True, header_style="bold magenta")
    tables_table.add_column("Table Name", style="cyan", width=30)
    tables_table.add_column("Type", style="green")

    for table_name, table_type in tables:
        tables_table.add_row(table_name, table_type)

    console.print(tables_table)
    console.print(f"\n[green]Total tables: {len(tables)}[/green]\n")

    # 2. For each table, show metadata and samples
    for table_name, _ in tables:
        console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
        console.print(f"[bold yellow]Table: {table_name}[/bold yellow]\n")

        # Get row count
        count_query = f"SELECT COUNT(*) FROM {table_name}"
        row_count = conn.execute(count_query).fetchone()[0]
        console.print(f"[green]Row count: {row_count:,}[/green]\n")

        # Get schema (columns and types)
        schema_query = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """

        schema = conn.execute(schema_query).fetchall()

        schema_table = Table(title=f"Schema: {table_name}", show_header=True)
        schema_table.add_column("Column Name", style="cyan", width=25)
        schema_table.add_column("Data Type", style="yellow", width=20)
        schema_table.add_column("Nullable", style="magenta", width=10)

        for col_name, data_type, nullable in schema:
            schema_table.add_row(col_name, data_type, nullable)

        console.print(schema_table)

        # Get sample data (first 5 rows)
        console.print(f"\n[bold]Sample Data (first 5 rows):[/bold]\n")

        sample_query = f"SELECT * FROM {table_name} LIMIT 5"
        sample_data = conn.execute(sample_query).fetchall()
        sample_columns = [desc[0] for desc in conn.description]

        if sample_data:
            sample_table = Table(show_header=True, header_style="bold green")

            # Add columns
            for col in sample_columns:
                sample_table.add_column(col, style="white", overflow="fold", max_width=20)

            # Add rows
            for row in sample_data:
                sample_table.add_row(*[str(val) if val is not None else '-' for val in row])

            console.print(sample_table)
        else:
            console.print("[yellow]No data in table[/yellow]")

        console.print()

    # 3. Summary statistics
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print("[bold yellow]Summary Statistics[/bold yellow]\n")

    summary_table = Table(title="Database Summary", show_header=True)
    summary_table.add_column("Metric", style="cyan", width=30)
    summary_table.add_column("Value", style="green", justify="right")

    total_rows = sum(conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0] for t in tables)
    total_columns = sum(len(conn.execute(f"SELECT * FROM {t[0]} LIMIT 0").description) for t in tables)

    summary_table.add_row("Total Tables", str(len(tables)))
    summary_table.add_row("Total Rows (all tables)", f"{total_rows:,}")
    summary_table.add_row("Total Columns (all tables)", str(total_columns))
    summary_table.add_row("Database Size", get_db_size(db_path))

    console.print(summary_table)

    # 4. Star schema visualization
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print("[bold yellow]Star Schema Structure[/bold yellow]\n")

    schema_diagram = """
    FACT TABLES (Center):
    ├─ fact_secondary_sales (1,000 rows)
    │  └─ Contains: invoice transactions from distributors to retailers
    │

    DIMENSION TABLES (Surrounding):
    ├─ dim_date (90 rows)
    │  └─ Fiscal calendar, weeks, months, quarters, seasons
    │
    ├─ dim_product (50 rows)
    │  └─ Product hierarchy: Category → Brand → SKU
    │
    ├─ dim_geography (200 rows)
    │  └─ Location hierarchy: Zone → State → District → Town → Outlet
    │
    ├─ dim_customer (120 rows)
    │  └─ Customer hierarchy: Distributor → Retailer → Outlet Type
    │
    └─ dim_channel (5 rows)
       └─ Sales channels: GT, MT, E-Com, IWS, Pharma

    RELATIONSHIPS:
    fact_secondary_sales.date_key         → dim_date.date_key
    fact_secondary_sales.product_key      → dim_product.product_key
    fact_secondary_sales.geography_key    → dim_geography.geography_key
    fact_secondary_sales.customer_key     → dim_customer.customer_key
    fact_secondary_sales.channel_key      → dim_channel.channel_key
    """

    console.print(Panel(schema_diagram, border_style="cyan", title="Star Schema"))

    # 5. Sample queries
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print("[bold yellow]Sample SQL Queries You Can Run[/bold yellow]\n")

    sample_queries = [
        ("Top 5 brands by sales", """
SELECT p.brand_name, SUM(s.net_value) as total_sales
FROM fact_secondary_sales s
JOIN dim_product p ON s.product_key = p.product_key
GROUP BY p.brand_name
ORDER BY total_sales DESC
LIMIT 5;
        """),
        ("Sales by state", """
SELECT g.state_name, SUM(s.net_value) as total_sales
FROM fact_secondary_sales s
JOIN dim_geography g ON s.geography_key = g.geography_key
GROUP BY g.state_name
ORDER BY total_sales DESC;
        """),
        ("Monthly sales trend", """
SELECT d.month_name, SUM(s.net_value) as monthly_sales
FROM fact_secondary_sales s
JOIN dim_date d ON s.date_key = d.date_key
GROUP BY d.month_name, d.month_number
ORDER BY d.month_number;
        """)
    ]

    for i, (title, query) in enumerate(sample_queries, 1):
        console.print(f"\n[bold green]{i}. {title}:[/bold green]")
        syntax = Syntax(query.strip(), "sql", theme="monokai", line_numbers=False)
        console.print(syntax)

    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]\n")
    console.print("[bold green]✓ Database exploration complete![/bold green]")
    console.print("\n[yellow]To run custom SQL queries, use:[/yellow]")
    console.print("  python -c \"import duckdb; conn = duckdb.connect('database/cpg_olap.duckdb'); print(conn.execute('YOUR_SQL_HERE').fetchall())\"")
    console.print()

    conn.close()


def get_db_size(db_path):
    """Get database file size"""
    import os
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
    return "Unknown"


if __name__ == "__main__":
    try:
        explore_database()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        traceback.print_exc()
