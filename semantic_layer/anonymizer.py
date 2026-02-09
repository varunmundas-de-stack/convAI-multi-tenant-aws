"""
Anonymization layer for protecting schema metadata when using external LLMs.

Converts real metric/dimension names to generic anonymized names before sending to LLM,
then maps responses back to real names for local processing.
"""
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AnonymizedMetric:
    """Anonymized metric representation"""
    anonymous_name: str
    anonymous_description: str
    real_name: str
    real_description: str
    category: str  # e.g., "value", "volume", "count"


@dataclass
class AnonymizedDimension:
    """Anonymized dimension representation"""
    anonymous_name: str
    anonymous_description: str
    real_name: str
    real_description: str
    hierarchy_level: str  # e.g., "level1", "level2"


class AnonymizationMapper:
    """
    Maps real metric/dimension names to anonymized versions and back.

    Strategies:
    1. Generic numbered naming (metric_001, dimension_001)
    2. Category-based naming (value_metric_001, time_dimension_001)
    3. Hash-based naming (for consistency across sessions)
    """

    def __init__(self, strategy: str = "category"):
        """
        Initialize anonymization mapper.

        Args:
            strategy: "generic", "category", or "hash"
        """
        self.strategy = strategy
        self.metric_map: Dict[str, AnonymizedMetric] = {}
        self.dimension_map: Dict[str, AnonymizedDimension] = {}
        self.reverse_metric_map: Dict[str, str] = {}
        self.reverse_dimension_map: Dict[str, str] = {}

    def anonymize_metrics(
        self,
        metrics: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
        """
        Anonymize metric names and descriptions.

        Args:
            metrics: List of dicts with 'name' and 'description'

        Returns:
            Tuple of (anonymized_metrics, mapping_dict)
        """
        anonymized = []

        for idx, metric in enumerate(metrics, 1):
            real_name = metric['name']
            real_desc = metric['description']

            # Determine category from description/name
            category = self._categorize_metric(real_name, real_desc)

            # Generate anonymous name
            if self.strategy == "generic":
                anon_name = f"metric_{idx:03d}"
            elif self.strategy == "category":
                anon_name = f"{category}_metric_{idx:03d}"
            elif self.strategy == "hash":
                anon_name = f"metric_{self._hash_name(real_name)}"
            else:
                anon_name = f"metric_{idx:03d}"

            # Generate anonymous description
            anon_desc = self._anonymize_metric_description(real_desc, category)

            # Store mapping
            self.metric_map[real_name] = AnonymizedMetric(
                anonymous_name=anon_name,
                anonymous_description=anon_desc,
                real_name=real_name,
                real_description=real_desc,
                category=category
            )
            self.reverse_metric_map[anon_name] = real_name

            anonymized.append({
                'name': anon_name,
                'description': anon_desc
            })

        return anonymized, self.reverse_metric_map

    def anonymize_dimensions(
        self,
        dimensions: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
        """
        Anonymize dimension names.

        Args:
            dimensions: List of dicts with 'name', 'table', 'attributes'

        Returns:
            Tuple of (anonymized_dimensions, mapping_dict)
        """
        anonymized = []

        for idx, dimension in enumerate(dimensions, 1):
            real_name = dimension['name']

            # Determine hierarchy level
            hierarchy = self._categorize_dimension(real_name)

            # Generate anonymous name
            if self.strategy == "generic":
                anon_name = f"dimension_{idx:03d}"
            elif self.strategy == "category":
                anon_name = f"{hierarchy}_dimension_{idx:03d}"
            elif self.strategy == "hash":
                anon_name = f"dimension_{self._hash_name(real_name)}"
            else:
                anon_name = f"dimension_{idx:03d}"

            anon_desc = self._anonymize_dimension_description(real_name, hierarchy)

            # Store mapping
            self.dimension_map[real_name] = AnonymizedDimension(
                anonymous_name=anon_name,
                anonymous_description=anon_desc,
                real_name=real_name,
                real_description="",
                hierarchy_level=hierarchy
            )
            self.reverse_dimension_map[anon_name] = real_name

            anonymized.append({
                'name': anon_name,
                'description': anon_desc
            })

        return anonymized, self.reverse_dimension_map

    def deanonymize_semantic_query(self, semantic_query_dict: Dict) -> Dict:
        """
        Convert anonymized metric/dimension names back to real names in SemanticQuery dict.

        Args:
            semantic_query_dict: Dict representation of SemanticQuery with anonymous names

        Returns:
            Dict with real names restored
        """
        result = semantic_query_dict.copy()

        # Deanonymize primary metric
        if 'metric_request' in result:
            metric_req = result['metric_request']
            if 'primary_metric' in metric_req:
                anon_name = metric_req['primary_metric']
                if anon_name in self.reverse_metric_map:
                    metric_req['primary_metric'] = self.reverse_metric_map[anon_name]

            # Deanonymize secondary metrics
            if 'secondary_metrics' in metric_req:
                metric_req['secondary_metrics'] = [
                    self.reverse_metric_map.get(m, m)
                    for m in metric_req['secondary_metrics']
                ]

        # Deanonymize dimensions in group_by
        if 'dimensionality' in result:
            dim_spec = result['dimensionality']
            if 'group_by' in dim_spec:
                dim_spec['group_by'] = [
                    self.reverse_dimension_map.get(d, d)
                    for d in dim_spec['group_by']
                ]

        # Deanonymize filters
        if 'filters' in result:
            for filter_obj in result['filters']:
                if 'dimension' in filter_obj:
                    anon_dim = filter_obj['dimension']
                    if anon_dim in self.reverse_dimension_map:
                        filter_obj['dimension'] = self.reverse_dimension_map[anon_dim]

        # Deanonymize sorting
        if 'sorting' in result and result['sorting']:
            if 'order_by' in result['sorting']:
                order_field = result['sorting']['order_by']
                # Could be metric or dimension
                if order_field in self.reverse_metric_map:
                    result['sorting']['order_by'] = self.reverse_metric_map[order_field]
                elif order_field in self.reverse_dimension_map:
                    result['sorting']['order_by'] = self.reverse_dimension_map[order_field]

        return result

    def _categorize_metric(self, name: str, description: str) -> str:
        """Categorize metric by type for better anonymization"""
        text = (name + " " + description).lower()

        # Check count first (more specific)
        if any(word in text for word in ['count', 'number']) and not any(word in text for word in ['account', 'discount']):
            return "count"
        elif any(word in text for word in ['rate', 'percentage', 'ratio']):
            return "ratio"
        elif any(word in text for word in ['average', 'mean', 'avg']):
            return "average"
        elif any(word in text for word in ['volume', 'quantity', 'units', 'qty']):
            return "volume"
        elif any(word in text for word in ['value', 'amount', 'revenue', 'sales', 'margin', 'profit']):
            return "value"
        else:
            return "metric"

    def _categorize_dimension(self, name: str) -> str:
        """Categorize dimension by hierarchy level"""
        name_lower = name.lower()

        if any(word in name_lower for word in ['date', 'time', 'year', 'month', 'week', 'quarter']):
            return "time"
        elif any(word in name_lower for word in ['product', 'brand', 'sku', 'category', 'item']):
            return "product"
        elif any(word in name_lower for word in ['geography', 'location', 'state', 'city', 'region', 'zone', 'district', 'town']):
            return "geography"
        elif any(word in name_lower for word in ['customer', 'distributor', 'retailer', 'outlet']):
            return "customer"
        elif any(word in name_lower for word in ['channel', 'sales']):
            return "channel"
        else:
            return "attribute"

    def _anonymize_metric_description(self, description: str, category: str) -> str:
        """Create generic description for metric"""
        templates = {
            "value": "Monetary value measurement",
            "volume": "Quantity measurement",
            "ratio": "Calculated ratio or percentage",
            "count": "Count of items",
            "average": "Average value calculation",
            "metric": "Business metric measurement"
        }
        return templates.get(category, "Business metric")

    def _anonymize_dimension_description(self, name: str, hierarchy: str) -> str:
        """Create generic description for dimension"""
        templates = {
            "time": "Time period attribute",
            "product": "Product hierarchy attribute",
            "geography": "Geographic location attribute",
            "customer": "Customer relationship attribute",
            "channel": "Sales channel attribute",
            "attribute": "Descriptive attribute"
        }
        return templates.get(hierarchy, "Data dimension")

    def _hash_name(self, name: str) -> str:
        """Create consistent hash for name"""
        return hashlib.md5(name.encode()).hexdigest()[:8]

    def get_anonymization_summary(self) -> Dict[str, int]:
        """Get summary of anonymization mapping"""
        return {
            "metrics_mapped": len(self.metric_map),
            "dimensions_mapped": len(self.dimension_map),
            "strategy": self.strategy
        }

    def export_mapping(self) -> Dict:
        """Export mapping for audit/debugging purposes"""
        return {
            "metrics": {
                anon.anonymous_name: anon.real_name
                for anon in self.metric_map.values()
            },
            "dimensions": {
                anon.anonymous_name: anon.real_name
                for anon in self.dimension_map.values()
            }
        }
