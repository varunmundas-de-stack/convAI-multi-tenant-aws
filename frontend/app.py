"""
Flask Web Application for CPG Conversational AI Chatbot
Provides a web-based chat interface for querying CPG analytics
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from semantic_layer.semantic_layer import SemanticLayer
from llm.intent_parser_v2 import IntentParserV2
from semantic_layer.validator import SemanticValidator
from security.rls import RowLevelSecurity, UserContext
from security.audit import AuditLogger
from query_engine.executor import QueryExecutor
from semantic_layer.orchestrator import QueryOrchestrator
import time
import traceback

app = Flask(__name__)

# Initialize components
semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
intent_parser = IntentParserV2(semantic_layer, use_claude=False)  # Use Ollama by default
validator = SemanticValidator(semantic_layer)
executor = QueryExecutor("database/cpg_olap.duckdb")
orchestrator = QueryOrchestrator(semantic_layer, executor)
audit_logger = AuditLogger("logs/audit.jsonl")

# Demo user context (can be customized)
demo_user = UserContext(
    user_id="demo_user",
    role="analyst",
    data_access_level="national",
    states=[],
    regions=[]
)


@app.route('/')
def index():
    """Render chat interface"""
    return render_template('chat.html')


@app.route('/api/query', methods=['POST'])
def process_query():
    """Process natural language query and return results"""
    try:
        data = request.json
        question = data.get('question', '').strip()

        if not question:
            return jsonify({
                'success': False,
                'error': 'Please enter a question'
            })

        question_lower = question.lower()

        # Handle meta/help questions - provide suggestions instead of querying
        help_keywords = [
            'what questions', 'what can i ask', 'what can you do',
            'give me examples', 'show examples', 'sample questions',
            'help me', 'what to ask', 'how to use', 'what should i ask',
            'give me some questions', 'example queries', 'what other questions',
            'example question', 'sample query'
        ]

        # Also check for single-word help triggers
        help_triggers = ['help', 'examples', 'suggestions']
        is_help_question = (
            any(keyword in question_lower for keyword in help_keywords) or
            question_lower.strip() in help_triggers or
            (question_lower.startswith('help') and len(question_lower) < 10)
        )

        if is_help_question:
            # Comprehensive list of all possible question types
            suggestions = {
                "🏆 Ranking Questions (Top/Bottom)": [
                    "Show top 5 brands by sales value",
                    "Top 10 SKUs by volume this month",
                    "Top distributors by sales value",
                    "Bottom 5 states by sales",
                    "Top 10 retailers by invoice count",
                    "Best performing channels by margin",
                    "Top 5 categories by sales volume"
                ],
                "📈 Trend Analysis (Time Series)": [
                    "Weekly sales trend for last 6 weeks",
                    "Monthly sales trend for this year",
                    "Sales volume by week for last 12 weeks",
                    "Daily sales trend this month",
                    "Quarterly sales trend",
                    "Monthly margin trend for last 6 months"
                ],
                "🔍 Comparison & Breakdown": [
                    "Compare sales by channel",
                    "Sales by state this month",
                    "Distribution by brand",
                    "Sales by retailer type",
                    "Compare volume by category",
                    "Sales by zone",
                    "Revenue by district"
                ],
                "📊 Snapshot Queries (Aggregates)": [
                    "Total sales this month",
                    "Total volume last month",
                    "Total margin this quarter",
                    "Invoice count this year",
                    "Average selling price this month"
                ],
                "🔬 Diagnostic Analysis (Root Cause)": [
                    "Why did sales change?",
                    "Why did sales drop?",
                    "Why did volume increase?",
                    "Analyze sales performance"
                ],
                "🎯 Filtered Queries": [
                    "Sales in Tamil Nadu this month",
                    "Top brands in Karnataka",
                    "Channel performance in South zone",
                    "GT channel sales by state"
                ],
                "💰 Different Metrics": [
                    "Show gross sales value by brand",
                    "Discount amount by channel",
                    "Margin by distributor",
                    "Invoice count by state",
                    "Return value by category"
                ]
            }

            html_response = '<div class="suggestions-box">'
            html_response += '<h3>📊 Complete List of Questions You Can Ask</h3>'

            for category, questions in suggestions.items():
                html_response += f'<div style="margin: 20px 0;">'
                html_response += f'<h4 style="color: #667eea; margin-bottom: 10px; font-size: 16px;">{category}</h4>'
                html_response += '<ul class="suggestions-list">'
                for question in questions:
                    html_response += f'<li>"{question}"</li>'
                html_response += '</ul>'
                html_response += '</div>'

            html_response += '<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #ffc107;">'
            html_response += '<p style="margin: 0; font-size: 14px; color: #856404;"><strong>💡 Key Features:</strong></p>'
            html_response += '<ul style="margin: 10px 0 0 20px; color: #856404; font-size: 13px;">'
            html_response += '<li><strong>Dimensions:</strong> Brand, SKU, Category, State, Zone, District, Channel, Distributor, Retailer</li>'
            html_response += '<li><strong>Metrics:</strong> Sales Value, Volume, Margin, Discounts, Invoice Count, Returns</li>'
            html_response += '<li><strong>Time Periods:</strong> Last 4/6/12 weeks, This/Last Month, MTD, QTD, YTD</li>'
            html_response += '<li><strong>Analysis Types:</strong> Ranking, Trends, Comparisons, Diagnostics, Snapshots</li>'
            html_response += '</ul>'
            html_response += '</div>'
            html_response += '</div>'

            return jsonify({
                'success': True,
                'response': html_response,
                'metadata': {
                    'query_id': f"HELP{int(time.time())}",
                    'intent': 'help',
                    'parse_time_ms': 0,
                    'exec_time_ms': 0,
                    'confidence': 1.0
                }
            })

        # Input validation: Check for out-of-scope questions

        # System/technical questions
        system_keywords = [
            'table', 'schema', 'column', 'database', 'metadata',
            'how many table', 'show table', 'describe', 'structure',
            'system', 'llm', 'model', 'backend', 'frontend', 'api', 'code'
        ]

        # General knowledge questions (not business analytics)
        general_knowledge_keywords = [
            'who is the president', 'who is the prime minister', 'who won',
            'what is the capital', 'when was', 'where is',
            'president of', 'capital of', 'population of',
            'who invented', 'who discovered', 'who created',
            'meaning of life', 'how old is', 'birthday',
            'weather', 'temperature', 'time', 'date today',
            'movie', 'song', 'book', 'game', 'sport',
            'recipe', 'cook', 'food recipe'
        ]

        # Check if question is about non-business topics
        non_business_topics = [
            'president', 'politics', 'government', 'election',
            'country', 'city', 'world', 'planet', 'space',
            'celebrity', 'actor', 'singer', 'athlete',
            'history', 'geography', 'science', 'math formula'
        ]

        # Check for "what is" or "who is" followed by non-business terms
        if question_lower.startswith(('what is ', 'who is ', 'who are ', 'where is ', 'when was ', 'when is ', 'how does ')):
            # Check if it contains any business-relevant terms
            business_terms = ['sales', 'revenue', 'margin', 'volume', 'brand', 'sku', 'distributor',
                            'retailer', 'channel', 'state', 'zone', 'invoice', 'value', 'trend']
            has_business_term = any(term in question_lower for term in business_terms)

            if not has_business_term:
                # Likely a general knowledge question
                return jsonify({
                    'success': False,
                    'error': '''⚠️ <strong>Out of Scope</strong>

This chatbot answers <strong>CPG sales analytics questions only</strong>.

Your question appears to be about general knowledge, not sales data.

💡 <strong>Try typing "give me examples"</strong> to see what I CAN answer!

I can help with:
• Sales metrics (value, volume, margin)
• Trends over time
• Top/bottom performers
• Comparisons by dimension
• Root cause analysis ("why" questions)'''
                })

        if (any(keyword in question_lower for keyword in system_keywords) or
            any(keyword in question_lower for keyword in general_knowledge_keywords) or
            (any(topic in question_lower for topic in non_business_topics) and
             not any(term in question_lower for term in ['sales', 'revenue', 'distributor', 'brand', 'sku']))):
            return jsonify({
                'success': False,
                'error': '''⚠️ <strong>Out of Scope</strong>

This chatbot answers <strong>CPG sales analytics questions only</strong>.

I cannot answer questions about:
• Database schema/metadata
• System architecture
• How the chatbot works
• General knowledge questions

💡 <strong>Try typing "give me examples"</strong> to see what I CAN answer!

Quick examples:
• "Show top 5 brands by sales value"
• "Compare sales by channel"
• "Weekly sales trend for last 6 weeks"

<em>For database metadata, use the CLI tool: python demos/explore_database.py</em>'''
            })

        # Final check: Does question contain ANY business-relevant keywords?
        # If not, it's likely completely out of scope
        business_keywords = [
            # Metrics
            'sales', 'revenue', 'value', 'volume', 'margin', 'profit', 'discount',
            'invoice', 'bill', 'amount', 'price', 'cost', 'return',
            # Dimensions - Product
            'brand', 'sku', 'product', 'category', 'item', 'pack',
            # Dimensions - Geography
            'state', 'zone', 'region', 'district', 'town', 'city', 'area', 'territory',
            # Dimensions - Customer/Channel
            'distributor', 'retailer', 'outlet', 'store', 'customer', 'channel',
            'gt', 'mt', 'trade', 'pharmacy', 'ecom', 'e-com',
            # Time
            'week', 'month', 'quarter', 'year', 'daily', 'weekly', 'monthly', 'trend',
            # Analytics terms
            'top', 'bottom', 'best', 'worst', 'compare', 'comparison', 'growth',
            'change', 'increase', 'decrease', 'drop', 'rise', 'performance',
            'why', 'analyze', 'analysis', 'breakdown', 'distribution',
            # Common question patterns
            'show', 'display', 'list', 'get', 'fetch', 'total', 'sum', 'count',
            'average', 'maximum', 'minimum', 'highest', 'lowest'
        ]

        has_any_business_keyword = any(keyword in question_lower for keyword in business_keywords)

        if not has_any_business_keyword:
            return jsonify({
                'success': False,
                'error': '''⚠️ <strong>Question Not Recognized</strong>

I couldn't find any business analytics terms in your question.

This chatbot is specialized for <strong>CPG sales analytics only</strong>.

💡 <strong>Try typing "give me examples"</strong> to see the full list of questions I understand!

<strong>Valid questions must include terms like:</strong>
• <strong>Metrics:</strong> sales, revenue, volume, margin, invoices
• <strong>Products:</strong> brand, SKU, category, product
• <strong>Geography:</strong> state, zone, region, district
• <strong>Customers:</strong> distributor, retailer, outlet, channel
• <strong>Analysis:</strong> top, trend, compare, why, breakdown

<strong>Examples:</strong>
• "Show top 5 brands by sales"
• "Compare sales by channel"
• "Weekly trend for last 6 weeks"'''
            })

        # 1. Parse intent
        start_time = time.time()
        try:
            semantic_query = intent_parser.parse(question)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'''Sorry, I couldn't understand that question.

This chatbot answers CPG sales analytics questions only.

💡 <strong>Try typing "give me examples"</strong> to see 35+ sample questions I can answer!

Or try questions like:
• "Show top 5 brands by sales value"
• "Compare sales by channel"
• "Weekly sales trend"'''
            })

        parse_time = (time.time() - start_time) * 1000

        # Check confidence level - if too low, suggest examples
        if semantic_query.confidence < 0.5:
            return jsonify({
                'success': False,
                'error': f'''I'm not confident I understood your question correctly (confidence: {semantic_query.confidence:.0%}).

💡 <strong>Try typing "give me examples"</strong> to see questions I can answer!

Or rephrase your question more specifically, like:
• "Top 10 SKUs by volume this month"
• "Sales by state"
• "Why did sales change?"'''
            })

        # 2. Validate
        errors = validator.validate(semantic_query)
        if errors:
            return jsonify({
                'success': False,
                'error': f'''Sorry, I couldn't process that question.

<strong>Issue:</strong> {', '.join(errors)}

💡 <strong>Try typing "give me examples"</strong> to see valid questions!

Common issues:
• Check metric names (e.g., "sales value", "volume", "margin")
• Check dimension names (e.g., "brand", "state", "channel")
• Ensure you're asking about sales analytics data'''
            })

        # 3. Apply security (optional - currently using demo user with national access)
        secured_query = RowLevelSecurity.apply_security(semantic_query, demo_user)

        # 4. Execute query using orchestrator
        start_time = time.time()
        result = orchestrator.execute(secured_query)
        exec_time = (time.time() - start_time) * 1000

        # 5. Format response based on query type
        if result['query_type'] == 'diagnostic':
            response = format_diagnostic_response(result)
        else:
            response = format_single_query_response(result)

        # 6. Audit log
        query_id = f"Q{int(time.time())}"
        audit_logger.log_query(
            query_id=query_id,
            user_id=demo_user.user_id,
            semantic_query=semantic_query.dict(),
            sql=result.get('sql', ''),
            result_count=result.get('metadata', {}).get('row_count', 0),
            exec_time=exec_time,
            success=True,
            error=None
        )

        return jsonify({
            'success': True,
            'response': response,
            'metadata': {
                'query_id': query_id,
                'intent': semantic_query.intent.value,
                'parse_time_ms': round(parse_time, 2),
                'exec_time_ms': round(exec_time, 2),
                'confidence': semantic_query.confidence
            }
        })

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error processing query: {error_trace}")

        return jsonify({
            'success': False,
            'error': f'''❌ <strong>Unexpected Error</strong>

Something went wrong while processing your question.

<strong>Error:</strong> {str(e)}

💡 <strong>Try typing "give me examples"</strong> to see questions that work!

Or try simpler questions like:
• "Total sales this month"
• "Top 5 brands by sales"
• "Sales by state"

If the problem persists, please contact support.'''
        })


def format_single_query_response(result):
    """Format single query results as HTML"""
    html_parts = []

    # Add SQL query (collapsible) - use unique ID for each query
    if 'sql' in result:
        sql_id = f"sqlQuery{int(time.time() * 1000)}"  # Unique ID with milliseconds
        html_parts.append(f"""
        <div class="sql-section">
            <button class="sql-toggle" onclick="toggleSQL('{sql_id}')">Show SQL Query</button>
            <pre class="sql-query" id="{sql_id}" style="display:none;">{result['sql']}</pre>
        </div>
        """)

    # Add results table
    if 'results' in result and result['results']:
        rows = result['results']

        # Build HTML table
        html_parts.append('<div class="results-table">')
        html_parts.append('<table>')

        # Header
        html_parts.append('<thead><tr>')
        for col in rows[0].keys():
            html_parts.append(f'<th>{col}</th>')
        html_parts.append('</tr></thead>')

        # Body
        html_parts.append('<tbody>')
        for row in rows:
            html_parts.append('<tr>')
            for value in row.values():
                formatted_value = format_value(value)
                html_parts.append(f'<td>{formatted_value}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')

        html_parts.append('</table>')
        html_parts.append('</div>')

        # Add summary
        row_count = result.get('metadata', {}).get('row_count', len(rows))
        html_parts.append(f'<p class="result-summary">{row_count} rows returned</p>')
    else:
        html_parts.append('<p class="no-results">No results found</p>')

    return ''.join(html_parts)


def format_diagnostic_response(result):
    """Format diagnostic workflow results as HTML"""
    html_parts = []

    analysis = result.get('analysis', {})

    # Trend Analysis
    trend = analysis.get('trend_analysis', {})
    if trend:
        direction = trend.get('direction', 'unknown')
        change_pct = trend.get('change_pct', 0)

        icon = '[+]' if direction == 'increasing' else '[!]' if direction == 'decreasing' else '[=]'
        color = 'green' if direction == 'increasing' else 'red' if direction == 'decreasing' else 'gray'

        html_parts.append(f"""
        <div class="diagnostic-section">
            <h3>Trend Analysis</h3>
            <p style="color: {color};">
                <strong>{icon} Direction:</strong> {direction.capitalize()}
                ({change_pct:+.1f}%)
            </p>
        </div>
        """)

    # Insights
    insights = analysis.get('insights', [])
    if insights:
        html_parts.append('<div class="diagnostic-section">')
        html_parts.append('<h3>Key Insights</h3>')
        html_parts.append('<ul class="insights-list">')
        for insight in insights:
            html_parts.append(f'<li>{insight}</li>')
        html_parts.append('</ul>')
        html_parts.append('</div>')

    # Recommendations
    recommendations = analysis.get('recommendations', [])
    if recommendations:
        html_parts.append('<div class="diagnostic-section recommendations">')
        html_parts.append('<h3>Recommendations</h3>')
        html_parts.append('<ul class="recommendations-list">')
        for rec in recommendations:
            html_parts.append(f'<li>{rec}</li>')
        html_parts.append('</ul>')
        html_parts.append('</div>')

    # Contribution Analysis (summary)
    contrib_analysis = analysis.get('contribution_analysis', [])
    if contrib_analysis:
        html_parts.append('<div class="diagnostic-section">')
        html_parts.append('<h3>Top Contributors</h3>')
        html_parts.append('<ul class="contributors-list">')
        for contrib in contrib_analysis[:3]:  # Top 3
            dim = contrib['dimension']
            top = contrib['top_contributor']
            html_parts.append(f'<li><strong>{dim}:</strong> {list(top.values())[0]}</li>')
        html_parts.append('</ul>')
        html_parts.append('</div>')

    # Metadata
    metadata = result.get('metadata', {})
    total_queries = metadata.get('total_queries', 0)
    total_time = metadata.get('total_execution_time_ms', 0)

    html_parts.append(f"""
    <p class="diagnostic-meta">
        <em>Executed {total_queries} queries in {total_time:.0f}ms</em>
    </p>
    """)

    return ''.join(html_parts)


def format_value(value):
    """Format cell value for display"""
    if value is None:
        return '-'
    elif isinstance(value, float):
        return f'{value:,.2f}'
    elif isinstance(value, int):
        return f'{value:,}'
    else:
        return str(value)


@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    """Get sample query suggestions"""
    suggestions = [
        "Show top 5 brands by sales value",
        "Weekly sales trend for last 6 weeks",
        "Top 10 SKUs by volume this month",
        "Sales by state this month",
        "Why did sales change?",
        "Compare sales by channel",
        "Show distribution by brand",
        "Top distributors by sales value"
    ]
    return jsonify({'suggestions': suggestions})


if __name__ == '__main__':
    print("="*60)
    print("CPG Conversational AI Chatbot")
    print("="*60)
    print("Starting Flask server...")
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("="*60)

    app.run(debug=True, host='0.0.0.0', port=5000)
