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

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, Response, stream_with_context
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from semantic_layer.semantic_layer import SemanticLayer
from llm.intent_parser_v2 import IntentParserV2
from semantic_layer.validator import SemanticValidator
from security.rls import RowLevelSecurity, UserContext
from security.auth import AuthManager, User
from query_engine.executor import QueryExecutor
from semantic_layer.orchestrator import QueryOrchestrator
from semantic_layer.cubejs_adapter import CubeJSAdapter, CubeJSError
from security.cubejs_token import generate_cubejs_token
from query_engine.query_validator import QueryValidator
import time
import traceback
import threading
from insights.hierarchy_insights_engine import HierarchyInsightsEngine

_DB_ENGINE = os.getenv('DB_ENGINE', 'duckdb').lower()


class _PgConn:
    """Thin psycopg2 wrapper that mimics the DuckDB connection interface."""

    class _Result:
        def __init__(self, cur):
            self._cur = cur

        def fetchone(self):
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str) -> '_Result':
        cur = self._conn.cursor()
        cur.execute(sql)
        return self._Result(cur)

    def close(self):
        self._conn.close()


def _get_analytics_conn(client_id: str):
    """Return a DuckDB or PostgreSQL connection for analytics queries."""
    if _DB_ENGINE == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            dbname=os.getenv('POSTGRES_DB', 'cpg_analytics'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
        )
        return _PgConn(conn)
    import duckdb
    client_config = auth_manager.get_client_config(client_id)
    db_path = str(_APP_ROOT / client_config['database_path'])
    return duckdb.connect(db_path, read_only=True)

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


@login_manager.unauthorized_handler
def unauthorized():
    """Return 401 JSON for API routes so the React app can detect session expiry."""
    from flask import request as _req
    if _req.path.startswith('/api/'):
        return jsonify({'error': 'Session expired. Please log in again.', 'expired': True}), 401
    return redirect(url_for('login'))

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

# Query result cache — avoid redundant LLM + DuckDB calls for identical questions
from flask_caching import Cache as _Cache
_query_cache = _Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

# Tenant schema mapping (client_id -> DuckDB schema name)
TENANT_SCHEMAS = {
    'nestle':   'client_nestle',
    'unilever': 'client_unilever',
    'itc':      'client_itc',
}

# Initialize hierarchy insights engine with absolute paths
insights_engine = HierarchyInsightsEngine(
    analytics_db_path=(
        'postgresql://' if _DB_ENGINE == 'postgresql'
        else str(_APP_ROOT / 'database' / 'cpg_multi_tenant.duckdb')
    ),
    users_db_path=str(_APP_ROOT / 'database' / 'users.db'),
)


def _insights_generation_loop():
    """Background daemon thread: generate insights on startup then every 6 hours."""
    time.sleep(10)  # let Flask finish initialising first
    while True:
        for client_id, schema_name in TENANT_SCHEMAS.items():
            try:
                count = insights_engine.generate_and_store(client_id, schema_name)
                app.logger.info("[Insights] %s: %d insights generated/refreshed", client_id, count)
            except Exception as exc:
                app.logger.error("[Insights] Error generating for %s: %s", client_id, exc)
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


# ── Shared scope-checking helpers (used by both /api/query and /api/query/stream) ──

def _kw_match(text, keywords):
    """Word-boundary aware keyword matching."""
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return True
    return False


