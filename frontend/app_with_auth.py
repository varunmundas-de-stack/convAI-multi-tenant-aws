"""
Flask Web Application with RBAC for CPG Conversational AI Chatbot
Implements user authentication and client-based schema access control
"""
import sys
import os
import re
import uuid
import sqlite3
import json as _json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
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
import threading
from insights.hierarchy_insights_engine import HierarchyInsightsEngine

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

# Absolute project root — resolves paths correctly regardless of working directory
_APP_ROOT = Path(__file__).parent.parent
_REACT_BUILD = _APP_ROOT / 'frontend' / 'static' / 'react'

# Serve React static build if it exists; fall back to legacy Jinja templates
if _REACT_BUILD.exists():
    app.static_folder = str(_REACT_BUILD)
    app.static_url_path = ''

# Initialize auth manager with absolute path
auth_manager = AuthManager(str(_APP_ROOT / 'database' / 'users.db'))

# Cache for client-specific components (avoid recreating for each request)
client_components = {}

# Initialize query validator (shared across all clients)
query_validator = QueryValidator()

# Tenant schema mapping (client_id -> DuckDB schema name)
TENANT_SCHEMAS = {
    'nestle':   'client_nestle',
    'unilever': 'client_unilever',
    'itc':      'client_itc',
}

# Initialize hierarchy insights engine with absolute paths
insights_engine = HierarchyInsightsEngine(
    analytics_db_path=str(_APP_ROOT / 'database' / 'cpg_multi_tenant.duckdb'),
    users_db_path=str(_APP_ROOT / 'database' / 'users.db'),
)


def _insights_generation_loop():
    """Background daemon thread: generate insights on startup then every 6 hours."""
    time.sleep(10)  # let Flask finish initialising first
    while True:
        for client_id, schema_name in TENANT_SCHEMAS.items():
            try:
                count = insights_engine.generate_and_store(client_id, schema_name)
                print(f"[Insights] {client_id}: {count} insights generated/refreshed")
            except Exception as exc:
                print(f"[Insights] Error generating for {client_id}: {exc}")
        time.sleep(6 * 3600)  # refresh every 6 hours


