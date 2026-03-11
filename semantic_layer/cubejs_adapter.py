"""
CubeJSAdapter — translates a SemanticQuery into a Cube.js REST query and
executes it against the Cube.js API.

This replaces the query_builder + executor pipeline for non-diagnostic queries.
Diagnostic queries still delegate to the orchestrator (which chains multiple
CubeJSAdapter calls internally).
"""
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from semantic_layer.schemas import SemanticQuery, IntentType, Filter

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Metric → Cube.js member mappings
# ──────────────────────────────────────────────────────────────────────────────
METRIC_TO_MEASURE: dict[str, str] = {
    'secondary_sales_value':  'FactSecondarySales.secondary_sales_value',
    'secondary_sales_volume': 'FactSecondarySales.secondary_sales_volume',
    'gross_sales_value':      'FactSecondarySales.gross_sales_value',
    'discount_amount':        'FactSecondarySales.discount_amount',
    'margin_amount':          'FactSecondarySales.margin_amount',
    'invoice_count':          'FactSecondarySales.invoice_count',
    # Common aliases
    'sales':    'FactSecondarySales.secondary_sales_value',
    'revenue':  'FactSecondarySales.secondary_sales_value',
    'volume':   'FactSecondarySales.secondary_sales_volume',
    'units':    'FactSecondarySales.secondary_sales_volume',
    'margin':   'FactSecondarySales.margin_amount',
    'discount': 'FactSecondarySales.discount_amount',
    'invoices': 'FactSecondarySales.invoice_count',
}

# Dimension column → Cube.js member
DIMENSION_TO_MEMBER: dict[str, str] = {
    # Product
    'brand_name':    'DimProduct.brand_name',
    'category_name': 'DimProduct.category_name',
    'sku_name':      'DimProduct.sku_name',
    'pack_size':     'DimProduct.pack_size',
    # Geography (dim_geography only has state/district/town)
    'state_name':    'DimGeography.state_name',
    'district_name': 'DimGeography.district_name',
    'town_name':     'DimGeography.town_name',
    # Customer
    'distributor_name': 'DimCustomer.distributor_name',
    'retailer_name':    'DimCustomer.retailer_name',
    'outlet_type':      'DimCustomer.outlet_type',
    # Channel
    'channel_name': 'DimChannel.channel_name',
    # Date grains
    'year':       'DimDate.year',
    'quarter':    'DimDate.quarter',
    'month':      'DimDate.month',
    'month_name': 'DimDate.month_name',
    'week':       'DimDate.week',
    'date':       'FactSecondarySales.invoice_date',
    # Sales hierarchy
    'so_code':  'DimSalesHierarchy.so_code',
    'so_name':  'DimSalesHierarchy.so_name',
    'asm_code': 'DimSalesHierarchy.asm_code',
    'asm_name': 'DimSalesHierarchy.asm_name',
    'zsm_code': 'DimSalesHierarchy.zsm_code',
    'zsm_name': 'DimSalesHierarchy.zsm_name',
    'nsm_code': 'DimSalesHierarchy.nsm_code',
    'nsm_name': 'DimSalesHierarchy.nsm_name',
    # Zone/region are in dim_sales_hierarchy, not dim_geography
    'zone_name':   'DimSalesHierarchy.zone_name',
    'region_name': 'DimSalesHierarchy.region_name',
}

# SemanticQuery filter operator → Cube.js filter operator
FILTER_OP_MAP: dict[str, str] = {
    '=':       'equals',
    'IN':      'equals',
    'NOT IN':  'notEquals',
    '>':       'gt',
    '<':       'lt',
    '>=':      'gte',
    '<=':      'lte',
    'BETWEEN': 'inDateRange',  # for date ranges
}

# time_context.window → relative date range understood by Cube.js
TIME_WINDOW_MAP: dict[str, str] = {
    'this_month':   'this month',
    'last_month':   'last month',
    'this_quarter':  'this quarter',
    'last_quarter':  'last quarter',
    'last_2_weeks':  'last 2 weeks',
    'last_3_months': 'last 3 months',
    'last_6_months': 'last 6 months',
    'this_year':    'this year',
    'last_year':    'last year',
    'last_4_weeks': 'last 4 weeks',
    'last_6_weeks': 'last 6 weeks',
    'last_week':    'last week',
    'last_7_days':  'last 7 days',
    'last_30_days': 'last 30 days',
    'last_90_days': 'last 90 days',
    'mtd':          'this month',
    'ytd':          'this year',
}


