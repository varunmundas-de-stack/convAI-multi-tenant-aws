"""
Semantic query validator - validates SemanticQuery before execution
"""
from typing import List
from semantic_layer.schemas import SemanticQuery
from semantic_layer.semantic_layer import SemanticLayer


class SemanticValidator:
    """Validates SemanticQuery structure and semantics"""

    def __init__(self, semantic_layer: SemanticLayer):
        self.semantic_layer = semantic_layer

    def validate(self, semantic_query: SemanticQuery) -> List[str]:
        """
        Validate semantic query and return list of errors.

        Args:
            semantic_query: Query to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # 1. Validate metric exists
        metric = self.semantic_layer.get_metric(
            semantic_query.metric_request.primary_metric
        )
        if not metric:
            errors.append(
                f"Unknown metric: {semantic_query.metric_request.primary_metric}"
            )
            return errors  # Can't continue without valid metric

        # 2. Validate secondary metrics
        for sec_metric_name in semantic_query.metric_request.secondary_metrics:
            if not self.semantic_layer.get_metric(sec_metric_name):
                errors.append(f"Unknown secondary metric: {sec_metric_name}")

        # 3. Validate dimensions exist
        for dim in semantic_query.dimensionality.group_by:
            # Check if dimension is in config
            dim_obj = self.semantic_layer.get_dimension(dim)
            if not dim_obj and not self._is_valid_dimension_attribute(dim):
                errors.append(f"Unknown dimension: {dim}")

        # 4. Validate metric-dimension compatibility (if defined in config)
        if hasattr(metric, 'allowed_dimensions'):
            allowed_dims = metric.get('allowed_dimensions', [])
            if allowed_dims:
                for dim in semantic_query.dimensionality.group_by:
                    if dim not in allowed_dims:
                        errors.append(
                            f"Dimension '{dim}' not compatible with metric '{metric['name']}'"
                        )

        # 5. Validate cardinality (prevent cartesian explosions)
        if len(semantic_query.dimensionality.group_by) > 4:
            errors.append("Too many dimensions (max 4 to prevent performance issues)")

        # 6. Validate time window
        valid_windows = [
            'last_4_weeks', 'last_6_weeks', 'last_12_weeks',
            'mtd', 'qtd', 'ytd', 'this_month', 'last_month',
            'this_year', 'last_year', 'this_quarter', 'last_quarter'
        ]
        if semantic_query.time_context.window not in valid_windows:
            errors.append(
                f"Invalid time window: {semantic_query.time_context.window}. "
                f"Valid: {', '.join(valid_windows)}"
            )

        # 7. Validate filters
        for filter_obj in semantic_query.filters:
            if not self._is_valid_dimension_attribute(filter_obj.dimension):
                errors.append(f"Invalid filter dimension: {filter_obj.dimension}")

            if not filter_obj.values:
                errors.append(f"Filter on {filter_obj.dimension} has no values")

            # Validate operator
            valid_operators = ["=", "IN", "NOT IN", "BETWEEN", ">", "<", ">=", "<="]
            if filter_obj.operator not in valid_operators:
                errors.append(f"Invalid filter operator: {filter_obj.operator}")

        # 8. Validate sorting
        if semantic_query.sorting:
            # Check if sorting by metric or dimension
            sort_field = semantic_query.sorting.order_by
            if (sort_field != semantic_query.metric_request.primary_metric and
                sort_field not in semantic_query.dimensionality.group_by):
                errors.append(
                    f"Cannot sort by '{sort_field}' - not in SELECT clause"
                )

            # Validate limit
            if semantic_query.sorting.limit:
                if semantic_query.sorting.limit < 1 or semantic_query.sorting.limit > 10000:
                    errors.append("Limit must be between 1 and 10000")

        return errors

    def validate_and_raise(self, semantic_query: SemanticQuery):
        """
        Validate and raise ValueError if invalid.

        Args:
            semantic_query: Query to validate

        Raises:
            ValueError: If query is invalid
        """
        errors = self.validate(semantic_query)
        if errors:
            raise ValueError(f"Invalid query: {'; '.join(errors)}")

    def _is_valid_dimension_attribute(self, dim_name: str) -> bool:
        """Check if dimension attribute exists"""
        # List of known dimension attributes
        known_attributes = [
            # Date
            'date', 'year', 'quarter', 'month', 'month_name', 'week', 'day_name',
            'fiscal_year', 'fiscal_quarter', 'fiscal_week', 'season',
            # Product
            'brand_name', 'brand_code', 'category_name', 'sku_name', 'sku_code', 'pack_size',
            # Geography
            'state_name', 'district_name', 'town_name',
            # Sales territory (stored in dim_sales_hierarchy)
            'zone_name', 'region_name',
            # Customer
            'distributor_name', 'retailer_name', 'outlet_type',
            # Channel
            'channel_name'
        ]
        return dim_name in known_attributes
