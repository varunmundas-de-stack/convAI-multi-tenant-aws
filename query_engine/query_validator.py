"""
Query Validation System
Detects overly broad questions and prompts for clarifications
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of query validation"""
    is_valid: bool
    is_too_broad: bool
    missing_context: List[str]
    suggestions: List[str]
    refined_question: Optional[str] = None


class QueryValidator:
    """
    Validates user queries and suggests refinements
    """

    # Patterns that indicate broad/vague questions
    BROAD_PATTERNS = [
        r'^(show|get|give|tell)\s+(me\s+)?(all|everything|anything|data)',
        r'^(show|get|give)\s+\w+\s*$',  # "show brands", "get data" (2 words only)
        r'^what\s+(is|are)\s+\w+\s*$',  # "what is sales", "what are trends"
        r'^how\s+much\s*$',
        r'^how\s+many\s*$',
        r'^\w+\s*\?*$',  # Single word questions
    ]

    # Context dimensions that should be specified
    CONTEXT_DIMENSIONS = {
        'time': {
            'keywords': ['when', 'time', 'date', 'period', 'year', 'month', 'week', 'day', 'quarter'],
            'question': "Which time period are you interested in?",
            'options': [
                "Today",
                "This week",
                "This month",
                "This quarter",
                "This year",
                "Last 30 days",
                "Last 90 days",
                "Custom date range"
            ]
        },
        'sales_type': {
            'keywords': ['sales', 'revenue', 'transactions'],
            'question': "Which type of sales data?",
            'options': [
                "Primary sales (Company → Distributor)",
                "Secondary sales (Distributor → Retailer)",
                "Both primary and secondary"
            ]
        },
        'product': {
            'keywords': ['product', 'sku', 'item', 'brand', 'category'],
            'question': "Which products or categories?",
            'options': [
                "All products",
                "Specific brand",
                "Specific category",
                "Specific SKU",
                "Top N products"
            ]
        },
        'geography': {
            'keywords': ['where', 'location', 'region', 'state', 'city', 'zone'],
            'question': "Which geography?",
            'options': [
                "All regions",
                "Specific zone",
                "Specific state",
                "Specific city",
                "My territory only"
            ]
        },
        'customer': {
            'keywords': ['customer', 'client', 'distributor', 'retailer'],
            'question': "Which customers?",
            'options': [
                "All customers",
                "Specific customer segment",
                "Top N customers",
                "New customers",
                "Active customers only"
            ]
        }
    }

    def __init__(self):
        self.validation_cache = {}

    def validate_query(self, question: str, context: Dict = None) -> ValidationResult:
        """
        Validate user query and check if it needs refinement

        Args:
            question: User question
            context: Optional context (user info, previous queries, etc.)

        Returns:
            ValidationResult with validation details
        """
        question = question.strip()

        # Check cache
        cache_key = f"{question}:{str(context)}"
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]

        # Check if question is too broad
        is_too_broad = self._is_too_broad(question)

        # Identify missing context
        missing_context = self._identify_missing_context(question, context)

        # Generate suggestions
        suggestions = self._generate_suggestions(question, missing_context)

        # Try to refine question
        refined = self._suggest_refinement(question, missing_context) if missing_context else None

        result = ValidationResult(
            is_valid=not is_too_broad or len(missing_context) == 0,
            is_too_broad=is_too_broad,
            missing_context=missing_context,
            suggestions=suggestions,
            refined_question=refined
        )

        # Cache result
        self.validation_cache[cache_key] = result

        return result

    def _is_too_broad(self, question: str) -> bool:
        """Check if question is too broad"""
        question_lower = question.lower()

        # Check broad patterns
        for pattern in self.BROAD_PATTERNS:
            if re.search(pattern, question_lower):
                return True

        # Check word count (very short questions are often too broad)
        word_count = len(question.split())
        if word_count <= 2:
            return True

        return False

    def _identify_missing_context(self, question: str, context: Dict = None) -> List[str]:
        """Identify which context dimensions are missing"""
        question_lower = question.lower()
        missing = []

        for dimension, config in self.CONTEXT_DIMENSIONS.items():
            # Check if dimension is mentioned in question
            has_dimension = any(kw in question_lower for kw in config['keywords'])

            if has_dimension:
                # Dimension is mentioned, but is it specific enough?
                if not self._has_specific_value(question_lower, dimension):
                    missing.append(dimension)
            else:
                # Dimension not mentioned - may need it based on question type
                if self._dimension_likely_needed(question_lower, dimension):
                    missing.append(dimension)

        return missing

    def _has_specific_value(self, question_lower: str, dimension: str) -> bool:
        """Check if question has specific value for dimension"""
        if dimension == 'time':
            time_specific = ['today', 'yesterday', 'this week', 'last month',
                            'january', 'february', 'q1', 'q2', '2024', '2025',
                            'last 30 days', 'last quarter']
            return any(ts in question_lower for ts in time_specific)

        elif dimension == 'sales_type':
            return 'primary' in question_lower or 'secondary' in question_lower

        elif dimension == 'product':
            # Has specific product name, category, or brand
            return bool(re.search(r'(category|brand|sku)\s+\w+', question_lower))

        elif dimension == 'geography':
            # Has specific location
            return bool(re.search(r'(in|from)\s+\w+', question_lower))

        elif dimension == 'customer':
            # Has specific customer segment or name
            return bool(re.search(r'(segment|customer)\s+\w+', question_lower))

        return False

    def _dimension_likely_needed(self, question_lower: str, dimension: str) -> bool:
        """Determine if dimension is likely needed for this question"""
        # Time is almost always needed for analytics questions
        if dimension == 'time':
            action_words = ['show', 'get', 'what', 'how many', 'how much', 'total', 'average']
            return any(word in question_lower for word in action_words)

        # Sales type needed when asking about sales
        if dimension == 'sales_type':
            return 'sales' in question_lower or 'revenue' in question_lower

        # Product context helpful for product-related questions
        if dimension == 'product':
            return 'product' in question_lower or 'sku' in question_lower

        return False

    def _generate_suggestions(self, question: str, missing_context: List[str]) -> List[str]:
        """Generate helpful suggestions for refining the query"""
        suggestions = []

        for dimension in missing_context:
            config = self.CONTEXT_DIMENSIONS.get(dimension)
            if config:
                suggestions.append(f"{config['question']} Options: {', '.join(config['options'][:3])}...")

        # Add general suggestions if question is very broad
        if len(question.split()) <= 3:
            suggestions.append("Try to be more specific about what you want to know.")
            suggestions.append("Include time period, products, or regions for better results.")

        return suggestions

    def _suggest_refinement(self, question: str, missing_context: List[str]) -> Optional[str]:
        """Suggest a refined version of the question"""
        if not missing_context:
            return None

        # Add default context to make question more specific
        refined = question

        if 'time' in missing_context and 'time' not in question.lower():
            refined += " for this month"

        if 'geography' in missing_context and 'where' not in question.lower():
            refined += " across all regions"

        if 'sales_type' in missing_context and 'sales' in question.lower():
            refined = refined.replace('sales', 'secondary sales')

        return refined if refined != question else None

    def get_clarification_questions(self, missing_context: List[str]) -> List[Dict[str, any]]:
        """
        Get structured clarification questions for missing context

        Args:
            missing_context: List of missing context dimensions

        Returns:
            List of question objects with options
        """
        questions = []

        for dimension in missing_context:
            config = self.CONTEXT_DIMENSIONS.get(dimension)
            if config:
                questions.append({
                    'dimension': dimension,
                    'question': config['question'],
                    'options': config['options']
                })

        return questions

    def apply_clarifications(self, original_question: str,
                           clarifications: Dict[str, str]) -> str:
        """
        Apply user-provided clarifications to refine the question

        Args:
            original_question: Original user question
            clarifications: Dict of dimension -> selected value

        Returns:
            Refined question with clarifications applied
        """
        refined = original_question

        # Add clarifications to question
        additions = []

        if 'time' in clarifications:
            additions.append(f"for {clarifications['time']}")

        if 'sales_type' in clarifications:
            if 'sales' in refined.lower() and 'primary' not in refined.lower() and 'secondary' not in refined.lower():
                refined = refined.replace('sales', f"{clarifications['sales_type']}")
            else:
                additions.append(clarifications['sales_type'])

        if 'product' in clarifications and clarifications['product'] != "All products":
            additions.append(f"for {clarifications['product']}")

        if 'geography' in clarifications and clarifications['geography'] != "All regions":
            additions.append(f"in {clarifications['geography']}")

        if 'customer' in clarifications and clarifications['customer'] != "All customers":
            additions.append(f"for {clarifications['customer']}")

        # Append all additions
        if additions:
            refined += " " + " ".join(additions)

        return refined.strip()