def get_client_components(client_id: str):
    """Get or create client-specific components"""
    if client_id not in client_components:
        # Get client configuration
        client_config = auth_manager.get_client_config(client_id)
        if not client_config:
            raise ValueError(f"Client {client_id} not found")

        # Resolve stored relative paths against project root
        config_path   = str(_APP_ROOT / client_config['config_path'])
        database_path = str(_APP_ROOT / client_config['database_path'])

        # Initialize semantic layer for this client
        semantic_layer = SemanticLayer(
            config_path=config_path,
            client_id=client_id
        )

        intent_parser = IntentParserV2(semantic_layer, use_claude=False)
        validator = SemanticValidator(semantic_layer)
        executor = QueryExecutor(database_path)
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
            login_user(user, remember=False)
            return jsonify({
                'success': True,
                'user': {
                    'user_id': user.id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'client_id': user.client_id,
                    'role': user.role,
                    'department': user.department,
                    'sales_hierarchy_level': user.sales_hierarchy_level,
                },
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401

    # GET — serve React app (or legacy HTML in dev without a build)
    if _REACT_BUILD.exists():
        return send_from_directory(str(_REACT_BUILD), 'index.html')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout — works for both React (GET) and legacy HTML"""
    logout_user()
    if request.accept_mimetypes.accept_json:
        return jsonify({'success': True})
    return redirect(url_for('login'))


@app.route('/api/me')
@login_required
def api_me():
    """Return current authenticated user info (used by React on page reload)"""
    return jsonify({
        'user_id': current_user.id,
        'username': current_user.username,
        'full_name': current_user.full_name,
        'client_id': current_user.client_id,
        'role': current_user.role,
        'department': current_user.department,
        'sales_hierarchy_level': current_user.sales_hierarchy_level,
    })


@app.route('/')
@login_required
def index():
    """Serve React app or legacy Jinja template"""
    if _REACT_BUILD.exists():
        return send_from_directory(str(_REACT_BUILD), 'index.html')
    client_config = auth_manager.get_client_config(current_user.client_id)
    return render_template('chat.html',
                           user=current_user,
                           client_name=client_config['client_name'])


@app.route('/<path:path>')
def catch_all(path):
    """React client-side routing — serve index.html for all non-API paths"""
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    if _REACT_BUILD.exists():
        full = _REACT_BUILD / path
        if full.exists():
            return send_from_directory(str(_REACT_BUILD), path)
        return send_from_directory(str(_REACT_BUILD), 'index.html')
    return redirect(url_for('index'))


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

        def _kw_match(text, keywords):
            """Word-boundary aware keyword matching — avoids 'show top' matching 'how to'."""
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    return True
            return False

        if _kw_match(question_lower, metadata_keywords):
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

        if _kw_match(question_lower, general_keywords):
            analytics_exceptions = ['what are', 'what is', 'how much', 'how many']
            if not any(exc in question_lower for exc in analytics_exceptions):
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

        # Apply security (RLS based on user's actual hierarchy)
        # Admin/analyst/NSM get national access; ZSM/ASM/SO get filtered access
        hierarchy_restricted_roles = {'SO', 'ASM', 'ZSM'}
        access_level = 'territory' if current_user.role in hierarchy_restricted_roles else 'national'

        user_context = UserContext(
            user_id=current_user.username,
            role=current_user.role,
            data_access_level=access_level,
            states=[],
            regions=[],
            sales_hierarchy_level=current_user.sales_hierarchy_level,
            so_codes=[current_user.so_code] if current_user.so_code else [],
            asm_codes=[current_user.asm_code] if current_user.asm_code else [],
            zsm_codes=[current_user.zsm_code] if current_user.zsm_code else [],
            nsm_codes=[current_user.nsm_code] if current_user.nsm_code else [],
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


@app.route('/api/insights', methods=['GET'])
@login_required
def get_insights():
    """Return hierarchy-targeted insights for the current user."""
    hierarchy_level = current_user.sales_hierarchy_level or current_user.role
    insights = insights_engine.get_insights_for_user(
        user_id=current_user.id,
        hierarchy_level=hierarchy_level,
        tenant_id=current_user.client_id,
        so_code=current_user.so_code,
        asm_code=current_user.asm_code,
        zsm_code=current_user.zsm_code,
        nsm_code=current_user.nsm_code,
    )
    return jsonify({'insights': insights})


@app.route('/api/insights/count', methods=['GET'])
@login_required
def get_insights_count():
    """Return unread insight count for badge display."""
    hierarchy_level = current_user.sales_hierarchy_level or current_user.role
    count = insights_engine.get_unread_count(
        user_id=current_user.id,
        hierarchy_level=hierarchy_level,
        tenant_id=current_user.client_id,
        so_code=current_user.so_code,
        asm_code=current_user.asm_code,
        zsm_code=current_user.zsm_code,
    )
    return jsonify({'unread_count': count})


@app.route('/api/insights/<insight_id>/read', methods=['POST'])
@login_required
def mark_insight_read(insight_id):
    """Mark an insight as read for the current user."""
    insights_engine.mark_read(insight_id, current_user.id)
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
# Chat Session Persistence  (Claude.ai / ChatGPT style)
# ─────────────────────────────────────────────────────────────────────────────

def _sessions_db():
    """Return a sqlite3 connection to users.db (session tables live there)."""
    conn = sqlite3.connect(str(_APP_ROOT / 'database' / 'users.db'))
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/sessions', methods=['GET'])
@login_required
def list_sessions():
    """Return all chat sessions for the current user, newest first."""
    with _sessions_db() as conn:
        rows = conn.execute("""
            SELECT session_id, title, created_at, last_active
            FROM   chat_sessions
            WHERE  user_id = ? AND is_active = 1
            ORDER  BY last_active DESC
            LIMIT  100
        """, (current_user.id,)).fetchall()
    return jsonify({'sessions': [dict(r) for r in rows]})


@app.route('/api/sessions', methods=['POST'])
@login_required
def create_session():
    """Create a new chat session."""
    body      = request.get_json() or {}
    title     = body.get('title', 'New conversation')[:120]
    sid       = str(uuid.uuid4())
    with _sessions_db() as conn:
        conn.execute("""
            INSERT INTO chat_sessions (session_id, user_id, client_id, title)
            VALUES (?, ?, ?, ?)
        """, (sid, current_user.id, current_user.client_id, title))
        conn.commit()
    return jsonify({'session_id': sid, 'title': title}), 201


@app.route('/api/sessions/<session_id>', methods=['PATCH'])
@login_required
def rename_session(session_id):
    """Rename a session title."""
    body  = request.get_json() or {}
    title = (body.get('title') or '').strip()[:120]
    if not title:
        return jsonify({'error': 'title is required'}), 400
    with _sessions_db() as conn:
        conn.execute("""
            UPDATE chat_sessions SET title = ?
            WHERE  session_id = ? AND user_id = ?
        """, (title, session_id, current_user.id))
        conn.commit()
    return jsonify({'success': True, 'title': title})


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    """Soft-delete a session (and its messages stay for audit)."""
    with _sessions_db() as conn:
        conn.execute("""
            UPDATE chat_sessions SET is_active = 0
            WHERE  session_id = ? AND user_id = ?
        """, (session_id, current_user.id))
        conn.commit()
    return jsonify({'success': True})


@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
@login_required
def get_session_messages(session_id):
    """Return all messages in a session (verifies ownership)."""
    with _sessions_db() as conn:
        # Ownership check
        sess = conn.execute("""
            SELECT session_id FROM chat_sessions
            WHERE session_id = ? AND user_id = ? AND is_active = 1
        """, (session_id, current_user.id)).fetchone()
        if not sess:
            return jsonify({'error': 'Session not found'}), 404

        rows = conn.execute("""
            SELECT message_id, role, content, raw_data, query_type, metadata, created_at
            FROM   chat_messages
            WHERE  session_id = ?
            ORDER  BY created_at ASC
        """, (session_id,)).fetchall()
    return jsonify({'messages': [dict(r) for r in rows]})


@app.route('/api/sessions/<session_id>/messages', methods=['POST'])
@login_required
def save_message(session_id):
    """Append a message to a session and bump last_active."""
    body = request.get_json() or {}
    role      = body.get('role')        # 'user' | 'assistant'
    content   = body.get('content', '')
    raw_data  = body.get('raw_data')    # list or None
    query_type = body.get('query_type')
    metadata  = body.get('metadata')   # dict or None
    title_hint = body.get('title_hint') # used to auto-title session from first user msg

    if role not in ('user', 'assistant') or not content:
        return jsonify({'error': 'role and content are required'}), 400

    mid = str(uuid.uuid4())
    raw_str  = _json.dumps(raw_data)  if raw_data  is not None else None
    meta_str = _json.dumps(metadata) if metadata  is not None else None

    with _sessions_db() as conn:
        # Ownership check
        sess = conn.execute("""
            SELECT title FROM chat_sessions
            WHERE session_id = ? AND user_id = ? AND is_active = 1
        """, (session_id, current_user.id)).fetchone()
        if not sess:
            return jsonify({'error': 'Session not found'}), 404

        conn.execute("""
            INSERT INTO chat_messages
                (message_id, session_id, user_id, role, content, raw_data, query_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (mid, session_id, current_user.id, role, content, raw_str, query_type, meta_str))

        # Auto-title the session from the first user message
        if role == 'user' and sess['title'] in ('New conversation', ''):
            auto_title = (title_hint or content)[:80]
            conn.execute("""
                UPDATE chat_sessions SET title = ?, last_active = CURRENT_TIMESTAMP
                WHERE  session_id = ?
            """, (auto_title, session_id))
        else:
            conn.execute("""
                UPDATE chat_sessions SET last_active = CURRENT_TIMESTAMP
                WHERE  session_id = ?
            """, (session_id,))

        conn.commit()

    return jsonify({'message_id': mid}), 201


if __name__ == '__main__':
    print("="*60)
    print("CPG Conversational AI Chatbot (RBAC Enabled)")
    print("="*60)
    print("Starting Flask server...")
    print("Open your browser and go to: http://localhost:5000")
    print("")
    print("Login with one of the sample users:")
    print("  - nestle_admin   / admin123")
    print("  - unilever_admin / admin123")
    print("  - itc_admin      / admin123")
    print("  - nestle_analyst / analyst123")
    print("  - nsm_rajesh     / nsm123  (NSM - full access)")
    print("  - zsm_amit       / zsm123  (ZSM - zone filtered)")
    print("  - asm_rahul      / asm123  (ASM - area filtered)")
    print("  - so_field1      / so123   (SO  - territory filtered)")
    print("")
    print("Press Ctrl+C to stop the server")
    print("="*60)

    # Start insights background thread here (not at module level) to avoid
    # a GIL conflict with Werkzeug's debug reloader forking the process.
    _insights_thread = threading.Thread(target=_insights_generation_loop, daemon=True)
    _insights_thread.start()

    # use_reloader=False prevents Werkzeug from forking a child process,
    # which would conflict with DuckDB releasing the GIL in the background thread.
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
