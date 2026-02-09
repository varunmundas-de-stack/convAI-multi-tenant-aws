"""
Enhanced LLM-based Intent Parser with dual provider support (Ollama + Claude API)
Outputs SemanticQuery format instead of legacy QueryIntent
"""
import json
import re
import os
from typing import Dict, List, Optional, Union
import ollama

# Import anthropic only if needed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from semantic_layer.schemas import (
    SemanticQuery, MetricRequest, Dimensionality,
    TimeContext, Filter, Sorting, ResultShape, IntentType
)
from semantic_layer.semantic_layer import SemanticLayer
from semantic_layer.anonymizer import AnonymizationMapper


class IntentParserV2:
    """
    Enhanced intent parser that outputs SemanticQuery.
    Supports both Ollama (dev/local) and Claude API (prod).
    """

    def __init__(
        self,
        semantic_layer: SemanticLayer,
        model: str = "llama3.2:3b",
        use_claude: bool = False,
        anonymize_schema: bool = False,
        anonymization_strategy: str = "category"
    ):
        """
        Initialize parser.

        Args:
            semantic_layer: Semantic layer instance
            model: Ollama model name (default: llama3.2:3b)
            use_claude: Whether to use Claude API instead of Ollama
            anonymize_schema: Whether to anonymize schema when sending to external LLM (recommended for production)
            anonymization_strategy: Strategy for anonymization ("generic", "category", or "hash")
        """
        self.semantic_layer = semantic_layer
        self.model = model

        # Check environment variable
        self.use_claude = use_claude or os.getenv("USE_CLAUDE_API", "false").lower() == "true"

        # Anonymization settings
        self.anonymize_schema = anonymize_schema or os.getenv("ANONYMIZE_SCHEMA", "false").lower() == "true"
        self.anonymizer = AnonymizationMapper(strategy=anonymization_strategy) if self.anonymize_schema else None

        if self.use_claude:
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            self.claude_client = anthropic.Anthropic(api_key=api_key)
        else:
            self.claude_client = None

    def parse(self, question: str) -> SemanticQuery:
        """
        Parse user question into SemanticQuery.

        Args:
            question: Natural language question

        Returns:
            SemanticQuery: Structured semantic query

        Raises:
            ValueError: If parsing fails completely
        """
        try:
            if self.use_claude:
                return self._parse_with_claude(question)
            else:
                return self._parse_with_ollama(question)
        except Exception as e:
            print(f"LLM parsing failed: {e}, using fallback")
            return self._fallback_parse(question)

    def _parse_with_ollama(self, question: str) -> SemanticQuery:
        """Parse using local Ollama"""
        prompt = self._build_semantic_prompt(question)

        response = ollama.chat(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self._get_system_prompt()},
                {'role': 'user', 'content': prompt}
            ],
            options={'temperature': 0.1, 'num_predict': 800}
        )

        intent_dict = self._extract_json(response['message']['content'])

        # De-anonymize if needed
        if self.anonymize_schema and self.anonymizer:
            intent_dict = self.anonymizer.deanonymize_semantic_query(intent_dict)

        intent_dict['original_question'] = question

        return SemanticQuery(**intent_dict)

    def _parse_with_claude(self, question: str) -> SemanticQuery:
        """Parse using Claude API for better accuracy"""
        prompt = self._build_semantic_prompt(question)

        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            temperature=0,
            system=self._get_system_prompt(),
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        intent_dict = self._extract_json(response.content[0].text)

        # De-anonymize if needed
        if self.anonymize_schema and self.anonymizer:
            intent_dict = self.anonymizer.deanonymize_semantic_query(intent_dict)

        intent_dict['original_question'] = question

        return SemanticQuery(**intent_dict)

    def _get_system_prompt(self) -> str:
        """System prompt with SemanticQuery schema and domain knowledge"""
        if self.anonymize_schema:
            # Use generic anonymized prompt
            return self._get_anonymized_system_prompt()
        else:
            # Use specific CPG domain prompt
            return self._get_cpg_system_prompt()

    def _get_cpg_system_prompt(self) -> str:
        """CPG-specific system prompt with real metric/dimension names"""
        return """You are a CPG/Sales analytics expert. Extract structured semantic queries from business questions.

Output ONLY valid JSON matching this schema:

{
  "intent": "trend | comparison | ranking | diagnostic | snapshot",
  "metric_request": {
    "primary_metric": "secondary_sales_value",
    "secondary_metrics": [],
    "metric_variant": "absolute"
  },
  "dimensionality": {
    "group_by": ["week", "brand_name"]
  },
  "time_context": {
    "time_dimension": "invoice_date",
    "window": "last_4_weeks",
    "grain": "week"
  },
  "filters": [
    {"dimension": "state_name", "operator": "=", "values": ["Tamil Nadu"]}
  ],
  "sorting": {
    "order_by": "secondary_sales_value",
    "direction": "DESC",
    "limit": 10
  },
  "result_shape": {
    "format": "chart",
    "chart_type": "line"
  },
  "confidence": 0.95
}

**CPG/Sales Metrics:**
- secondary_sales_value: Net invoiced value to retailers (₹)
- secondary_sales_volume: Total units sold
- gross_sales_value: Gross sales before discounts
- discount_amount: Total discounts given
- margin_amount: Total margin earned
- invoice_count: Number of invoices
- return_value: Value of returns
- active_outlets: Outlets with sales
- average_selling_price: Price per unit

**Dimensions:**
- Product: category_name, brand_name, sku_name, pack_size
- Geography: zone_name, state_name, district_name, town_name, outlet_name
- Customer: distributor_name, retailer_name, outlet_type
- Channel: channel_name (GT, MT, E-Com, IWS, Pharma)
- Date: year, quarter, month, month_name, week, fiscal_year, fiscal_quarter, season

**Time Windows:**
last_4_weeks, last_6_weeks, last_12_weeks, mtd, qtd, ytd, this_month, last_month, this_year, last_year

**Intent Types:**
- snapshot: Single point-in-time aggregate (e.g., "total sales this month")
- trend: Time-series over multiple periods (e.g., "sales by week")
- comparison: Period-over-period (e.g., "this month vs last month")
- ranking: Top/bottom N (e.g., "top 10 brands")
- diagnostic: Root cause analysis (e.g., "why did sales drop")

**Examples:**

Q: "Show sales by brand for last 4 weeks"
A: {"intent": "trend", "metric_request": {"primary_metric": "secondary_sales_value"}, "dimensionality": {"group_by": ["brand_name"]}, "time_context": {"window": "last_4_weeks"}}

Q: "Top 10 SKUs by volume this month"
A: {"intent": "ranking", "metric_request": {"primary_metric": "secondary_sales_volume"}, "dimensionality": {"group_by": ["sku_name"]}, "time_context": {"window": "this_month"}, "sorting": {"order_by": "secondary_sales_volume", "direction": "DESC", "limit": 10}}

Q: "Top distributors by sales value"
A: {"intent": "ranking", "metric_request": {"primary_metric": "secondary_sales_value"}, "dimensionality": {"group_by": ["distributor_name"]}, "time_context": {"window": "last_4_weeks"}, "sorting": {"order_by": "secondary_sales_value", "direction": "DESC", "limit": 10}}

Q: "Compare sales by channel"
A: {"intent": "comparison", "metric_request": {"primary_metric": "secondary_sales_value"}, "dimensionality": {"group_by": ["channel_name"]}, "time_context": {"window": "last_4_weeks"}}

Q: "Sales trend by week in Tamil Nadu"
A: {"intent": "trend", "metric_request": {"primary_metric": "secondary_sales_value"}, "dimensionality": {"group_by": ["week"]}, "time_context": {"window": "last_12_weeks", "grain": "week"}, "filters": [{"dimension": "state_name", "operator": "=", "values": ["Tamil Nadu"]}]}

Q: "Why did sales drop?"
A: {"intent": "diagnostic", "metric_request": {"primary_metric": "secondary_sales_value"}, "dimensionality": {"group_by": []}, "time_context": {"window": "last_4_weeks"}, "diagnostics": {"enabled": true, "dimensions": ["brand_name", "state_name", "channel_name"]}}

CRITICAL: When users ask for "top X", "compare", or mention a dimension (brands, channels, distributors, SKUs, states, etc.), ALWAYS include that dimension in group_by. Without group_by, the query will return a single total instead of the breakdown requested.

Now parse the user's question and respond ONLY with JSON:"""

    def _get_anonymized_system_prompt(self) -> str:
        """Generic anonymized system prompt - no real schema names exposed"""
        return """You are a business analytics expert. Extract structured semantic queries from business questions.

Output ONLY valid JSON matching this schema:

{
  "intent": "trend | comparison | ranking | diagnostic | snapshot",
  "metric_request": {
    "primary_metric": "value_metric_001",
    "secondary_metrics": [],
    "metric_variant": "absolute"
  },
  "dimensionality": {
    "group_by": ["time_dimension_001", "product_dimension_001"]
  },
  "time_context": {
    "time_dimension": "invoice_date",
    "window": "last_4_weeks",
    "grain": "week"
  },
  "filters": [
    {"dimension": "geography_dimension_001", "operator": "=", "values": ["Value1"]}
  ],
  "sorting": {
    "order_by": "value_metric_001",
    "direction": "DESC",
    "limit": 10
  },
  "result_shape": {
    "format": "chart",
    "chart_type": "line"
  },
  "confidence": 0.95
}

**Metric Categories:**
- value_metric_*: Monetary value measurements
- volume_metric_*: Quantity measurements
- ratio_metric_*: Calculated ratios and percentages
- count_metric_*: Count of items
- average_metric_*: Average calculations

**Dimension Categories:**
- time_dimension_*: Time period attributes (year, quarter, month, week, day)
- product_dimension_*: Product hierarchy attributes
- geography_dimension_*: Geographic location attributes
- customer_dimension_*: Customer relationship attributes
- channel_dimension_*: Sales channel attributes

**Time Windows:**
last_4_weeks, last_6_weeks, last_12_weeks, mtd, qtd, ytd, this_month, last_month, this_year, last_year

**Intent Types:**
- snapshot: Single point-in-time aggregate (e.g., "total value this month")
- trend: Time-series over multiple periods (e.g., "value by week")
- comparison: Period-over-period (e.g., "this month vs last month")
- ranking: Top/bottom N (e.g., "top 10 by value")
- diagnostic: Root cause analysis (e.g., "why did value drop")

**Examples:**

Q: "Show value by product for last 4 weeks"
A: {"intent": "trend", "metric_request": {"primary_metric": "value_metric_001"}, "dimensionality": {"group_by": ["product_dimension_001"]}, "time_context": {"window": "last_4_weeks"}}

Q: "Top 10 items by volume this month"
A: {"intent": "ranking", "metric_request": {"primary_metric": "volume_metric_001"}, "dimensionality": {"group_by": ["product_dimension_002"]}, "time_context": {"window": "this_month"}, "sorting": {"order_by": "volume_metric_001", "direction": "DESC", "limit": 10}}

Q: "Compare value by channel"
A: {"intent": "comparison", "metric_request": {"primary_metric": "value_metric_001"}, "dimensionality": {"group_by": ["channel_dimension_001"]}, "time_context": {"window": "last_4_weeks"}}

CRITICAL: When users ask for "top X", "compare", or mention breaking down by category, ALWAYS include appropriate dimensions in group_by. Use the metric/dimension names provided in the "Available Metrics" and "Available Dimensions" lists.

Now parse the user's question and respond ONLY with JSON:"""

    def _build_semantic_prompt(self, question: str) -> str:
        """Build prompt for semantic query extraction"""
        # Get available metrics/dimensions
        metrics_info = self.semantic_layer.list_available_metrics()
        dimensions_info = self.semantic_layer.list_available_dimensions()

        # Anonymize if enabled
        if self.anonymize_schema and self.anonymizer:
            metrics_info, _ = self.anonymizer.anonymize_metrics(metrics_info)
            dimensions_info, _ = self.anonymizer.anonymize_dimensions(dimensions_info)

        return f"""User Question: "{question}"

Available Metrics: {', '.join([m['name'] for m in metrics_info[:10]])}
Available Dimensions: {', '.join([d['name'] for d in dimensions_info[:10]])}

Parse into SemanticQuery JSON:"""

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response"""
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")

        # Fallback empty structure
        return {
            'intent': 'snapshot',
            'metric_request': {
                'primary_metric': 'secondary_sales_value'
            },
            'dimensionality': {'group_by': []},
            'time_context': {'window': 'last_4_weeks'},
            'filters': [],
            'confidence': 0.5
        }

    def _fallback_parse(self, question: str) -> SemanticQuery:
        """
        Fallback keyword-based parsing if LLM fails.
        Returns basic SemanticQuery.
        """
        question_lower = question.lower()

        # Detect intent
        intent = IntentType.SNAPSHOT
        if any(word in question_lower for word in ['trend', 'over time', 'by week', 'by month']):
            intent = IntentType.TREND
        elif any(word in question_lower for word in ['top', 'bottom', 'best', 'worst']):
            intent = IntentType.RANKING
        elif any(word in question_lower for word in ['why', 'reason', 'cause', 'drop', 'increase']):
            intent = IntentType.DIAGNOSTIC

        # Detect primary metric
        primary_metric = "secondary_sales_value"
        if any(word in question_lower for word in ['volume', 'units', 'quantity']):
            primary_metric = "secondary_sales_volume"
        elif any(word in question_lower for word in ['margin', 'profit']):
            primary_metric = "margin_amount"
        elif any(word in question_lower for word in ['invoice', 'bills']):
            primary_metric = "invoice_count"

        # Detect grouping
        group_by = []
        if any(word in question_lower for word in ['by brand', 'per brand', 'brand']):
            group_by.append('brand_name')
        if any(word in question_lower for word in ['by state', 'per state']):
            group_by.append('state_name')
        if any(word in question_lower for word in ['by week', 'weekly']):
            group_by.append('week')
        if any(word in question_lower for word in ['by month', 'monthly']):
            group_by.append('month_name')
        if any(word in question_lower for word in ['by category', 'categor']):
            group_by.append('category_name')
        if any(word in question_lower for word in ['by channel', 'per channel', 'channel']):
            group_by.append('channel_name')
        if any(word in question_lower for word in ['distributor']):
            group_by.append('distributor_name')
        if any(word in question_lower for word in ['sku', 'product']):
            group_by.append('sku_name')
        if any(word in question_lower for word in ['retailer', 'by retailer']):
            group_by.append('retailer_name')
        if any(word in question_lower for word in ['by zone', 'zone']):
            group_by.append('zone_name')
        if any(word in question_lower for word in ['by district', 'district']):
            group_by.append('district_name')

        # Special case: "compare" usually means grouping by the dimension mentioned
        if 'compare' in question_lower and not group_by:
            # Try to find what to compare by
            if 'channel' in question_lower:
                group_by.append('channel_name')
            elif 'brand' in question_lower:
                group_by.append('brand_name')
            elif 'state' in question_lower:
                group_by.append('state_name')
            elif 'distributor' in question_lower:
                group_by.append('distributor_name')

        # Detect time window
        window = "last_4_weeks"
        if 'this month' in question_lower:
            window = "this_month"
        elif 'last month' in question_lower:
            window = "last_month"
        elif '6 weeks' in question_lower:
            window = "last_6_weeks"
        elif '12 weeks' in question_lower:
            window = "last_12_weeks"

        # Detect limit
        limit = None
        limit_match = re.search(r'top (\d+)', question_lower)
        if limit_match:
            limit = int(limit_match.group(1))

        # Build sorting if ranking
        sorting = None
        if intent == IntentType.RANKING or limit:
            sorting = Sorting(
                order_by=primary_metric,
                direction="DESC",
                limit=limit or 10
            )

        return SemanticQuery(
            intent=intent,
            metric_request=MetricRequest(primary_metric=primary_metric),
            dimensionality=Dimensionality(group_by=group_by),
            time_context=TimeContext(window=window),
            filters=[],
            sorting=sorting,
            confidence=0.6,
            original_question=question
        )

    def generate_natural_response(
        self,
        question: str,
        results: List[Dict],
        sql_query: str
    ) -> str:
        """
        Generate natural language response from query results.

        Args:
            question: Original question
            results: Query results
            sql_query: Generated SQL

        Returns:
            Natural language response
        """
        if not results:
            return "I couldn't find any data matching your question."

        # Prepare results summary
        results_summary = self._summarize_results(results)

        prompt = f"""User asked: "{question}"