def _check_scope(question, client_id, username):
    """
    Check whether a question is in-scope for analytics.

    Returns a response dict  {success, response, metadata}  if the question
    should be short-circuited (out-of-scope / help / permission-denied).
    Returns None  if the question is valid and should proceed to intent parsing.
    """
    q = question.lower().strip()

    # ── 1. Help / examples request ────────────────────────────────────────────
    help_keywords = [
        'what questions', 'what can i ask', 'what can you do',
        'give me examples', 'show examples', 'sample questions',
        'help me', 'what to ask', 'how to use',
    ]
    if any(kw in q for kw in help_keywords) or q in ('help', 'examples', 'suggestions'):
        suggestions = {
            "🏆 Ranking": ["Show top 5 brands by sales value",
                           "Top 10 SKUs by volume this month",
                           "Top distributors by sales value"],
            "📈 Trends":  ["Weekly sales trend for last 6 weeks",
                           "Monthly sales trend for this year"],
            "🔍 Compare": ["Compare sales by channel",
                           "Sales by state this month"],
            "📊 Snapshot":["Total sales this month",
                           "Total volume last month"],
            "🔬 Diagnostics":["Why did sales change?", "Why did sales drop?"],
        }
        html = '<div class="suggestions-box"><h3>📊 Sample Questions</h3>'
        for cat, qs in suggestions.items():
            html += f'<h4>{cat}</h4><ul>'
            for sq in qs:
                html += f'<li>"{sq}"</li>'
            html += '</ul>'
        html += '</div>'
        return {'success': True, 'response': html,
                'metadata': {'intent': 'help', 'query_id': f'HELP{int(time.time())}'}}

    # ── 2. Database / schema metadata questions ───────────────────────────────
    metadata_kws = [
        'table', 'column', 'schema', 'database', 'metadata',
        'what tables', 'what columns', 'show tables', 'describe table',
        'table structure', 'database structure', 'list tables',
        'what data', 'what fields', 'available fields',
    ]
    if _kw_match(q, metadata_kws):
        html = """
        <div style="padding:15px;background:#ffebee;border-left:4px solid #f44336;border-radius:4px;">
          <h3 style="color:#d32f2f;margin-bottom:10px;">❌ Out of Scope</h3>
          <p><strong>This assistant is for analytics queries only — not database metadata.</strong></p>
          <p style="margin-top:10px;padding:10px;background:white;border-radius:4px;">
            <strong>Try instead:</strong><br>
            • "Show top 5 brands by sales"<br>• "Weekly sales trend"<br>
            • "Why did sales change?"<br>• "Total sales this month"
          </p>
        </div>"""
        return {'success': False, 'response': html,
                'metadata': {'intent': 'out_of_scope_metadata'}}

    # ── 3. General knowledge / off-topic questions ────────────────────────────
    general_kws = [
        'who is', 'who was', 'who are', 'what is a', 'what are the',
        'when was', 'where is', 'where was', 'how to', 'how do i',
        'weather', 'news', 'stock market', 'sports', 'politics',
        'calculate', 'math', 'geography', 'history', 'science',
        'president', 'prime minister', 'actor', 'actress', 'celebrity',
        'movie', 'film', 'song', 'music', 'cricket', 'football',
    ]
    analytics_exceptions = ['what is the', 'what are my', 'how much', 'how many',
                            'how is', 'where is my', 'when is my']
    if _kw_match(q, general_kws) and not any(exc in q for exc in analytics_exceptions):
        html = """
        <div style="padding:15px;background:#fff3cd;border-left:4px solid #ffc107;border-radius:4px;">
          <h3 style="color:#856404;margin-bottom:10px;">⚠️ Out of Scope</h3>
          <p><strong>I'm a CPG sales analytics assistant — not a general knowledge chatbot.</strong></p>
          <p style="margin-top:10px;">Your question is outside my domain. I can only help with
             sales data, brand performance, distribution metrics, and trends.</p>
          <p style="margin-top:10px;padding:10px;background:white;border-radius:4px;">
            <strong>Try asking:</strong><br>
            • "Show top brands by sales this month"<br>
            • "Why did sales drop last week?"<br>
            • "Compare channel performance"
          </p>
        </div>"""
        return {'success': False, 'response': html,
                'metadata': {'intent': 'out_of_scope_general'}}

    # ── 4. Cross-client data access attempt ───────────────────────────────────
    all_clients = {
        'nestle':   ['nestle', 'nestlé'],
        'unilever': ['unilever', 'hindustan unilever', 'hul'],
        'itc':      ['itc', 'itc limited'],
    }
    mentioned = []
    for cid, aliases in all_clients.items():
        if cid != client_id and any(alias in q for alias in aliases):
            cfg = auth_manager.get_client_config(cid)
            if cfg:
                mentioned.append(cfg['client_name'])
    if mentioned:
        my_cfg = auth_manager.get_client_config(client_id)
        my_name = my_cfg['client_name'] if my_cfg else client_id
        html = f"""
        <div style="padding:15px;background:#ffebee;border-left:4px solid #f44336;border-radius:4px;">
          <h3 style="color:#d32f2f;margin-bottom:10px;">🚫 Permission Denied</h3>
          <p>You do not have access to data from: <strong>{', '.join(mentioned)}</strong></p>
          <p style="margin-top:10px;">Your account (<strong>{username}</strong>) can only
             access <strong>{my_name}</strong> data.</p>
        </div>"""
        return {'success': False, 'response': html,
                'metadata': {'intent': 'permission_denied'}}

    return None  # in-scope — proceed to intent parsing


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


