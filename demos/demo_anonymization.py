"""
Demo: Schema Anonymization for External LLM Protection

This demo shows how anonymization protects your database schema metadata
when using external LLMs (like Claude API) while maintaining full functionality.

What gets anonymized:
- Metric names: secondary_sales_value → value_metric_001
- Dimension names: brand_name → product_dimension_001
- Descriptions: "Net invoiced value" → "Monetary value measurement"

What stays secure:
- Table names, column names never sent to LLM
- SQL queries generated locally after LLM response
- Actual data values never exposed
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from semantic_layer.semantic_layer import SemanticLayer
from semantic_layer.anonymizer import AnonymizationMapper
from llm.intent_parser_v2 import IntentParserV2


def demo_without_anonymization():
    """Show what gets sent to LLM WITHOUT anonymization"""
    print("=" * 80)
    print("DEMO 1: WITHOUT ANONYMIZATION (Schema Exposed)")
    print("=" * 80)

    # Initialize semantic layer
    config_path = "semantic_layer/configs/client_nestle.yaml"
    semantic_layer = SemanticLayer(config_path, client_id="nestle")

    # Initialize parser WITHOUT anonymization
    parser = IntentParserV2(
        semantic_layer=semantic_layer,
        model="llama3.2:3b",
        use_claude=False,
        anonymize_schema=False  # Schema exposed
    )

    # Show what gets sent to LLM
    print("\n📤 What gets sent to external LLM:")
    print("-" * 80)

    metrics = semantic_layer.list_available_metrics()[:5]
    dimensions = semantic_layer.list_available_dimensions()[:5]

    print("\nMetrics exposed:")
    for m in metrics:
        print(f"  - {m['name']}: {m['description']}")

    print("\nDimensions exposed:")
    for d in dimensions:
        print(f"  - {d['name']}")

    print("\n⚠️  RISK: Real schema names exposed to external LLM!")
    print("=" * 80)
    print()


def demo_with_anonymization():
    """Show what gets sent to LLM WITH anonymization"""
    print("=" * 80)
    print("DEMO 2: WITH ANONYMIZATION (Schema Protected)")
    print("=" * 80)

    # Initialize semantic layer
    config_path = "semantic_layer/configs/client_nestle.yaml"
    semantic_layer = SemanticLayer(config_path, client_id="nestle")

    # Initialize parser WITH anonymization
    parser = IntentParserV2(
        semantic_layer=semantic_layer,
        model="llama3.2:3b",
        use_claude=False,
        anonymize_schema=True,  # Schema protected
        anonymization_strategy="category"  # Category-based naming
    )

    # Show what gets sent to LLM
    print("\n📤 What gets sent to external LLM:")
    print("-" * 80)

    metrics = semantic_layer.list_available_metrics()[:5]
    dimensions = semantic_layer.list_available_dimensions()[:5]

    # Anonymize
    anon_metrics, _ = parser.anonymizer.anonymize_metrics(metrics)
    anon_dimensions, _ = parser.anonymizer.anonymize_dimensions(dimensions)

    print("\nAnonymized Metrics:")
    for m in anon_metrics:
        print(f"  - {m['name']}: {m['description']}")

    print("\nAnonymized Dimensions:")
    for d in anon_dimensions:
        print(f"  - {d['name']}: {d['description']}")

    print("\n✅ SAFE: Only generic names sent to external LLM!")
    print("=" * 80)
    print()


def demo_mapping_details():
    """Show detailed mapping between real and anonymous names"""
    print("=" * 80)
    print("DEMO 3: ANONYMIZATION MAPPING DETAILS")
    print("=" * 80)

    # Initialize semantic layer
    config_path = "semantic_layer/configs/client_nestle.yaml"
    semantic_layer = SemanticLayer(config_path, client_id="nestle")

    # Create anonymizer
    anonymizer = AnonymizationMapper(strategy="category")

    # Get and anonymize metrics
    metrics = semantic_layer.list_available_metrics()[:8]
    anon_metrics, metric_map = anonymizer.anonymize_metrics(metrics)

    print("\n🔀 Metric Mapping:")
    print("-" * 80)
    print(f"{'Real Name':<30} → {'Anonymous Name':<25} Category")
    print("-" * 80)

    for real_name, anon_name in metric_map.items():
        metric_obj = anonymizer.metric_map.get(real_name)
        if metric_obj:
            print(f"{real_name:<30} → {metric_obj.anonymous_name:<25} {metric_obj.category}")

    # Get and anonymize dimensions
    dimensions = semantic_layer.list_available_dimensions()[:8]
    anon_dimensions, dim_map = anonymizer.anonymize_dimensions(dimensions)

    print("\n🔀 Dimension Mapping:")
    print("-" * 80)
    print(f"{'Real Name':<30} → {'Anonymous Name':<30} Category")
    print("-" * 80)

    for real_name, anon_name in dim_map.items():
        dim_obj = anonymizer.dimension_map.get(real_name)
        if dim_obj:
            print(f"{real_name:<30} → {dim_obj.anonymous_name:<30} {dim_obj.hierarchy_level}")

    print("\n📊 Summary:")
    summary = anonymizer.get_anonymization_summary()
    print(f"  - Metrics mapped: {summary['metrics_mapped']}")
    print(f"  - Dimensions mapped: {summary['dimensions_mapped']}")
    print(f"  - Strategy: {summary['strategy']}")

    print("=" * 80)
    print()


def demo_end_to_end():
    """Show end-to-end flow with anonymization"""
    print("=" * 80)
    print("DEMO 4: END-TO-END ANONYMIZED QUERY FLOW")
    print("=" * 80)

    # Initialize semantic layer
    config_path = "semantic_layer/configs/client_nestle.yaml"
    semantic_layer = SemanticLayer(config_path, client_id="nestle")

    # Initialize parser WITH anonymization
    parser = IntentParserV2(
        semantic_layer=semantic_layer,
        model="llama3.2:3b",
        use_claude=False,
        anonymize_schema=True,
        anonymization_strategy="category"
    )

    question = "Show sales by brand for last 4 weeks"

    print(f"\n❓ User Question: '{question}'")
    print("-" * 80)

    print("\n1️⃣ Schema sent to LLM (anonymized):")
    metrics = semantic_layer.list_available_metrics()[:3]
    anon_metrics, _ = parser.anonymizer.anonymize_metrics(metrics)
    print(f"   Metrics: {', '.join([m['name'] for m in anon_metrics])}")

    print("\n2️⃣ LLM returns intent with anonymous names:")
    print("   {")
    print('     "intent": "trend",')
    print('     "metric_request": {"primary_metric": "value_metric_001"},')
    print('     "dimensionality": {"group_by": ["product_dimension_001"]},')
    print('     "time_context": {"window": "last_4_weeks"}')
    print("   }")

    print("\n3️⃣ De-anonymization happens locally:")
    sample_intent = {
        "intent": "trend",
        "metric_request": {"primary_metric": "value_metric_001"},
        "dimensionality": {"group_by": ["product_dimension_001"]},
        "time_context": {"window": "last_4_weeks"}
    }
    deanon_intent = parser.anonymizer.deanonymize_semantic_query(sample_intent)
    print(f"   Real metric: {deanon_intent['metric_request']['primary_metric']}")
    print(f"   Real dimension: {deanon_intent['dimensionality']['group_by']}")

    print("\n4️⃣ SQL generated locally (schema never sent to LLM):")
    print("   SELECT p.brand_name, SUM(f.net_value) AS secondary_sales_value")
    print("   FROM client_nestle.fact_secondary_sales f")
    print("   LEFT JOIN client_nestle.dim_product p ON f.product_key = p.product_key")
    print("   WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'")
    print("   GROUP BY p.brand_name")

    print("\n✅ Complete: Schema protected, query executed successfully!")
    print("=" * 80)
    print()


def demo_anonymization_strategies():
    """Compare different anonymization strategies"""
    print("=" * 80)
    print("DEMO 5: ANONYMIZATION STRATEGIES COMPARISON")
    print("=" * 80)

    # Initialize semantic layer
    config_path = "semantic_layer/configs/client_nestle.yaml"
    semantic_layer = SemanticLayer(config_path, client_id="nestle")

    metrics = semantic_layer.list_available_metrics()[:3]
    real_names = [m['name'] for m in metrics]

    strategies = ['generic', 'category', 'hash']

    print("\n📊 Same metrics, different strategies:")
    print("-" * 80)
    print(f"{'Real Name':<30} Generic          Category              Hash")
    print("-" * 80)

    for i, real_name in enumerate(real_names):
        row = f"{real_name:<30}"

        for strategy in strategies:
            mapper = AnonymizationMapper(strategy=strategy)
            anon, _ = mapper.anonymize_metrics([metrics[i]])
            row += f" {anon[0]['name']:<18}"

        print(row)

    print("\n💡 Strategy Recommendations:")
    print("  - generic: Simplest, sequential numbering (metric_001, metric_002)")
    print("  - category: Better context for LLM (value_metric_001, volume_metric_001)")
    print("  - hash: Consistent across sessions, harder to guess")

    print("\n🎯 Recommended: 'category' for best LLM accuracy with good security")
    print("=" * 80)
    print()


def main():
    """Run all demos"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  SCHEMA ANONYMIZATION DEMO - Protect Your Data Model".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")

    demos = [
        ("Basic Demos", [
            demo_without_anonymization,
            demo_with_anonymization,
            demo_mapping_details,
        ]),
        ("Advanced Demos", [
            demo_end_to_end,
            demo_anonymization_strategies,
        ])
    ]

    for section_name, section_demos in demos:
        print(f"\n{'=' * 80}")
        print(f"{section_name.upper()}")
        print(f"{'=' * 80}\n")

        for demo_func in section_demos:
            try:
                demo_func()
                input("Press Enter to continue...")
                print("\n")
            except Exception as e:
                print(f"❌ Error in {demo_func.__name__}: {e}")
                print()

    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  SUMMARY - HOW TO ENABLE ANONYMIZATION".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    print("Option 1: Via code initialization")
    print("-" * 80)
    print("parser = IntentParserV2(")
    print("    semantic_layer=semantic_layer,")
    print("    anonymize_schema=True,  # Enable anonymization")
    print("    anonymization_strategy='category'  # or 'generic', 'hash'")
    print(")")
    print()
    print("Option 2: Via environment variable")
    print("-" * 80)
    print("export ANONYMIZE_SCHEMA=true")
    print()
    print("✅ Best Practice: Always enable for production with external LLMs!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
