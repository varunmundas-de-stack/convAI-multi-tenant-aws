"""
AST Query Builder - converts SemanticQuery to SQL AST
"""
from typing import List, Optional, Dict
from semantic_layer.schemas import SemanticQuery, Filter, IntentType
from semantic_layer.ast_builder import (
    Query, SelectClause, FromClause, JoinClause, WhereClause,
    GroupByClause, OrderByClause, LimitClause,
    ColumnRef, AggregateExpr, BinaryExpr, Literal, RawSQLExpr
)


class ASTQueryBuilder:
    """Builds SQL AST from SemanticQuery"""

    def __init__(self, semantic_layer):
        """
        Args:
            semantic_layer: SemanticLayer instance for metric/dimension lookups
        """
        self.semantic_layer = semantic_layer

    def build_query(self, semantic_query: SemanticQuery) -> Query:
        """
        Convert SemanticQuery to SQL AST.

        Args:
            semantic_query: Structured semantic query

        Returns:
            Query: Complete SQL AST

        Raises:
            ValueError: If query cannot be built (invalid metric, dimension, etc.)
        """
        # 1. Resolve metric → fact table
        metric_name = semantic_query.metric_request.primary_metric
        metric = self.semantic_layer.get_metric(metric_name)

        if not metric:
            raise ValueError(f"Unknown metric: {metric_name}")

        # 2. Build SELECT (dimensions + metrics)
        select = self._build_select(semantic_query, metric)

        # 3. Build FROM clause
        from_clause = self._build_from(metric)

        # 4. Build JOINs for dimensions
        joins = self._build_joins(semantic_query, metric)

        # 5. Build WHERE (filters + time + metric filters)
        where = self._build_where(semantic_query, metric)

        # 6. Build GROUP BY
        group_by = self._build_group_by(semantic_query)

        # 7. Build ORDER BY
        order_by = self._build_order_by(semantic_query)

        # 8. Build LIMIT
        limit = self._build_limit(semantic_query)

        # 9. Construct query tree
        query = Query(
            select=select,
            from_clause=from_clause,
            joins=joins,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit
        )

        # 10. Validate before returning
        errors = query.validate()
        if errors:
            # Filter out warnings
            critical_errors = [e for e in errors if not e.startswith("Warning:")]
            if critical_errors:
                raise ValueError(f"Invalid query: {'; '.join(critical_errors)}")

        return query

    def _build_select(self, semantic_query: SemanticQuery, metric: Dict) -> SelectClause:
        """Build SELECT clause with dimensions and metrics"""
        expressions = []

        # Add dimensions (group by columns)
        for dim_name in semantic_query.dimensionality.group_by:
            # Resolve dimension attribute
            col_name = self._resolve_dimension_attribute(dim_name)
            if col_name:
                expressions.append(ColumnRef(column=col_name, alias=dim_name))

        # Add primary metric
        metric_sql = metric.get('sql', f"SUM({metric['table']}.value)")

        # Parse metric SQL to create aggregate
        # Simplified: assume SUM(column) or COUNT(column) format
        if metric_sql.startswith("SUM("):
            col = metric_sql[4:-1]  # Extract column name
            agg = AggregateExpr(
                function="SUM",
                expression=col,
                alias=semantic_query.metric_request.primary_metric
            )
            expressions.append(agg)
        elif metric_sql.startswith("COUNT("):
            col = metric_sql[6:-1]
            agg = AggregateExpr(
                function="COUNT",
                expression=col,
                alias=semantic_query.metric_request.primary_metric
            )
            expressions.append(agg)
        elif metric_sql.startswith("AVG("):
            col = metric_sql[4:-1]
            agg = AggregateExpr(
                function="AVG",
                expression=col,
                alias=semantic_query.metric_request.primary_metric
            )
            expressions.append(agg)
        else:
            # Complex expression - use as-is
            expressions.append(f"({metric_sql}) AS {semantic_query.metric_request.primary_metric}")

        # Add secondary metrics
        for sec_metric_name in semantic_query.metric_request.secondary_metrics:
            sec_metric = self.semantic_layer.get_metric(sec_metric_name)
            if sec_metric:
                sec_sql = sec_metric.get('sql', f"SUM(value)")
                expressions.append(f"({sec_sql}) AS {sec_metric_name}")

        return SelectClause(expressions=expressions)

    def _build_from(self, metric: Dict) -> FromClause:
        """Build FROM clause"""
        table_name = metric.get('table', 'fact_secondary_sales')

        # Extract table name if it has joins in the config
        if ' JOIN ' in table_name.upper():
            # Complex table reference - use first table
            table_name = table_name.split()[0]

        return FromClause(table=table_name, alias="f")

    def _build_joins(self, semantic_query: SemanticQuery, metric: Dict) -> List[JoinClause]:
        """Build JOIN clauses for dimensions"""
        joins = []

        # Map dimension/filter column to base table name
        dimension_tables = {
            'date': 'dim_date',
            'year': 'dim_date',
            'quarter': 'dim_date',
            'month': 'dim_date',
            'month_name': 'dim_date',
            'week': 'dim_date',
            'day_name': 'dim_date',
            'fiscal_year': 'dim_date',
            'fiscal_quarter': 'dim_date',
            'fiscal_week': 'dim_date',
            'brand_name': 'dim_product',
            'brand_code': 'dim_product',
            'category_name': 'dim_product',
            'sku_name': 'dim_product',
            'sku_code': 'dim_product',
            'state_name': 'dim_geography',
            'district_name': 'dim_geography',
            'town_name': 'dim_geography',
            # zone_name and region_name are in dim_sales_hierarchy, not dim_geography
            'zone_name': 'dim_sales_hierarchy',
            'region_name': 'dim_sales_hierarchy',
            'distributor_name': 'dim_customer',
            'retailer_name': 'dim_customer',
            'outlet_type': 'dim_customer',
            'channel_name': 'dim_channel',
            # Sales hierarchy columns
            'so_code': 'dim_sales_hierarchy',
            'so_name': 'dim_sales_hierarchy',
            'asm_code': 'dim_sales_hierarchy',
            'asm_name': 'dim_sales_hierarchy',
            'zsm_code': 'dim_sales_hierarchy',
            'zsm_name': 'dim_sales_hierarchy',
            'nsm_code': 'dim_sales_hierarchy',
            'nsm_name': 'dim_sales_hierarchy',
            'territory_code': 'dim_sales_hierarchy',
            'territory_name': 'dim_sales_hierarchy',
        }

        # Track joined tables to avoid duplicates
        joined_tables = set()

        # Collect all columns that need joins: from group_by AND from filters
        cols_needing_joins = list(semantic_query.dimensionality.group_by)
        for filter_obj in semantic_query.filters:
            cols_needing_joins.append(filter_obj.dimension)

        # Derive schema prefix from metric's fact table (e.g. "client_nestle")
        metric_table = metric.get('table', '')
        schema_prefix = metric_table.rsplit('.', 1)[0] if '.' in metric_table else ''

        for dim in cols_needing_joins:
            base_table = dimension_tables.get(dim)
            if base_table and base_table not in joined_tables:
                # Get the qualified table name from semantic layer
                qualified_table = base_table  # fallback to base name
                for dim_name, dimension in self.semantic_layer.dimensions.items():
                    dim_base_table = dimension.table.split('.')[-1] if '.' in dimension.table else dimension.table
                    if dim_base_table == base_table:
                        qualified_table = dimension.table  # Use fully qualified name
                        break

                # If still unqualified and we have a schema prefix, apply it
                if qualified_table == base_table and schema_prefix:
                    qualified_table = f"{schema_prefix}.{base_table}"

                # Create join with qualified table name
                join = self._create_dimension_join(qualified_table)
                if join:
                    joins.append(join)
                    joined_tables.add(base_table)  # Track by base name to avoid duplicates

        return joins

    def _create_dimension_join(self, table: str) -> Optional[JoinClause]:
        """Create JOIN for a dimension table"""
        # Map table to join condition
        join_conditions = {
            'dim_date': BinaryExpr(
                left=ColumnRef(column="date_key", table="f"),
                operator="=",
                right=ColumnRef(column="date_key", table="d")
            ),
            'dim_product': BinaryExpr(
                left=ColumnRef(column="product_key", table="f"),
                operator="=",
                right=ColumnRef(column="product_key", table="p")
            ),
            'dim_geography': BinaryExpr(
                left=ColumnRef(column="geography_key", table="f"),
                operator="=",
                right=ColumnRef(column="geography_key", table="g")
            ),
            'dim_customer': BinaryExpr(
                left=ColumnRef(column="customer_key", table="f"),
                operator="=",
                right=ColumnRef(column="customer_key", table="c")
            ),
            'dim_channel': BinaryExpr(
                left=ColumnRef(column="channel_key", table="f"),
                operator="=",
                right=ColumnRef(column="channel_key", table="ch")
            ),
            'dim_sales_hierarchy': BinaryExpr(
                left=ColumnRef(column="sales_hierarchy_key", table="f"),
                operator="=",
                right=ColumnRef(column="hierarchy_key", table="sh")
            ),
        }

        # Map table to alias
        table_aliases = {
            'dim_date': 'd',
            'dim_product': 'p',
            'dim_geography': 'g',
            'dim_customer': 'c',
            'dim_channel': 'ch',
            'dim_sales_hierarchy': 'sh',
        }

        # Extract base table name (handle schema-qualified names like client_nestle.dim_product)
        base_table = table.split('.')[-1] if '.' in table else table

        condition = join_conditions.get(base_table)
        alias = table_aliases.get(base_table)

        if condition and alias:
            return JoinClause(
                join_type="LEFT",
                table=table,  # Use full qualified table name
                alias=alias,
                on_condition=condition
            )

        return None

    def _build_where(self, semantic_query: SemanticQuery, metric: Dict) -> Optional[WhereClause]:
        """Build WHERE clause"""
        conditions = []

        # Add metric-level filters (e.g., return_flag = false)
        metric_filters = metric.get('filters', [])
        for filter_str in metric_filters:
            # Parse simple filters like "return_flag = false"
            if '=' in filter_str:
                parts = filter_str.split('=')
                col = parts[0].strip()
                val = parts[1].strip()

                # Convert value
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]

                condition = BinaryExpr(
                    left=ColumnRef(column=col, table="f"),
                    operator="=",
                    right=Literal(value=val)
                )
                conditions.append(condition)

        # Add user filters
        for filter_obj in semantic_query.filters:
            condition = self._build_filter_condition(filter_obj)
            if condition:
                conditions.append(condition)

        # Add time window filter (pass fact table so dates use data's max date, not CURRENT_DATE)
        fact_table = metric.get('table', 'fact_secondary_sales')
        time_condition = self._build_time_filter(semantic_query.time_context, fact_table)
        if time_condition:
            conditions.append(time_condition)

        if conditions:
            return WhereClause(condition=conditions)

        return None

    def _build_filter_condition(self, filter_obj: Filter) -> Optional[BinaryExpr]:
        """Build condition from Filter object"""
        # Resolve dimension to column
        col_name = self._resolve_dimension_attribute(filter_obj.dimension)
        if not col_name:
            return None

        if filter_obj.operator == "IN":
            literals = [Literal(value=v) for v in filter_obj.values]
            return BinaryExpr(
                left=ColumnRef(column=col_name),
                operator="IN",
                right=literals
            )
        elif filter_obj.operator == "=":
            return BinaryExpr(
                left=ColumnRef(column=col_name),
                operator="=",
                right=Literal(value=filter_obj.values[0])
            )
        else:
            # Other operators
            return BinaryExpr(
                left=ColumnRef(column=col_name),
                operator=filter_obj.operator,
                right=Literal(value=filter_obj.values[0])
            )

    def _build_time_filter(self, time_context, fact_table: str = 'fact_secondary_sales') -> Optional[RawSQLExpr]:
        """Build time filter condition using invoice_date on the fact table.

        Uses MAX(invoice_date) from the fact table instead of CURRENT_DATE so that
        relative windows like 'this_month' / 'last_4_weeks' stay anchored to the
        latest available data rather than the server clock (handles data that doesn't
        extend to today).
        """
        window = time_context.window if time_context else None
        if not window:
            return None

        # Anchor all relative windows to the latest date present in the data.
        # This handles the common case where the dataset ends before today.
        md = f"(SELECT MAX(invoice_date) FROM {fact_table})"

        # All filters use f.invoice_date directly (avoids dependency on dim_date join)
        time_filters = {
            'last_4_weeks':  f"f.invoice_date >= {md} - INTERVAL 28 DAY",
            'last_6_weeks':  f"f.invoice_date >= {md} - INTERVAL 42 DAY",
            'last_12_weeks': f"f.invoice_date >= {md} - INTERVAL 84 DAY",
            'this_month':    f"EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM {md}) AND EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md})",
            'mtd':           f"EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM {md}) AND EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md})",
            'last_month':    f"EXTRACT(MONTH FROM f.invoice_date) = EXTRACT(MONTH FROM {md} - INTERVAL 1 MONTH) AND EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md} - INTERVAL 1 MONTH)",
            'qtd':           f"EXTRACT(QUARTER FROM f.invoice_date) = EXTRACT(QUARTER FROM {md}) AND EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md})",
            'ytd':           f"EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md})",
            'this_year':     f"EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md})",
            'last_year':     f"EXTRACT(YEAR FROM f.invoice_date) = EXTRACT(YEAR FROM {md}) - 1",
        }

        sql = time_filters.get(window)
        if sql:
            return RawSQLExpr(sql=sql)
        return None

    def _build_group_by(self, semantic_query: SemanticQuery) -> Optional[GroupByClause]:
        """Build GROUP BY clause"""
        if not semantic_query.dimensionality.group_by:
            return None

        columns = []
        for dim in semantic_query.dimensionality.group_by:
            col_name = self._resolve_dimension_attribute(dim)
            if col_name:
                columns.append(ColumnRef(column=col_name))

        if columns:
            return GroupByClause(columns=columns)

        return None

    def _build_order_by(self, semantic_query: SemanticQuery) -> Optional[OrderByClause]:
        """Build ORDER BY clause"""
        if not semantic_query.sorting:
            return None

        order_by = semantic_query.sorting.order_by
        direction = semantic_query.sorting.direction

        # Check if ordering by metric or dimension
        if order_by in semantic_query.dimensionality.group_by:
            col = self._resolve_dimension_attribute(order_by)
            if col:
                return OrderByClause(columns=[(ColumnRef(column=col), direction)])
        else:
            # Ordering by metric
            return OrderByClause(columns=[(order_by, direction)])

        return None

    def _build_limit(self, semantic_query: SemanticQuery) -> Optional[LimitClause]:
        """Build LIMIT clause"""
        if semantic_query.sorting and semantic_query.sorting.limit:
            return LimitClause(limit=semantic_query.sorting.limit)
        return None

    def _resolve_dimension_attribute(self, dim_name: str) -> Optional[str]:
        """
        Resolve dimension name to table.column.

        Args:
            dim_name: Dimension name (e.g., 'brand_name', 'state_name')

        Returns:
            Column reference with table alias (e.g., 'p.brand_name')
        """
        # Map dimension to table.column
        dimension_mapping = {
            # Date dimensions
            'date': 'd.date',
            'year': 'd.year',
            'quarter': 'd.quarter',
            'month': 'd.month',
            'month_name': 'd.month_name',
            'week': 'd.week',
            'day_name': 'd.day_name',
            'fiscal_year': 'd.fiscal_year',
            'fiscal_quarter': 'd.fiscal_quarter',
            'fiscal_week': 'd.fiscal_week',
            'season': 'd.season',

            # Product dimensions
            'brand_name': 'p.brand_name',
            'brand_code': 'p.brand_code',
            'category_name': 'p.category_name',
            'sku_name': 'p.sku_name',
            'sku_code': 'p.sku_code',
            'pack_size': 'p.pack_size',

            # Geography dimensions (dim_geography only has state/district/town)
            'state_name': 'g.state_name',
            'district_name': 'g.district_name',
            'town_name': 'g.town_name',
            # zone_name and region_name are in dim_sales_hierarchy (alias sh)
            'zone_name': 'sh.zone_name',
            'region_name': 'sh.region_name',

            # Customer dimensions
            'distributor_name': 'c.distributor_name',
            'retailer_name': 'c.retailer_name',
            'outlet_type': 'c.outlet_type',

            # Channel dimensions
            'channel_name': 'ch.channel_name',

            # Sales Hierarchy dimensions
            'so_code': 'sh.so_code',
            'so_name': 'sh.so_name',
            'asm_code': 'sh.asm_code',
            'asm_name': 'sh.asm_name',
            'zsm_code': 'sh.zsm_code',
            'zsm_name': 'sh.zsm_name',
            'nsm_code': 'sh.nsm_code',
            'nsm_name': 'sh.nsm_name',
            'territory_code': 'sh.territory_code',
            'territory_name': 'sh.territory_name',
        }

        return dimension_mapping.get(dim_name)