class CubeJSAdapter:
    """
    Converts SemanticQuery → Cube.js query JSON and executes it via REST API.

    Usage:
        adapter = CubeJSAdapter()
        cube_query = adapter.build_query(semantic_query)
        result     = adapter.execute(cube_query, cubejs_token)
    """

    def __init__(self, cubejs_url: str | None = None):
        self.base_url = (cubejs_url or os.getenv('CUBEJS_URL', 'http://cubejs:4000')).rstrip('/')

    # ──────────────────────────────────────────────────────────────────────────
    # Public: build Cube.js query JSON from SemanticQuery
    # ──────────────────────────────────────────────────────────────────────────
    def build_query(self, semantic_query: SemanticQuery) -> dict[str, Any]:
        """
        Translate a SemanticQuery into a Cube.js /load query object.

        Returns a dict ready to POST to  /cubejs-api/v1/load  {"query": <dict>}
        """
        measures    = self._build_measures(semantic_query)
        dimensions  = self._build_dimensions(semantic_query)
        time_dims   = self._build_time_dimensions(semantic_query)
        filters     = self._build_filters(semantic_query.filters)
        order       = self._build_order(semantic_query)
        limit       = self._build_limit(semantic_query)

        cube_query: dict[str, Any] = {
            'measures':        measures,
            'dimensions':      dimensions,
            'timeDimensions':  time_dims,
            'filters':         filters,
        }
        if order:
            cube_query['order'] = order
        if limit:
            cube_query['limit'] = limit

        log.debug('Built Cube.js query: %s', json.dumps(cube_query, indent=2))
        return cube_query

    # ──────────────────────────────────────────────────────────────────────────
    # Public: execute a pre-built Cube.js query
    # ──────────────────────────────────────────────────────────────────────────
    def execute(self, cube_query: dict[str, Any], token: str) -> dict[str, Any]:
        """
        POST to Cube.js /cubejs-api/v1/load and return normalised result.

        Returns:
            {
              'results': [ {...row...}, ... ],
              'sql':     '<annotated SQL from Cube.js or empty string>',
              'meta':    { ... }
            }

        Raises:
            CubeJSError on non-200 or Cube.js error payload.
        """
        url = f'{self.base_url}/cubejs-api/v1/load'
        headers = {
            'Authorization': token,
            'Content-Type':  'application/json',
        }
        payload = {'query': cube_query}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise CubeJSError(f'Cube.js request failed: {exc}') from exc

        if resp.status_code != 200:
            raise CubeJSError(
                f'Cube.js returned HTTP {resp.status_code}: {resp.text[:300]}'
            )

        body = resp.json()
        if 'error' in body:
            raise CubeJSError(f'Cube.js error: {body["error"]}')

        # Normalise: flatten the member-prefixed keys (e.g. "DimProduct.brand_name" → "brand_name")
        raw_rows = body.get('data', [])
        rows = [_flatten_row(r) for r in raw_rows]

        return {
            'results': rows,
            'sql':     '',   # Cube.js doesn't return SQL in /load; use /sql endpoint if needed
            'meta':    body.get('annotation', {}),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _build_measures(self, sq: SemanticQuery) -> list[str]:
        measures = []
        primary = METRIC_TO_MEASURE.get(sq.metric_request.primary_metric)
        if primary:
            measures.append(primary)
        for m in sq.metric_request.secondary_metrics:
            member = METRIC_TO_MEASURE.get(m)
            if member:
                measures.append(member)
        if not measures:
            # Default fallback
            measures.append('FactSecondarySales.secondary_sales_value')
        return measures

    def _build_dimensions(self, sq: SemanticQuery) -> list[str]:
        dims = []
        for d in sq.dimensionality.group_by:
            member = DIMENSION_TO_MEMBER.get(d)
            if member and not member.startswith('FactSecondarySales.invoice_date'):
                # invoice_date goes in timeDimensions, not dimensions
                dims.append(member)
        return dims

    def _build_time_dimensions(self, sq: SemanticQuery) -> list[dict]:
        date_range = _resolve_time_window(sq.time_context.window)
        grain = sq.time_context.grain or 'day'

        # Map SemanticQuery grain to Cube.js granularity string
        grain_map = {
            'day':     'day',
            'week':    'week',
            'month':   'month',
            'quarter': 'quarter',
            'year':    'year',
        }
        granularity = grain_map.get(grain, 'day')

        # Check if the group_by includes a date-level dimension (week/month/year)
        # and adjust granularity accordingly
        for d in sq.dimensionality.group_by:
            if d in ('week', 'week_label'):
                granularity = 'week'
                break
            if d in ('month', 'month_name'):
                granularity = 'month'
                break
            if d == 'quarter':
                granularity = 'quarter'
                break
            if d == 'year':
                granularity = 'year'
                break

        time_dim: dict[str, Any] = {
            'dimension': 'FactSecondarySales.invoice_date',
            'granularity': granularity,
        }

        if isinstance(date_range, list):
            time_dim['dateRange'] = date_range       # ['2024-01-01', '2024-03-31']
        elif isinstance(date_range, str):
            time_dim['dateRange'] = date_range       # 'last 4 weeks'

        return [time_dim]

    def _build_filters(self, filters: list[Filter]) -> list[dict]:
        cube_filters = []
        for f in filters:
            member = DIMENSION_TO_MEMBER.get(f.dimension)
            if not member:
                log.warning('Unknown filter dimension: %s — skipped', f.dimension)
                continue
            op = FILTER_OP_MAP.get(f.operator, 'equals')
            cube_filters.append({
                'member':   member,
                'operator': op,
                'values':   [str(v) for v in f.values],
            })
        return cube_filters

    def _build_order(self, sq: SemanticQuery) -> dict | None:
        if not sq.sorting:
            return None
        member = (
            METRIC_TO_MEASURE.get(sq.sorting.order_by)
            or DIMENSION_TO_MEMBER.get(sq.sorting.order_by)
        )
        if not member:
            return None
        direction = sq.sorting.direction.lower()  # 'asc' or 'desc'
        return {member: direction}

    def _build_limit(self, sq: SemanticQuery) -> int | None:
        if sq.sorting and sq.sorting.limit:
            return sq.sorting.limit
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_time_window(window: str) -> str | list[str]:
    """
    Convert a SemanticQuery time window to a Cube.js dateRange value.
    Returns either a Cube.js relative string ('last 4 weeks') or an ISO pair.
    """
    if window in TIME_WINDOW_MAP:
        return TIME_WINDOW_MAP[window]

    import re
    # Numeric offset: last_N_weeks / last_N_days / last_N_months
    m = re.match(r'last_(\d+)_(day|week|month)s?', window)
    if m:
        n, grain = m.group(1), m.group(2)
        return f'last {n} {grain}s'

    # Specific quarter+year: q4_2025, 2025_q4, q42025, q4-2025, etc.
    m = re.match(r'q([1-4])[\W_]?(\d{4})|(\d{4})[\W_]?q([1-4])', window)
    if m:
        q  = int(m.group(1) or m.group(4))
        yr = int(m.group(2) or m.group(3))
        q_months = {1: (1, 3, 31), 2: (4, 6, 30), 3: (7, 9, 30), 4: (10, 12, 31)}
        sm, em, ed = q_months[q]
        return [f'{yr}-{sm:02d}-01', f'{yr}-{em:02d}-{ed:02d}']

    # Year only: 2025, year_2025, this_2025
    m = re.search(r'\b(20\d{2})\b', window)
    if m:
        yr = m.group(1)
        return [f'{yr}-01-01', f'{yr}-12-31']

    # Unknown — default to last 4 weeks
    log.warning('Unknown time window %r — defaulting to last 4 weeks', window)
    return 'last 4 weeks'


def _flatten_row(row: dict) -> dict:
    """
    Cube.js returns rows with fully-qualified keys like "DimProduct.brand_name".
    Flatten them to just the column name ("brand_name") for compatibility with
    the existing Flask response-formatting functions.
    """
    flat = {}
    for key, value in row.items():
        short_key = key.split('.')[-1] if '.' in key else key
        flat[short_key] = value
    return flat


class CubeJSError(Exception):
    """Raised when the Cube.js API returns an error."""