@app.route('/api/cubejs-token', methods=['GET'])
@login_required
def get_cubejs_token():
    """Return a short-lived Cube.js JWT for the current user.

    The React frontend (Dashboard tab) can use this token to call the
    Cube.js API directly for live dashboard queries, bypassing Flask.
    Flask itself also uses this token when forwarding chat queries to Cube.js.
    """
    try:
        token = generate_cubejs_token(current_user)
        cubejs_url = os.getenv('CUBEJS_URL', 'http://localhost:4000')
        return jsonify({'token': token, 'cubejsUrl': cubejs_url})
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503


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
        app.logger.info("Processing query: '%s' | user: %s | client: %s",
                        question, current_user.username, current_user.client_id)

        # Scope check — handles help, out-of-scope, and cross-client questions
        scope_result = _check_scope(question, current_user.client_id, current_user.username)
        if scope_result is not None:
            return jsonify(scope_result)

        # Validate query for broadness
        try:
            validation_result = query_validator.validate_query(question)
        except Exception as e:
            app.logger.warning("Query validation error (skipping): %s", e)
            # If validation fails, continue to intent parsing
            validation_result = None

        if validation_result and validation_result.is_too_broad:
            app.logger.debug("Query too broad. Missing context: %s", validation_result.missing_context)

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

        # Cache check — skip expensive LLM+DB work on repeated identical queries
        _ck = f"q:{current_user.client_id}:{current_user.username}:{question.lower().strip()}"
        _cached = _query_cache.get(_ck)
        if _cached:
            app.logger.info("Cache hit for query key: %s", _ck[:60])
            return jsonify(_cached)

        # Parse intent
        start_time = time.time()
        try:
            semantic_query = components['intent_parser'].parse(question)
            app.logger.debug("Parsed intent: %s (confidence %.2f)", semantic_query.intent, semantic_query.confidence)
        except Exception as e:
            app.logger.error("Intent parsing failed: %s\n%s", e, traceback.format_exc())
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

        # Execute query via Cube.js (replaces AST builder + DuckDB executor)
        start_time = time.time()
        try:
            cubejs_token = generate_cubejs_token(current_user)
            adapter = CubeJSAdapter()

            if secured_query.intent.value == 'diagnostic':
                # Diagnostic queries: delegate to orchestrator which chains
                # multiple CubeJSAdapter calls via its existing workflow.
                # The orchestrator still uses the legacy executor internally;
                # swap it out for a CubeJS-backed executor when ready.
                result = components['orchestrator'].execute(secured_query)
            else:
                cube_query = adapter.build_query(secured_query)
                raw = adapter.execute(cube_query, cubejs_token)
                result = {
                    'query_type': 'single',
                    'sql': raw.get('sql', ''),
                    'results': raw.get('results', []),
                    'metadata': {
                        'row_count': len(raw.get('results', [])),
                        'execution_time_ms': 0,
                        'intent': secured_query.intent.value,
                    },
                }
        except CubeJSError as cube_err:
            # Cube.js unavailable or query failed — fall back to legacy pipeline
            app.logger.warning("Cube.js error (%s) — falling back to legacy executor", cube_err)
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

        response_payload = {
            'success': True,
            'response': response,
            'raw_data': result.get('results', []),
            'query_type': result.get('query_type', 'standard'),
            'metadata': {
                'user': current_user.username,
                'client': current_user.client_id,
                'intent': semantic_query.intent.value,
                'parse_time_ms': round(parse_time, 2),
                'exec_time_ms': round(exec_time, 2),
                'confidence': semantic_query.confidence,
                'sql': result.get('sql', '')
            }
        }
        _query_cache.set(_ck, response_payload)
        return jsonify(response_payload)

    except Exception as e:
        app.logger.error("Error processing query: %s", traceback.format_exc())

        auth_manager.log_query(
            current_user.id, current_user.username, current_user.client_id,
            question, None, False, str(e)
        )

        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


