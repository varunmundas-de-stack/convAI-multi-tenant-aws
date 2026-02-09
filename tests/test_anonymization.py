"""
Unit tests for schema anonymization functionality
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from semantic_layer.anonymizer import AnonymizationMapper


def test_anonymize_metrics_generic():
    """Test generic strategy anonymization for metrics"""
    mapper = AnonymizationMapper(strategy="generic")

    metrics = [
        {"name": "secondary_sales_value", "description": "Net invoiced value"},
        {"name": "secondary_sales_volume", "description": "Total units sold"}
    ]

    anon_metrics, reverse_map = mapper.anonymize_metrics(metrics)

    # Check anonymized names
    assert anon_metrics[0]['name'] == "metric_001"
    assert anon_metrics[1]['name'] == "metric_002"

    # Check reverse mapping
    assert reverse_map["metric_001"] == "secondary_sales_value"
    assert reverse_map["metric_002"] == "secondary_sales_volume"

    print("[PASS] test_anonymize_metrics_generic")


def test_anonymize_metrics_category():
    """Test category strategy anonymization for metrics"""
    mapper = AnonymizationMapper(strategy="category")

    metrics = [
        {"name": "total_amount", "description": "Net invoiced value"},
        {"name": "quantity_sold", "description": "Total units sold"},
        {"name": "invoice_count", "description": "Number of invoices"}
    ]

    anon_metrics, reverse_map = mapper.anonymize_metrics(metrics)

    # Check category-based names
    assert anon_metrics[0]['name'].startswith("value_metric_")
    assert anon_metrics[1]['name'].startswith("volume_metric_")
    assert anon_metrics[2]['name'].startswith("count_metric_")

    # Check descriptions are anonymized
    assert "Monetary value" in anon_metrics[0]['description']
    assert "Quantity" in anon_metrics[1]['description']

    print("[PASS] test_anonymize_metrics_category")


def test_anonymize_dimensions():
    """Test dimension anonymization"""
    mapper = AnonymizationMapper(strategy="category")

    dimensions = [
        {"name": "brand_name", "description": "Product brand"},
        {"name": "state_name", "description": "Geographic state"},
        {"name": "week", "description": "Week number"}
    ]

    anon_dims, reverse_map = mapper.anonymize_dimensions(dimensions)

    # Check category-based names
    assert anon_dims[0]['name'].startswith("product_dimension_")
    assert anon_dims[1]['name'].startswith("geography_dimension_")
    assert anon_dims[2]['name'].startswith("time_dimension_")

    # Check reverse mapping
    assert reverse_map[anon_dims[0]['name']] == "brand_name"
    assert reverse_map[anon_dims[1]['name']] == "state_name"

    print("[PASS] test_anonymize_dimensions")


def test_deanonymize_semantic_query():
    """Test de-anonymization of semantic query"""
    mapper = AnonymizationMapper(strategy="generic")

    # Setup mappings
    metrics = [{"name": "secondary_sales_value", "description": "Net value"}]
    dimensions = [{"name": "brand_name", "description": "Brand"}]

    mapper.anonymize_metrics(metrics)
    mapper.anonymize_dimensions(dimensions)

    # Create anonymized query dict
    anon_query = {
        "intent": "trend",
        "metric_request": {
            "primary_metric": "metric_001",
            "secondary_metrics": []
        },
        "dimensionality": {
            "group_by": ["dimension_001"]
        },
        "filters": [
            {"dimension": "dimension_001", "operator": "=", "values": ["Brand A"]}
        ],
        "sorting": {
            "order_by": "metric_001",
            "direction": "DESC"
        }
    }

    # De-anonymize
    real_query = mapper.deanonymize_semantic_query(anon_query)

    # Verify de-anonymization
    assert real_query['metric_request']['primary_metric'] == "secondary_sales_value"
    assert real_query['dimensionality']['group_by'] == ["brand_name"]
    assert real_query['filters'][0]['dimension'] == "brand_name"
    assert real_query['sorting']['order_by'] == "secondary_sales_value"

    print("[PASS] test_deanonymize_semantic_query")


def test_hash_strategy():
    """Test hash strategy produces consistent names"""
    mapper1 = AnonymizationMapper(strategy="hash")
    mapper2 = AnonymizationMapper(strategy="hash")

    metrics = [{"name": "secondary_sales_value", "description": "Net value"}]

    anon1, _ = mapper1.anonymize_metrics(metrics)
    anon2, _ = mapper2.anonymize_metrics(metrics)

    # Same input should produce same hash
    assert anon1[0]['name'] == anon2[0]['name']
    assert anon1[0]['name'].startswith("metric_")

    print("[PASS] test_hash_strategy")


def test_anonymization_summary():
    """Test anonymization summary export"""
    mapper = AnonymizationMapper(strategy="category")

    metrics = [
        {"name": "metric1", "description": "desc1"},
        {"name": "metric2", "description": "desc2"}
    ]
    dimensions = [
        {"name": "dim1", "description": "d1"},
        {"name": "dim2", "description": "d2"},
        {"name": "dim3", "description": "d3"}
    ]

    mapper.anonymize_metrics(metrics)
    mapper.anonymize_dimensions(dimensions)

    summary = mapper.get_anonymization_summary()

    assert summary['metrics_mapped'] == 2
    assert summary['dimensions_mapped'] == 3
    assert summary['strategy'] == "category"

    print("[PASS] test_anonymization_summary")


def test_export_mapping():
    """Test exporting mapping for audit"""
    mapper = AnonymizationMapper(strategy="generic")

    metrics = [{"name": "sales_value", "description": "Sales"}]
    dimensions = [{"name": "brand", "description": "Brand"}]

    mapper.anonymize_metrics(metrics)
    mapper.anonymize_dimensions(dimensions)

    mapping = mapper.export_mapping()

    # Check structure
    assert 'metrics' in mapping
    assert 'dimensions' in mapping

    # Check mappings exist
    assert len(mapping['metrics']) == 1
    assert len(mapping['dimensions']) == 1

    # Check reverse mapping works
    anon_metric_name = list(mapping['metrics'].keys())[0]
    assert mapping['metrics'][anon_metric_name] == "sales_value"

    print("[PASS] test_export_mapping")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("RUNNING ANONYMIZATION UNIT TESTS")
    print("=" * 80 + "\n")

    tests = [
        test_anonymize_metrics_generic,
        test_anonymize_metrics_category,
        test_anonymize_dimensions,
        test_deanonymize_semantic_query,
        test_hash_strategy,
        test_anonymization_summary,
        test_export_mapping
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_func.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed")
    print("=" * 80 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
