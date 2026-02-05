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

        # 1. Parse intent
        start_time = time.time()
        semantic_query = intent_parser.parse(question)
        parse_time = (time.time() - start_time) * 1000

        # 2. Validate
        errors = validator.validate(semantic_query)
        if errors:
            return jsonify({
                'success': False,
                'error': f"Validation failed: {', '.join(errors)}"
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
            'error': f"Error: {str(e)}"
        })


def format_single_query_response(result):
    """Format single query results as HTML"""
    html_parts = []

    # Add SQL query (collapsible)
    if 'sql' in result:
        html_parts.append(f"""
        <div class="sql-section">
            <button class="sql-toggle" onclick="toggleSQL()">Show SQL Query</button>
            <pre class="sql-query" id="sqlQuery" style="display:none;">{result['sql']}</pre>
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