@app.route('/api/query/stream', methods=['POST'])
@login_required
def process_query_stream():
    """SSE streaming version of /api/query — emits live progress steps then final result."""
    data = request.json or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'error': 'Empty question'}), 400

    # Capture user identity before entering generator (Flask context exits after response starts)
    user_id        = current_user.id
    username       = current_user.username
    client_id      = current_user.client_id
    user_role      = current_user.role
    so_code        = current_user.so_code
    asm_code       = current_user.asm_code
    zsm_code       = current_user.zsm_code
    nsm_code       = current_user.nsm_code
    shier_level    = current_user.sales_hierarchy_level
    full_name      = getattr(current_user, 'full_name', username)

    def _sse(payload: dict) -> str:
        return f"data: {_json.dumps(payload)}\n\n"

    @stream_with_context
    def generate():
        import traceback as _tb

        yield _sse({"type": "progress", "step": "intent",
                    "msg": "🧠 Understanding your question…"})

        try:
            # ── Scope check (instant — no LLM needed) ─────────────────
            scope_result = _check_scope(question, client_id, username)
            if scope_result is not None:
                yield _sse({"type": "result", **scope_result})
                return

            # ── Cache check — skip LLM+DB on repeated questions ────────
            _ck = f"q:{client_id}:{username}:{question.lower().strip()}"
            _cached = _query_cache.get(_ck)
            if _cached:
                yield _sse({"type": "progress", "step": "format", "msg": "⚡ Loaded from cache…"})
                yield _sse({"type": "result", **_cached})
                return

            components = get_client_components(client_id)
            start = time.time()

            # ── Intent parsing (LLM call — slowest step) ──────────────
            semantic_query = components['intent_parser'].parse(question)
            parse_ms = (time.time() - start) * 1000

            yield _sse({"type": "progress", "step": "validate",
                        "msg": "✅ Validating query…"})

            errors = components['validator'].validate(semantic_query)
            if errors:
                yield _sse({"type": "result", "success": False,
                            "error": f"Validation errors: {', '.join(errors)}"})
                return

            hierarchy_restricted = {'SO', 'ASM', 'ZSM'}
            access_level = 'territory' if user_role in hierarchy_restricted else 'national'
            user_ctx = UserContext(
                user_id=username, role=user_role, data_access_level=access_level,
                states=[], regions=[],
                sales_hierarchy_level=shier_level,
                so_codes=[so_code]   if so_code   else [],
                asm_codes=[asm_code] if asm_code  else [],
                zsm_codes=[zsm_code] if zsm_code  else [],
                nsm_codes=[nsm_code] if nsm_code  else [],
            )
            secured_query = RowLevelSecurity.apply_security(semantic_query, user_ctx)

            yield _sse({"type": "progress", "step": "exec",
                        "msg": "⚡ Running analytics…"})

            # ── Execution ──────────────────────────────────────────────
            exec_start = time.time()
            try:
                cubejs_token = generate_cubejs_token_for(
                    username, client_id, user_role,
                    so_code=so_code, asm_code=asm_code,
                    zsm_code=zsm_code, nsm_code=nsm_code)
                adapter = CubeJSAdapter()
                if secured_query.intent.value == 'diagnostic':
                    result = components['orchestrator'].execute(secured_query)
                else:
                    cube_query = adapter.build_query(secured_query)
                    raw = adapter.execute(cube_query, cubejs_token)
                    result = {
                        'query_type': 'single',
                        'sql': raw.get('sql', ''),
                        'results': raw.get('results', []),
                        'metadata': {'row_count': len(raw.get('results', [])),
                                     'execution_time_ms': 0,
                                     'intent': secured_query.intent.value},
                    }
            except CubeJSError:
                result = components['orchestrator'].execute(secured_query)

            exec_ms = (time.time() - exec_start) * 1000

            yield _sse({"type": "progress", "step": "format",
                        "msg": "📊 Formatting results…"})

            if result['query_type'] == 'diagnostic':
                response_html = format_diagnostic_response(result)
            else:
                response_html = format_single_query_response(result)

            auth_manager.log_query(user_id, username, client_id, question,
                                   result.get('sql', ''), True, None)

            result_payload = {
                "success":    True,
                "response":   response_html,
                "raw_data":   result.get('results', []),
                "query_type": result.get('query_type', 'standard'),
                "metadata": {
                    "user":          username,
                    "client":        client_id,
                    "intent":        semantic_query.intent.value,
                    "parse_time_ms": round(parse_ms, 2),
                    "exec_time_ms":  round(exec_ms, 2),
                    "confidence":    semantic_query.confidence,
                    "sql":           result.get('sql', ''),
                },
            }
            _query_cache.set(_ck, result_payload)
            yield _sse({"type": "result", **result_payload})

        except Exception as exc:
            auth_manager.log_query(user_id, username, client_id, question,
                                   None, False, str(exc))
            yield _sse({"type": "result", "success": False,
                        "error": f"Unexpected error: {exc}"})

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def generate_cubejs_token_for(username, client_id, role, so_code=None, asm_code=None, zsm_code=None, nsm_code=None):
    """Generate Cube.js token from raw values (safe to call inside a generator)."""
    import os, jwt
    from datetime import datetime, timedelta, timezone
    secret = os.getenv('CUBEJS_API_SECRET')
    if not secret:
        raise RuntimeError('CUBEJS_API_SECRET not set')
    role_up = (role or '').upper()
    hierarchy_code = (
        so_code  if role_up == 'SO'  and so_code  else
        asm_code if role_up == 'ASM' and asm_code else
        zsm_code if role_up == 'ZSM' and zsm_code else
        nsm_code if role_up == 'NSM' and nsm_code else None
    )
    payload = {
        'clientId': client_id, 'username': username, 'role': role,
        'hierarchy_code': hierarchy_code,
        'exp': datetime.now(tz=timezone.utc) + timedelta(hours=8),
        'iat': datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def format_single_query_response(result):
    """Format single query results as HTML"""
    html_parts = []

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


@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Return all chart data for the Dashboard tab in a single call.

    Applies RLS: admin/NSM/analyst get full schema data; SO/ASM/ZSM get
    filtered by their sales_hierarchy_key rows only.
    """
    try:
        schema = TENANT_SCHEMAS.get(current_user.client_id)
        if not schema:
            return jsonify({'error': 'Unknown client'}), 400

        con = _get_analytics_conn(current_user.client_id)

        # ── Build RLS WHERE clause ────────────────────────────────────────────
        # Hierarchy-restricted roles filter through dim_sales_hierarchy join
        hierarchy_restricted = {'SO', 'ASM', 'ZSM'}
        rls_join  = ''
        rls_where = ''

        if current_user.role in hierarchy_restricted and current_user.sales_hierarchy_level:
            lvl = current_user.sales_hierarchy_level
            if lvl == 'SO' and current_user.so_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.so_code = '{current_user.so_code}'"
            elif lvl == 'ASM' and current_user.asm_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.asm_code = '{current_user.asm_code}'"
            elif lvl == 'ZSM' and current_user.zsm_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.zsm_code = '{current_user.zsm_code}'"

        # ── KPIs ─────────────────────────────────────────────────────────────
        kpi_sql = f"""
            SELECT
                COALESCE(SUM(f.net_value), 0)              AS total_sales,
                COUNT(DISTINCT f.invoice_number)            AS total_invoices
            FROM {schema}.fact_secondary_sales f
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
            {rls_where}
        """
        kpi_row = con.execute(kpi_sql).fetchone()
        total_sales    = float(kpi_row[0]) if kpi_row[0] else 0.0
        total_invoices = int(kpi_row[1])   if kpi_row[1] else 0

        # ── Top Brand ─────────────────────────────────────────────────────────
        top_brand_sql = f"""
            SELECT p.brand_name
            FROM {schema}.fact_secondary_sales f
            JOIN {schema}.dim_product p ON f.product_key = p.product_key
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
            {rls_where}
            GROUP BY p.brand_name ORDER BY SUM(f.net_value) DESC LIMIT 1
        """
        tb_row    = con.execute(top_brand_sql).fetchone()
        top_brand = tb_row[0] if tb_row else 'N/A'

        # ── Top Region ────────────────────────────────────────────────────────
        top_region_sql = f"""
            SELECT g.state_name
            FROM {schema}.fact_secondary_sales f
            JOIN {schema}.dim_geography g ON f.geography_key = g.geography_key
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
            {rls_where}
            GROUP BY g.state_name ORDER BY SUM(f.net_value) DESC LIMIT 1
        """
        tr_row     = con.execute(top_region_sql).fetchone()
        top_region = tr_row[0] if tr_row else 'N/A'

        # ── Sales by Brand (top 8) ────────────────────────────────────────────
        brand_sql = f"""
            SELECT p.brand_name, CAST(SUM(f.net_value) AS FLOAT8) AS sales
            FROM {schema}.fact_secondary_sales f
            JOIN {schema}.dim_product p ON f.product_key = p.product_key
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
            {rls_where}
            GROUP BY p.brand_name ORDER BY 2 DESC LIMIT 8
        """
        by_brand = [
            {'brand_name': r[0], 'sales': float(r[1])}
            for r in con.execute(brand_sql).fetchall()
        ]

        # ── Weekly Sales Trend (last 8 weeks) ─────────────────────────────────
        trend_sql = f"""
            SELECT
                DATE_TRUNC('week', f.invoice_date)::VARCHAR AS week,
                CAST(SUM(f.net_value) AS FLOAT8)            AS sales
            FROM {schema}.fact_secondary_sales f
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '56' DAY
            {rls_where}
            GROUP BY 1 ORDER BY 1
        """
        trend = [
            {'week': r[0][:10], 'sales': float(r[1])}
            for r in con.execute(trend_sql).fetchall()
        ]

        # ── Sales by Channel ──────────────────────────────────────────────────
        channel_sql = f"""
            SELECT c.channel_name, CAST(SUM(f.net_value) AS FLOAT8) AS sales
            FROM {schema}.fact_secondary_sales f
            JOIN {schema}.dim_channel c ON f.channel_key = c.channel_key
            {rls_join}
            WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
            {rls_where}
            GROUP BY c.channel_name ORDER BY 2 DESC
        """
        by_channel = [
            {'channel_name': r[0], 'sales': float(r[1])}
            for r in con.execute(channel_sql).fetchall()
        ]

        con.close()

        return jsonify({
            'kpis': {
                'total_sales':    total_sales,
                'total_invoices': total_invoices,
                'top_brand':      top_brand,
                'top_region':     top_region,
            },
            'by_brand':   by_brand,
            'trend':      trend,
            'by_channel': by_channel,
        })

    except Exception as e:
        app.logger.error("[Dashboard] Error: %s", traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard/drilldown', methods=['GET'])
@login_required
def dashboard_drilldown():
    """Return detail data for a clicked chart element (brand → SKUs, channel → brands, week → days)."""
    drill_type = request.args.get('drill_type', '').strip()
    value      = request.args.get('value', '').strip()

    if not drill_type or not value:
        return jsonify({'error': 'drill_type and value are required'}), 400
    if drill_type not in ('brand_skus', 'channel_brands', 'week_days'):
        return jsonify({'error': 'Invalid drill_type'}), 400

    # Sanitise the incoming value — strip SQL-dangerous chars, keep alphanumeric + common label chars
    import re as _re
    if not _re.match(r'^[\w\s\-\.\/:]+$', value):
        return jsonify({'error': 'Invalid value'}), 400
    # Escape single quotes for safe f-string interpolation
    safe_val = value.replace("'", "''")

    try:
        schema = TENANT_SCHEMAS.get(current_user.client_id)
        if not schema:
            return jsonify({'error': 'Unknown client'}), 400

        con = _get_analytics_conn(current_user.client_id)

        # ── RLS (same logic as /api/dashboard) ───────────────────────────────
        hierarchy_restricted = {'SO', 'ASM', 'ZSM'}
        rls_join  = ''
        rls_where = ''
        if current_user.role in hierarchy_restricted and current_user.sales_hierarchy_level:
            lvl = current_user.sales_hierarchy_level
            if lvl == 'SO' and current_user.so_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.so_code = '{current_user.so_code}'"
            elif lvl == 'ASM' and current_user.asm_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.asm_code = '{current_user.asm_code}'"
            elif lvl == 'ZSM' and current_user.zsm_code:
                rls_join  = f'JOIN {schema}.dim_sales_hierarchy sh ON f.sales_hierarchy_key = sh.hierarchy_key'
                rls_where = f"AND sh.zsm_code = '{current_user.zsm_code}'"

        # ── Queries per drill type ────────────────────────────────────────────
        if drill_type == 'brand_skus':
            sql = f"""
                SELECT p.sku_name                                  AS label,
                       CAST(SUM(f.net_value)       AS FLOAT8)      AS sales,
                       COUNT(DISTINCT f.invoice_number)            AS invoices
                FROM {schema}.fact_secondary_sales f
                JOIN {schema}.dim_product p ON f.product_key = p.product_key
                {rls_join}
                WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
                  AND p.brand_name = '{safe_val}'
                {rls_where}
                GROUP BY p.sku_name ORDER BY 2 DESC LIMIT 10
            """
            title = f'{value} — Top SKUs (Last 30 Days)'

        elif drill_type == 'channel_brands':
            sql = f"""
                SELECT p.brand_name                                AS label,
                       CAST(SUM(f.net_value)       AS FLOAT8)      AS sales,
                       COUNT(DISTINCT f.invoice_number)            AS invoices
                FROM {schema}.fact_secondary_sales f
                JOIN {schema}.dim_product  p  ON f.product_key  = p.product_key
                JOIN {schema}.dim_channel  c  ON f.channel_key  = c.channel_key
                {rls_join}
                WHERE f.invoice_date >= CURRENT_DATE - INTERVAL '30' DAY
                  AND c.channel_name = '{safe_val}'
                {rls_where}
                GROUP BY p.brand_name ORDER BY 2 DESC LIMIT 8
            """
            title = f'{value} Channel — Brand Breakdown'

        else:  # week_days
            sql = f"""
                SELECT CAST(f.invoice_date AS VARCHAR)             AS label,
                       CAST(SUM(f.net_value)       AS FLOAT8)      AS sales,
                       COUNT(DISTINCT f.invoice_number)            AS invoices
                FROM {schema}.fact_secondary_sales f
                {rls_join}
                WHERE DATE_TRUNC('week', f.invoice_date) = '{safe_val}'::DATE
                {rls_where}
                GROUP BY 1 ORDER BY 1
            """
            title = f'Week of {value} — Daily Sales'

        rows  = con.execute(sql).fetchall()
        total = sum(r[1] for r in rows) or 1
        items = [
            {
                'label':    r[0],
                'sales':    float(r[1]),
                'invoices': int(r[2]),
                'pct':      round(float(r[1]) / total * 100, 1),
            }
            for r in rows
        ]
        con.close()
        return jsonify({'title': title, 'items': items})

    except Exception as exc:
        app.logger.error("[Drilldown] Error: %s", traceback.format_exc())
        return jsonify({'error': str(exc)}), 500


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