Query Results (top {min(len(results), 10)} rows):
{results_summary}

Total rows: {len(results)}

Generate a concise, insightful response (max 100 words) with:
- Direct answer to the question
- Key numbers and insights
- Business-friendly language (no SQL jargon)"""

        try:
            if self.use_claude:
                response = self.claude_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=200,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text.strip()
            else:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {
                            'role': 'system',
                            'content': 'You are a helpful data analyst. Provide clear, concise answers with specific numbers.'
                        },
                        {'role': 'user', 'content': prompt}
                    ],
                    options={'temperature': 0.3, 'num_predict': 200}
                )
                return response['message']['content'].strip()

        except Exception as e:
            print(f"Error generating response: {e}")
            return self._simple_summary(results)

    def _summarize_results(self, results: List[Dict], max_rows: int = 10) -> str:
        """Create text summary of results"""
        if not results:
            return "No data"

        summary_lines = []
        for i, row in enumerate(results[:max_rows], 1):
            row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
            summary_lines.append(f"{i}. {row_str}")

        return "\n".join(summary_lines)

    def _simple_summary(self, results: List[Dict]) -> str:
        """Generate simple summary without LLM"""
        if not results:
            return "No data found."

        summary = f"Found {len(results)} result(s). "

        if results:
            first_row = results[0]
            summary += "Sample: " + ", ".join([f"{k}={v}" for k, v in first_row.items()])

        return summary
