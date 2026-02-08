"""
Demo script for CPG Conversational AI System with AST + Semantic Layer
Tests the complete flow: Question → SemanticQuery → AST → SQL → Results
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from semantic_layer.semantic_layer import SemanticLayer
from semantic_layer.schemas import (
    SemanticQuery, MetricRequest, Dimensionality,
    TimeContext, Filter, Sorting, IntentType, Diagnostics
)
from semantic_layer.validator import SemanticValidator
from security.rls import RowLevelSecurity, UserContext
from security.audit import AuditLogger
from query_engine.executor import QueryExecutor
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import time


def demo_manual_query():
    """Demo 1: Manually constructed SemanticQuery"""
    console = Console()

    console.print("\n[bold cyan]Demo 1: Manual SemanticQuery Construction[/bold cyan]\n")

    # Initialize components
    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
    validator = SemanticValidator(semantic_layer)

    # Manually construct a query
    semantic_query = SemanticQuery(
        intent=IntentType.RANKING,
        metric_request=MetricRequest(
            primary_metric="secondary_sales_value",
            metric_variant="absolute"
        ),
        dimensionality=Dimensionality(
            group_by=["brand_name"]
        ),
        time_context=TimeContext(
            window="last_4_weeks",
            grain="day"
        ),
        filters=[],
        sorting=Sorting(
            order_by="secondary_sales_value",
            direction="DESC",
            limit=5
        ),
        confidence=1.0,
        original_question="Top 5 brands by sales"
    )

    console.print("[green]OK[/green] SemanticQuery constructed")
    console.print(f"Intent: {semantic_query.intent}")
    console.print(f"Metric: {semantic_query.metric_request.primary_metric}")
    console.print(f"Group By: {semantic_query.dimensionality.group_by}")
    console.print(f"Time Window: {semantic_query.time_context.window}")

    # Validate
    errors = validator.validate(semantic_query)
    if errors:
        console.print(f"[red]Validation errors:[/red] {errors}")
        return
    console.print("[green]OK[/green] Validation passed")

    # Generate SQL using AST
    console.print("\n[yellow]Generating SQL using AST builder...[/yellow]")
    sql_query = semantic_layer.semantic_query_to_sql(semantic_query)

    # Display SQL
    console.print("\n[bold]Generated SQL:[/bold]")
    console.print(Panel(sql_query.sql, title="SQL Query", border_style="blue"))

    # Execute
    console.print("\n[yellow]Executing query...[/yellow]")
    executor = QueryExecutor("database/cpg_olap.duckdb")

    start_time = time.time()
    result = executor.execute(sql_query.sql)
    exec_time = (time.time() - start_time) * 1000

    # Display results
    if hasattr(result, 'data') and result.data:
        table = Table(title=f"Results ({len(result.data)} rows)")

        # Add columns
        for col in result.data[0].keys():
            table.add_column(col, style="cyan")

        # Add rows
        for row in result.data:
            table.add_row(*[str(v) for v in row.values()])

        console.print(table)
        console.print(f"\n[green]OK[/green] Execution time: {exec_time:.2f}ms")
    else:
        console.print(f"[red]Query failed:[/red] {getattr(result, 'error', 'Unknown error')}")


def demo_with_security():
    """Demo 2: Query with Row-Level Security"""
    console = Console()

    console.print("\n\n[bold cyan]Demo 2: Row-Level Security[/bold cyan]\n")

    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")

    # Create query for state-level data
    semantic_query = SemanticQuery(
        intent=IntentType.SNAPSHOT,
        metric_request=MetricRequest(primary_metric="secondary_sales_value"),
        dimensionality=Dimensionality(group_by=["state_name"]),
        time_context=TimeContext(window="this_month"),
        filters=[],
        sorting=Sorting(order_by="secondary_sales_value", direction="DESC", limit=10),
        confidence=1.0,
        original_question="Sales by state this month"
    )

    # Apply security for a sales rep (restricted access)
    user = UserContext(
        user_id="rep_123",
        role="sales_rep",
        data_access_level="state",
        states=["Tamil Nadu", "Karnataka"]
    )

    console.print(f"User: {user.user_id} (Role: {user.role})")
    console.print(f"Access Level: {user.data_access_level}")
    console.print(f"Allowed States: {user.states}")

    # Apply RLS
    secured_query = RowLevelSecurity.apply_security(semantic_query, user)

    console.print(f"\n[yellow]Security filters applied:[/yellow]")
    console.print(f"Original filters: {len(semantic_query.filters)}")
    console.print(f"Secured filters: {len(secured_query.filters)}")

    if secured_query.filters:
        for f in secured_query.filters:
            console.print(f"  - {f.dimension} {f.operator} {f.values}")

    # Generate SQL
    sql_query = semantic_layer.semantic_query_to_sql(secured_query)
    console.print("\n[bold]Generated SQL (with RLS):[/bold]")
    console.print(Panel(sql_query.sql, border_style="yellow"))

    # Execute
    executor = QueryExecutor("database/cpg_olap.duckdb")
    result = executor.execute(sql_query.sql)

    if hasattr(result, 'data') and result.data:
        console.print(f"\n[green]OK[/green] Results limited to allowed states: {len(result.data)} rows")


def demo_with_audit():
    """Demo 3: Query with Audit Logging"""
    console = Console()

    console.print("\n\n[bold cyan]Demo 3: Audit Logging[/bold cyan]\n")

    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
    audit_logger = AuditLogger("logs/audit.jsonl")

    # Simple query
    semantic_query = SemanticQuery(
        intent=IntentType.TREND,
        metric_request=MetricRequest(primary_metric="secondary_sales_volume"),
        dimensionality=Dimensionality(group_by=["week"]),
        time_context=TimeContext(window="last_6_weeks", grain="week"),
        filters=[],
        confidence=1.0,
        original_question="Weekly sales volume trend"
    )

    # Generate SQL
    sql_query = semantic_layer.semantic_query_to_sql(semantic_query)

    # Execute
    executor = QueryExecutor("database/cpg_olap.duckdb")

    start_time = time.time()
    result = executor.execute(sql_query.sql)
    exec_time = (time.time() - start_time) * 1000

    # Log to audit
    query_id = f"Q{int(time.time())}"
    audit_logger.log_query(
        query_id=query_id,
        user_id="demo_user",
        semantic_query=semantic_query.dict(),
        sql=sql_query.sql,
        result_count=len(result.data) if hasattr(result, 'data') and result.data else 0,
        exec_time=exec_time,
        success=hasattr(result, 'data') and result.data is not None,
        error=getattr(result, 'error', None)
    )

    console.print(f"[green]OK[/green] Query logged to audit trail")
    console.print(f"Query ID: {query_id}")
    console.print(f"Execution Time: {exec_time:.2f}ms")

    # Show audit stats
    stats = audit_logger.get_query_stats()
    console.print("\n[bold]Audit Statistics:[/bold]")
    for key, value in stats.items():
        console.print(f"  {key}: {value}")


def demo_validation():
    """Demo 4: Query Validation"""
    console = Console()

    console.print("\n\n[bold cyan]Demo 4: Query Validation[/bold cyan]\n")

    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
    validator = SemanticValidator(semantic_layer)

    # Test 1: Valid query
    console.print("[bold]Test 1: Valid Query[/bold]")
    valid_query = SemanticQuery(
        intent=IntentType.SNAPSHOT,
        metric_request=MetricRequest(primary_metric="secondary_sales_value"),
        dimensionality=Dimensionality(group_by=["brand_name"]),
        time_context=TimeContext(window="this_month"),
        filters=[],
        confidence=1.0,
        original_question="Sales by brand"
    )

    errors = validator.validate(valid_query)
    if errors:
        console.print(f"[red]X Errors:[/red] {errors}")
    else:
        console.print("[green]OK Valid query[/green]")

    # Test 2: Invalid metric
    console.print("\n[bold]Test 2: Invalid Metric[/bold]")
    invalid_query = SemanticQuery(
        intent=IntentType.SNAPSHOT,
        metric_request=MetricRequest(primary_metric="nonexistent_metric"),
        dimensionality=Dimensionality(group_by=[]),
        time_context=TimeContext(window="this_month"),
        filters=[],
        confidence=1.0,
        original_question="Test"
    )

    errors = validator.validate(invalid_query)
    if errors:
        console.print(f"[red]X Errors:[/red] {errors}")
    else:
        console.print("[green]OK Valid query[/green]")

    # Test 3: Too many dimensions
    console.print("\n[bold]Test 3: Too Many Dimensions[/bold]")
    too_many_dims = SemanticQuery(
        intent=IntentType.SNAPSHOT,
        metric_request=MetricRequest(primary_metric="secondary_sales_value"),
        dimensionality=Dimensionality(
            group_by=["brand_name", "state_name", "month_name", "channel_name", "outlet_type"]
        ),
        time_context=TimeContext(window="this_month"),
        filters=[],
        confidence=1.0,
        original_question="Test"
    )

    errors = validator.validate(too_many_dims)
    if errors:
        console.print(f"[red]X Errors:[/red] {errors}")
    else:
        console.print("[green]OK Valid query[/green]")




def demo_query_patterns():
    """Demo 5: Query Pattern Optimization"""
    console = Console()

    console.print("\n\n[bold cyan]Demo 5: Query Pattern Optimization[/bold cyan]\n")

    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
    from semantic_layer.query_patterns import PatternRegistry

    pattern_registry = PatternRegistry()

    # Test 1: Trend Pattern
    console.print("[bold]Test 1: Trend Pattern Optimization[/bold]")
    trend_query = SemanticQuery(
        intent=IntentType.TREND,
        metric_request=MetricRequest(primary_metric="secondary_sales_value"),
        dimensionality=Dimensionality(group_by=["brand_name"]),  # Missing time dim
        time_context=TimeContext(window="last_6_weeks", grain="week"),
        filters=[],
        confidence=1.0,
        original_question="Sales trend by brand"
    )

    console.print(f"Before optimization: group_by = {trend_query.dimensionality.group_by}")
    optimized = pattern_registry.optimize_query(trend_query)
    console.print(f"After optimization: group_by = {optimized.dimensionality.group_by}")
    console.print(f"Sorting added: {optimized.sorting.order_by if optimized.sorting else 'None'}")

    # Test 2: Ranking Pattern
    console.print("\n[bold]Test 2: Ranking Pattern Optimization[/bold]")
    ranking_query = SemanticQuery(
        intent=IntentType.RANKING,
        metric_request=MetricRequest(primary_metric="secondary_sales_volume"),
        dimensionality=Dimensionality(group_by=["sku_name"]),
        time_context=TimeContext(window="this_month"),
        filters=[],
        confidence=1.0,
        original_question="Top SKUs by volume"
    )

    console.print(f"Before optimization: sorting = {ranking_query.sorting}")
    optimized = pattern_registry.optimize_query(ranking_query)
    console.print(f"After optimization: limit = {optimized.sorting.limit if optimized.sorting else 'None'}")
    console.print(f"[green]OK[/green] Pattern optimization working")


def demo_orchestrator():
    """Demo 6: Query Orchestrator for Diagnostics"""
    console = Console()

    console.print("\n\n[bold cyan]Demo 6: Query Orchestrator - Diagnostic Workflow[/bold cyan]\n")

    semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
    from semantic_layer.orchestrator import QueryOrchestrator

    executor = QueryExecutor("database/cpg_olap.duckdb")
    orchestrator = QueryOrchestrator(semantic_layer, executor)

    # Diagnostic query
    diagnostic_query = SemanticQuery(
        intent=IntentType.DIAGNOSTIC,
        metric_request=MetricRequest(primary_metric="secondary_sales_value"),
        dimensionality=Dimensionality(group_by=[]),
        time_context=TimeContext(window="last_6_weeks", grain="week"),
        filters=[],
        diagnostics=Diagnostics(
            enabled=True,
            diagnostic_type="contribution",
            dimensions=["brand_name", "state_name"]
        ),
        confidence=1.0,
        original_question="Why did sales change?"
    )

    console.print("[yellow]Executing diagnostic workflow...[/yellow]")
    result = orchestrator.execute(diagnostic_query)

    console.print(f"\n[bold]Diagnostic Results:[/bold]")
    console.print(f"Total queries executed: {result['metadata']['total_queries']}")
    console.print(f"Total execution time: {result['metadata']['total_execution_time_ms']:.2f}ms")

    # Show analysis
    analysis = result['analysis']
    console.print("\n[bold]Trend Analysis:[/bold]")
    trend = analysis['trend_analysis']
    console.print(f"  Direction: {trend['direction']}")
    console.print(f"  Change: {trend['change_pct']:.1f}%")

    console.print("\n[bold]Key Insights:[/bold]")
    for insight in analysis['insights']:
        console.print(f"  {insight}")

    console.print("\n[bold]Recommendations:[/bold]")
    for rec in analysis['recommendations']:
        console.print(f"  {rec}")

    console.print(f"\n[green]OK[/green] Diagnostic workflow completed")


def main():
    """Run all demos"""
    console = Console()

    console.print(Panel.fit(
        "[bold cyan]CPG Conversational AI System Demo[/bold cyan]\n"
        "Production-Ready AST + Semantic Layer Architecture",
        border_style="cyan"
    ))

    try:
        demo_manual_query()
        demo_with_security()
        demo_with_audit()
        demo_validation()
        demo_query_patterns()
        demo_orchestrator()

        console.print("\n\n[bold green]OK All 6 demos completed successfully![/bold green]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
