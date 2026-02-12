"""
Flask Web Application with RBAC for CPG Conversational AI Chatbot
Implements user authentication and client-based schema access control
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from semantic_layer.semantic_layer import SemanticLayer
from llm.intent_parser_v2 import IntentParserV2
from semantic_layer.validator import SemanticValidator
from security.rls import RowLevelSecurity, UserContext
from security.auth import AuthManager, User
from query_engine.executor import QueryExecutor
from semantic_layer.orchestrator import QueryOrchestrator
from query_engine.query_validator import QueryValidator
import time
import traceback

app = Flask(__name__)

# IMPORTANT: Change this in production! Use environment variable
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Session configuration - expire when browser closes
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_TYPE'] = 'filesystem'  # Don't persist sessions in browser
app.config['SESSION_PERMANENT'] = False  # Expire when browser closes

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated
login_manager.session_protection = "strong"  # Prevent session hijacking

# Initialize auth manager
auth_manager = AuthManager("database/users.db")

# Cache for client-specific components (avoid recreating for each request)
client_components = {}

# Initialize query validator (shared across all clients)
query_validator = QueryValidator()


def get_client_components(client_id: str):
    """Get or create client-specific components"""
    if client_id not in client_components:
        # Get client configuration
        client_config = auth_manager.get_client_config(client_id)
        if not client_config:
            raise ValueError(f"Client {client_id} not found")

        # Initialize semantic layer for this client
        semantic_layer = SemanticLayer(
            config_path=client_config['config_path'],
            client_id=client_id
        )

        intent_parser = IntentParserV2(semantic_layer, use_claude=False)
        validator = SemanticValidator(semantic_layer)
        executor = QueryExecutor(client_config['database_path'])
        orchestrator = QueryOrchestrator(semantic_layer, executor)

        client_components[client_id] = {
            'semantic_layer': semantic_layer,
            'intent_parser': intent_parser,
            'validator': validator,
            'executor': executor,
            'orchestrator': orchestrator,
            'config': client_config
        }

    return client_components[client_id]


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return auth_manager.get_user_by_id(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        # Authenticate user
        user = auth_manager.authenticate(username, password)

        if user:
            login_user(user, remember=False)  # Don't remember across browser sessions
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'redirect': url_for('index')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401

    # GET request - show login form
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Render chat interface (requires login)"""
    client_config = auth_manager.get_client_config(current_user.client_id)
    return render_template('chat.html',
                         user=current_user,
                         client_name=client_config['client_name'])


@app.route('/api/suggestions', methods=['GET'])
@login_required
def get_suggestions():
    """Get query suggestions for the user"""
    # More varied and comprehensive suggestions
    suggestions = [
        "Show top 5 brands by sales",
        "Weekly sales trend for last 6 weeks",
        "Top 10 SKUs by volume this month",
        "Why did sales change?",
        "Total sales this month",
        "Compare sales by channel",
        "Top distributors by sales value",
        "Sales by state this month"
    ]
    return jsonify({'suggestions': suggestions})


@app.route('/api/query', methods=['POST'])
@login_required
def process_query():
    """Process natural language query (requires login)"""
    try:
        data = request.json
        question = data.get('question', '').strip()

        if not question:
            return jsonify({
                'success': False,
                'error': 'Please enter a question'
            })

        # Get client-specific components
        components = get_client_components(current_user.client_id)

        question_lower = question.lower()
        print(f"\n{'='*60}")
        print(f"DEBUG: Processing query: '{question}'")
        print(f"DEBUG: User: {current_user.username}, Client: {current_user.client_id}")
        print(f"{'='*60}")

        # Handle meta/help questions
        help_keywords = [
            'what questions', 'what can i ask', 'what can you do',
            'give me examples', 'show examples', 'sample questions',
            'help me', 'what to ask', 'how to use',
        ]

        help_triggers = ['help', 'examples', 'suggestions']
        is_help_question = (
            any(keyword in question_lower for keyword in help_keywords) or
            question_lower.strip() in help_triggers
        )

        if is_help_question:
            suggestions = {
                "🏆 Ranking Questions": [
                    "Show top 5 brands by sales value",
                    "Top 10 SKUs by volume this month",
                    "Top distributors by sales value",
                ],
                "📈 Trend Analysis": [
                    "Weekly sales trend for last 6 weeks",
                    "Monthly sales trend for this year",
                ],
                "🔍 Comparison": [
                    "Compare sales by channel",
                    "Sales by state this month",
                ],
                "📊 Snapshots": [
                    "Total sales this month",
                    "Total volume last month",
                ],
                "🔬 Diagnostics": [
                    "Why did sales change?",
                    "Why did sales drop?",
                ],
            }

            html_response = '<div class="suggestions-box">'
            html_response += '<h3>📊 Sample Questions</h3>'

            for category, questions in suggestions.items():
                html_response += f'<h4>{category}</h4><ul>'
                for q in questions:
                    html_response += f'<li>"{q}"</li>'
                html_response += '</ul>'

            html_response += '</div>'

            return jsonify({
                'success': True,
                'response': html_response,
                'metadata': {
                    'query_id': f"HELP{int(time.time())}",
                    'intent': 'help',
                }
            })

        # Check for out-of-scope questions
        # 1. Metadata/schema questions
        metadata_keywords = [
            'table', 'column', 'schema', 'database', 'metadata',
            'what tables', 'what columns', 'show tables', 'describe table',
            'table structure', 'database structure', 'list tables',
            'what data', 'what fields', 'available fields'
        ]

        if any(keyword in question_lower for keyword in metadata_keywords):
            print(f"DEBUG: Metadata keywords check triggered!")
            print(f"DEBUG: Matched keywords: {[k for k in metadata_keywords if k in question_lower]}")
            client_config = auth_manager.get_client_config(current_user.client_id)
            html_response = f"""
            <div style="padding: 15px; background: #ffebee; border-left: 4px solid #f44336; border-radius: 4px;">
                <h3 style="color: #d32f2f; margin-bottom: 10px;">❌ Out of Scope Question</h3>
                <p><strong>This chatbot is for analytics queries only, not database metadata exploration.</strong></p>
                <p style="margin-top: 10px;">You asked about database structure or metadata. This information is not available through the chatbot interface.</p>
                <p style="margin-top: 10px; padding: 10px; background: white; border-radius: 4px;">
                    <strong>What you CAN ask:</strong><br>
                    • "Show top 5 brands by sales"<br>
                    • "Weekly sales trend"<br>
                    • "Why did sales change?"<br>
                    • "Total sales this month"
                </p>
                <p style="margin-top: 10px; font-size: 12px; color: #666;">
                    <em>💡 For metadata exploration, use the CLI tool: <code>python explore_database.py</code></em>
                </p>
            </div>
            """
            return jsonify({
                'success': False,
                'response': html_response,
                'metadata': {'intent': 'out_of_scope_metadata'}
            })

        # 2. General knowledge questions
        general_keywords = [
            'who is', 'when was', 'where is', 'how to',
            'weather', 'news', 'stock market', 'sports', 'politics',
            'calculate', 'math', 'geography', 'history', 'science'
        ]

        if any(keyword in question_lower for keyword in general_keywords):
            print(f"DEBUG: General keywords check triggered!")
            print(f"DEBUG: Matched keywords: {[k for k in general_keywords if k in question_lower]}")
            # Exclude legitimate analytics questions
            analytics_exceptions = ['what are', 'what is', 'how much', 'how many']
            if not any(exc in question_lower for exc in analytics_exceptions):
                print(f"DEBUG: No analytics exceptions found, blocking as general knowledge question")
                html_response = f"""
                <div style="padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                    <h3 style="color: #856404; margin-bottom: 10px;">⚠️ Out of Scope Question</h3>
                    <p><strong>This chatbot is specialized for CPG sales analytics only.</strong></p>
                    <p style="margin-top: 10px;">Your question appears to be about general knowledge or non-analytics topics.</p>
                    <p style="margin-top: 10px; padding: 10px; background: white; border-radius: 4px;">
                        <strong>I can help you with:</strong><br>
                        • Sales performance analysis<br>
                        • Brand and product insights<br>
                        • Distribution channel metrics<br>
                        • Time-based trends and diagnostics
                    </p>
                    <p style="margin-top: 10px; font-size: 13px;">
                        <strong>Try asking:</strong> "Show top brands by sales this month"
                    </p>
                </div>
                """
                return jsonify({
                    'success': False,
                    'response': html_response,
                    'metadata': {'intent': 'out_of_scope_general'}
                })

        # 3. Check for cross-client queries (mentions of other companies)
        all_clients = {
            'nestle': ['nestle', 'nestlé'],
            'unilever': ['unilever', 'hindustan unilever', 'hul'],
            'itc': ['itc', 'itc limited']
        }

        # Check if question mentions other clients
        mentioned_clients = []
        for client_id, aliases in all_clients.items():
            if client_id != current_user.client_id:
                if any(alias in question_lower for alias in aliases):
                    client_config = auth_manager.get_client_config(client_id)
                    if client_config:
                        mentioned_clients.append(client_config['client_name'])

        if mentioned_clients:
            print(f"DEBUG: Cross-client check triggered!")
            print(f"DEBUG: Mentioned clients: {mentioned_clients}")
            current_client = auth_manager.get_client_config(current_user.client_id)
            html_response = f"""
            <div style="padding: 15px; background: #ffebee; border-left: 4px solid #f44336; border-radius: 4px;">
                <h3 style="color: #d32f2f; margin-bottom: 10px;">🚫 Permission Denied</h3>
                <p><strong>You do not have access to data from: {', '.join(mentioned_clients)}</strong></p>
                <p style="margin-top: 10px;">Your account (<strong>{current_user.username}</strong>) is authorized to access <strong>{current_client['client_name']}</strong> data only.</p>
                <p style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 4px;">
                    <strong>⚠️ Data Isolation:</strong><br>
                    For security and privacy reasons, each client's data is completely isolated.
                    You can only query data for your assigned organization.
                </p>
                <p style="margin-top: 10px; padding: 10px; background: white; border-radius: 4px;">
                    <strong>✅ You CAN ask about:</strong><br>
                    • "{current_client['client_name']} top brands by sales"<br>
                    • "Weekly sales trend for my products"<br>
                    • "Why did our sales change?"<br>
                    • "Total sales this month"
                </p>
            </div>
            """
            return jsonify({
                'success': False,
                'response': html_response,
                'metadata': {'intent': 'permission_denied'}
            })

        # Validate query for broadness
        print(f"DEBUG: Validating query broadness...")
        try:
            validation_result = query_validator.validate_query(question)
        except Exception as e:
            print(f"DEBUG: Validation error: {str(e)}")
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            # If validation fails, continue to intent parsing
            validation_result = None

        if validation_result and validation_result.is_too_broad:
            print(f"DEBUG: Query is too broad. Missing context: {validation_result.missing_context}")

            # Get clarification questions
            clarification_questions = query_validator.get_clarification_questions(
                validation_result.missing_context
            )

            # Build interactive HTML response with clarification options
            html_response = '<div class="suggestions-box">'
            html_response += '<h3>🤔 Let\'s Be More Specific</h3>'
            html_response += '<p>Your question is a bit broad. Please provide more details:</p>'

            for q in clarification_questions:
                html_response += f'<h4 style="margin-top: 15px;">{q["question"]}</h4>'
                html_response += '<ul class="suggestions-list">'
                for option in q['options']:
                    # Create clickable suggestion that will refine the query
                    # Use double quotes for HTML attributes, escape single quotes in JS
                    import html
                    option_safe = html.escape(option)
                    suggestion_text = f"{question} {option}".replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ')
                    html_response += f'<li class="clarification-option" onclick=\'selectClarification("{suggestion_text}")\'>{option_safe}</li>'
                html_response += '</ul>'

            # Show refined suggestion
            if validation_result.refined_question:
                import html
                refined_safe = html.escape(validation_result.refined_question)
                refined_escaped = validation_result.refined_question.replace('"', '&quot;')
                html_response += f'<div class="hint">'
                html_response += f'<strong>💡 Or try this:</strong> <span style="cursor: pointer; color: #667eea;" onclick=\'selectClarification("{refined_escaped}")\'>{refined_safe}</span>'
                html_response += '</div>'

            html_response += '</div>'

            return jsonify({
                'success': True,
                'response': html_response,
                'metadata': {
                    'intent': 'clarification_needed',
                    'confidence': 0,
                    'exec_time_ms': 0
                }
            })

        print(f"DEBUG: Query validation passed, proceeding to intent parsing...")

        # Parse intent
        start_time = time.time()
        try:
            semantic_query = components['intent_parser'].parse(question)
            print(f"DEBUG: Successfully parsed intent: {semantic_query.intent}")  # Debug log
        except Exception as e:
            print(f"DEBUG: Intent parsing failed: {str(e)}")  # Debug log
            print(f"DEBUG: Full error: {traceback.format_exc()}")  # Full traceback
            auth_manager.log_query(
                current_user.id, current_user.username, current_user.client_id,
                question, None, False, str(e)
            )
            return jsonify({
                'success': False,
                'error': f'Sorry, I couldn\'t understand that question: {str(e)}'
            })

        parse_time = (time.time() - start_time) * 1000

        # Validate
        errors = components['validator'].validate(semantic_query)
        if errors:
            auth_manager.log_query(
                current_user.id, current_user.username, current_user.client_id,
                question, None, False, ', '.join(errors)
            )
            return jsonify({
                'success': False,
                'error': f'Validation errors: {", ".join(errors)}'
            })

        # Apply security (RLS based on user role)
        user_context = UserContext(
            user_id=current_user.username,
            role=current_user.role,
            data_access_level='national',  # Can be customized per user
            states=[],
            regions=[]
        )
        secured_query = RowLevelSecurity.apply_security(semantic_query, user_context)

        # Execute query
        start_time = time.time()
        result = components['orchestrator'].execute(secured_query)
        exec_time = (time.time() - start_time) * 1000

        # Format response (NO LLM Call #2 for security)
        if result['query_type'] == 'diagnostic':
            response = format_diagnostic_response(result)
        else:
            response = format_single_query_response(result)

        # Audit log
        auth_manager.log_query(
            current_user.id, current_user.username, current_user.client_id,
            question, result.get('sql', ''), True, None
        )

        return jsonify({
            'success': True,
            'response': response,
            'raw_data': result.get('results', []),  # Include raw data for chart rendering
            'query_type': result.get('query_type', 'standard'),
            'metadata': {
                'user': current_user.username,
                'client': current_user.client_id,
                'intent': semantic_query.intent.value,
                'parse_time_ms': round(parse_time, 2),
                'exec_time_ms': round(exec_time, 2),
                'confidence': semantic_query.confidence
            }
        })

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error processing query: {error_trace}")

        auth_manager.log_query(
            current_user.id, current_user.username, current_user.client_id,
            question, None, False, str(e)
        )

        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


def format_single_query_response(result):
    """Format single query results as HTML"""
    html_parts = []

    # Add SQL query (collapsible)
    if 'sql' in result:
        sql_id = f"sqlQuery{int(time.time() * 1000)}"
        html_parts.append(f"""
        <div class="sql-section">
            <button class="sql-toggle" onclick="toggleSQL('{sql_id}')">Show SQL Query</button>
            <pre class="sql-query" id="{sql_id}" style="display:none;">{result['sql']}</pre>
        </div>
        """)

    # Add results table
    if 'results' in result and result['results']:
        rows = result['results']

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


if __name__ == '__main__':
    print("="*60)
    print("CPG Conversational AI Chatbot (RBAC Enabled)")
    print("="*60)
    print("Starting Flask server...")
    print("Open your browser and go to: http://localhost:5000")
    print("")
    print("Login with one of the sample users:")
    print("  - nestle_admin / nestle123")
    print("  - unilever_admin / unilever123")
    print("  - itc_admin / itc123")
    print("")
    print("Press Ctrl+C to stop the server")
    print("="*60)

    app.run(debug=True, host='0.0.0.0', port=5000)
