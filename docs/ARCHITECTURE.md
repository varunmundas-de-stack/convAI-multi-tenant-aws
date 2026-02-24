# 🏗️ ARCHITECTURE - CPG Conversational AI with Multi-Client RBAC

**Complete End-to-End System Architecture**

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Breakdown](#component-breakdown)
4. [Data Flow](#data-flow)
5. [Multi-Client Isolation](#multi-client-isolation)
6. [Security Architecture](#security-architecture)
7. [Database Schema](#database-schema)
8. [Query Processing Chain](#query-processing-chain)
9. [Technology Stack](#technology-stack)
10. [Deployment Architecture](#deployment-architecture)
11. [Schema Anonymization](#-schema-anonymization-security-enhancement) ⭐ NEW
12. [System Actors and Responsibilities](#-system-actors-and-responsibilities) ⭐ NEW

---

## 🎯 System Overview

### **What This System Does**

A **secure, multi-tenant conversational analytics platform** for CPG (Consumer Packaged Goods) companies that:
- ✅ Allows natural language queries about sales data
- ✅ Isolates each client's data completely (Nestle, Unilever, ITC)
- ✅ Authenticates users with role-based access control
- ✅ Generates SQL from natural language WITHOUT exposing business data to LLM
- ✅ Provides audit trail for all queries

### **Key Innovation**

**Semantic Layer Architecture** - Business questions are translated to SQL using a **rule-based semantic layer**, NOT by sending data to LLM. This protects sensitive business information.

---

## 🏛️ Architecture Diagram

### **High-Level System Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                          │
│                    Chrome/Firefox/Edge                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK WEB APPLICATION                        │
│                  (app_with_auth.py - Port 5000)                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Login      │  │   Session    │  │   Logout     │         │
│  │   /login     │  │   Manager    │  │   /logout    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │             Query Processing Endpoint                    │  │
│  │                 /api/query (POST)                        │  │
│  │  • Validates user session                               │  │
│  │  • Loads client-specific YAML config                    │  │
│  │  • Routes to appropriate semantic layer                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
┌───────────────────┐ ┌──────────────┐ ┌──────────────┐
│   Nestle YAML     │ │ Unilever YAML│ │   ITC YAML   │
│   (Schema:        │ │ (Schema:     │ │ (Schema:     │
│   client_nestle)  │ │ client_unilever)│ │ client_itc)  │
└─────────┬─────────┘ └──────┬───────┘ └──────┬───────┘
          │                  │                 │
          └──────────────────┼─────────────────┘
                             ▼
        ┌────────────────────────────────────────┐
        │     SEMANTIC LAYER COMPONENTS          │
        ├────────────────────────────────────────┤
        │  1. Intent Parser (NL → Structured)    │
        │  2. Validator (Check metrics/dims)     │
        │  3. Query Builder (AST-based SQL)      │
        │  4. Row-Level Security (RLS filter)    │
        └────────────────┬───────────────────────┘
                         │ Generated SQL
                         ▼
        ┌────────────────────────────────────────┐
        │         QUERY EXECUTOR                 │
        │  • Read-only connection                │
        │  • Schema-qualified queries            │
        │  • Result formatting                   │
        └────────────────┬───────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ client_nestle   │ │client_unilever  │ │  client_itc     │
│   (Schema)      │ │   (Schema)      │ │   (Schema)      │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • fact_sales    │ │ • fact_sales    │ │ • fact_sales    │
│ • dim_product   │ │ • dim_product   │ │ • dim_product   │
│ • dim_geography │ │ • dim_geography │ │ • dim_geography │
│ • dim_customer  │ │ • dim_customer  │ │ • dim_customer  │
│ • dim_channel   │ │ • dim_channel   │ │ • dim_channel   │
│ • dim_date      │ │ • dim_date      │ │ • dim_date      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │   DuckDB Database        │
              │ cpg_multi_tenant.duckdb  │
              │   (Single File ~10MB)    │
              └──────────────────────────┘

              ┌──────────────────────────┐
              │   SQLite Database        │
              │      users.db            │
              │ • Users table            │
              │ • Clients table          │
              │ • Audit log              │
              └──────────────────────────┘
```

---

## 🧩 Component Breakdown

### **1. Frontend Layer**

#### **HTML Templates**
```
frontend/templates/
├── login.html           # User authentication form
└── chat.html           # Full-screen chat interface
```

**Features:**
- Clean login (no demo credentials shown)
- Full viewport chat interface (no nested scrolling)
- User info display (name, company, role)
- Logout button
- Clickable suggestion chips
- Real-time query/response

---

### **2. Authentication Layer**

#### **Flask-Login + Custom AuthManager**

```python
# security/auth.py
class AuthManager:
    - authenticate(username, password)
    - get_user_by_id(user_id)
    - get_client_config(client_id)
    - log_query(user_id, query, sql, success)
```

**Security Features:**
- ✅ Bcrypt password hashing
- ✅ Session management (expires on browser close)
- ✅ Strong session protection
- ✅ CSRF protection
- ✅ HTTP-only cookies

---

### **3. Semantic Layer**

#### **Purpose:** Translate business questions to SQL WITHOUT sending data to LLM

**Files:**
```
semantic_layer/
├── semantic_layer.py       # Core: YAML config parser
├── intent_parser_v2.py     # NL → SemanticQuery
├── validator.py            # Validate metrics/dimensions
├── query_builder.py        # SemanticQuery → SQL AST
├── ast_builder.py          # SQL AST nodes
├── orchestrator.py         # Coordinate execution
└── configs/
    ├── client_nestle.yaml
    ├── client_unilever.yaml
    └── client_itc.yaml
```

**Key Concept:**
```
Natural Language → Semantic Query → SQL AST → SQL String
     (Rule-based pattern matching, NO raw data to LLM)
```

---

### **4. Query Processing Chain**

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: PARSE INTENT                                       │
│  Input: "Show top 5 brands by sales"                        │
│  Output: SemanticQuery(                                     │
│            intent=RANKING,                                  │
│            metric=secondary_sales_value,                    │
│            dimension=brand_name,                            │
│            limit=5                                          │
│          )                                                  │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: VALIDATE                                           │
│  Check:                                                     │
│  ✓ Metric exists in YAML                                   │
│  ✓ Dimension exists in YAML                                │
│  ✓ Metric allows this dimension                            │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: APPLY ROW-LEVEL SECURITY (RLS)                    │
│  Based on user role/permissions:                           │
│  • Admin: All data                                         │
│  • Analyst: All data (currently same as admin)             │
│  • Future: Regional analysts → filter by state/zone        │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: BUILD SQL (AST-Based)                             │
│  SELECT p.brand_name, SUM(net_value) AS sales_value        │
│  FROM client_nestle.fact_secondary_sales f                 │
│  LEFT JOIN client_nestle.dim_product p                     │
│    ON f.product_key = p.product_key                        │
│  GROUP BY p.brand_name                                     │
│  ORDER BY sales_value DESC                                 │
│  LIMIT 5                                                   │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: EXECUTE SQL                                        │
│  • Read-only connection                                    │
│  • Schema-qualified tables (client_nestle.*)               │
│  • Query timeout protection                                │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: FORMAT RESPONSE                                    │
│  • HTML table                                              │
│  • Collapsible SQL query section                           │
│  • Metadata (execution time, confidence)                   │
│  • NO LLM CALL #2 (security measure)                       │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: AUDIT LOG                                          │
│  INSERT INTO audit_log:                                     │
│  • User ID, username, client                               │
│  • Original question                                       │
│  • Generated SQL                                           │
│  • Success/failure                                         │
│  • Timestamp                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Multi-Client Isolation

### **Critical Security Feature:** Complete Data Isolation

#### **Mechanism 1: Schema-Level Isolation (Database)**

```sql
-- Three separate schemas in one DuckDB file
CREATE SCHEMA client_nestle;
CREATE SCHEMA client_unilever;
CREATE SCHEMA client_itc;

-- Each schema has its own tables
client_nestle.fact_secondary_sales
client_nestle.dim_product
...

client_unilever.fact_secondary_sales
client_unilever.dim_product
...
```

**Benefit:** DuckDB enforces schema separation - no cross-schema queries possible without explicit schema prefix.

---

#### **Mechanism 2: YAML Config Isolation (Application)**

**When nestle_analyst logs in:**
```python
client_id = "nestle"  # From user record
config_path = f"semantic_layer/configs/client_{client_id}.yaml"
semantic_layer = SemanticLayer(config_path, client_id="nestle")
# ONLY loads client_nestle.yaml
# ONLY queries client_nestle.* tables
```

**When unilever_analyst logs in:**
```python
client_id = "unilever"
config_path = f"semantic_layer/configs/client_{client_id}.yaml"
semantic_layer = SemanticLayer(config_path, client_id="unilever")
# ONLY loads client_unilever.yaml
# ONLY queries client_unilever.* tables
```

**Result:**
- ✅ Nestle YAML is NEVER loaded for Unilever users
- ✅ Nestle schema is NEVER queried for Unilever users
- ✅ Zero cross-client data leakage

---

#### **Mechanism 3: Permission Checking (Frontend)**

```python
# Detect cross-client queries
if "unilever" in question.lower() and current_user.client_id == "nestle":
    return "🚫 Permission Denied: You do not have access to Unilever data"
```

---

## 🔒 Security Architecture

### **Multi-Layer Security**

#### **Layer 1: Authentication**
- Bcrypt password hashing (12 rounds)
- Session management with Flask-Login
- Session expires on browser close
- HTTP-only, SameSite cookies
- Strong session protection

#### **Layer 2: Authorization (RBAC)**
- User → Client mapping (users.client_id)
- Role-based access (admin, analyst)
- Client-specific YAML loading
- Schema-qualified SQL generation

#### **Layer 3: Query Security**
- AST-based SQL generation (injection-proof)
- Read-only database connection
- Query timeout limits
- No dynamic SQL string concatenation

#### **Layer 4: Data Protection**
- Schema isolation (database-level)
- YAML config isolation (app-level)
- No business data sent to LLM
- Formatted responses (no LLM call #2)

#### **Layer 5: Audit Trail**
- Every query logged with user identity
- SQL statements captured
- Success/failure tracking
- Timestamp for compliance

---

## 💾 Database Schema

### **User Authentication Database (SQLite)**

**File:** `database/users.db`

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    full_name TEXT,
    client_id TEXT NOT NULL,  -- Links to clients table
    role TEXT NOT NULL,        -- 'admin' or 'analyst'
    created_at TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Clients table
CREATE TABLE clients (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    database_path TEXT NOT NULL,
    config_path TEXT NOT NULL,
    schema_name TEXT NOT NULL
);

-- Audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    client_id TEXT NOT NULL,
    question TEXT NOT NULL,
    sql_query TEXT,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

### **Analytics Database (DuckDB)**

**File:** `database/cpg_multi_tenant.duckdb` (~10MB)

#### **Schema Structure (Per Client)**

```sql
-- Example for client_nestle schema
CREATE SCHEMA client_nestle;

-- Fact table
CREATE TABLE client_nestle.fact_secondary_sales (
    transaction_id INTEGER PRIMARY KEY,
    date_key INTEGER,
    product_key INTEGER,
    geography_key INTEGER,
    customer_key INTEGER,
    channel_key INTEGER,
    invoice_number TEXT,
    net_value DECIMAL(10,2),
    gross_value DECIMAL(10,2),
    quantity INTEGER
);

-- Dimension tables
CREATE TABLE client_nestle.dim_product (
    product_key INTEGER PRIMARY KEY,
    sku_code TEXT,
    sku_name TEXT,
    brand_name TEXT,
    category_name TEXT
);

CREATE TABLE client_nestle.dim_geography (
    geography_key INTEGER PRIMARY KEY,
    state_name TEXT,
    zone_name TEXT,
    district_name TEXT,
    town_name TEXT
);

CREATE TABLE client_nestle.dim_customer (
    customer_key INTEGER PRIMARY KEY,
    distributor_name TEXT,
    retailer_name TEXT,
    outlet_name TEXT,
    outlet_type TEXT
);

CREATE TABLE client_nestle.dim_channel (
    channel_key INTEGER PRIMARY KEY,
    channel_name TEXT,
    channel_type TEXT
);

CREATE TABLE client_nestle.dim_date (
    date_key INTEGER PRIMARY KEY,
    date DATE,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name TEXT,
    week INTEGER,
    day_name TEXT,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    fiscal_week INTEGER
);
```

**Same structure repeated for:**
- `client_unilever` schema
- `client_itc` schema

---

## 🔄 Query Processing Chain (Detailed)

### **Chain of Thought: "Show top 5 brands by sales"**

#### **Phase 1: User Input → Intent Recognition**

```python
# Input
question = "Show top 5 brands by sales"

# Intent Parser (intent_parser_v2.py)
intent = recognize_pattern(question)
# Pattern match: "top N [dimension] by [metric]" → RANKING intent

# Output
semantic_query = SemanticQuery(
    intent=IntentType.RANKING,
    metric_request=MetricRequest(
        primary_metric="secondary_sales_value"
    ),
    dimensionality=Dimensionality(
        group_by=["brand_name"]
    ),
    sorting=Sorting(
        order_by="secondary_sales_value",
        direction="DESC",
        limit=5
    )
)
```

---

#### **Phase 2: Validation**

```python
# Validator (validator.py)
errors = []

# Check metric exists
if "secondary_sales_value" not in semantic_layer.metrics:
    errors.append("Unknown metric")

# Check dimension exists
if "brand_name" not in dimension_attributes:
    errors.append("Unknown dimension")

# Check metric allows this dimension
allowed_dims = metric_config['allowed_dimensions']
if "product" not in allowed_dims:
    errors.append("Invalid metric-dimension combination")

if errors:
    raise ValidationError(errors)
```

---

#### **Phase 3: SQL Generation (AST-Based)**

```python
# Query Builder (query_builder.py)
# Build AST (Abstract Syntax Tree)

ast = Query(
    select=SelectClause([
        ColumnRef(column="brand_name", table="p", alias="brand_name"),
        AggregateExpr(
            func="SUM",
            expr=ColumnRef(column="net_value", table="f"),
            alias="secondary_sales_value"
        )
    ]),
    from_clause=FromClause(
        table="client_nestle.fact_secondary_sales",
        alias="f"
    ),
    joins=[
        JoinClause(
            join_type="LEFT",
            table="client_nestle.dim_product",  # Schema-qualified!
            alias="p",
            on_condition=BinaryExpr(
                left=ColumnRef("product_key", "f"),
                operator="=",
                right=ColumnRef("product_key", "p")
            )
        )
    ],
    group_by=GroupByClause(["p.brand_name"]),
    order_by=OrderByClause([("secondary_sales_value", "DESC")]),
    limit=LimitClause(5)
)

# Convert AST to SQL string
sql = ast.to_sql()
```

---

#### **Phase 4: Execution**

```python
# Executor (executor.py)
conn = duckdb.connect('database/cpg_multi_tenant.duckdb', read_only=True)
result = conn.execute(sql).fetchall()

# Result:
# [
#   {'brand_name': 'Brand-B-nestle', 'secondary_sales_value': 377845.26},
#   {'brand_name': 'Brand-D-nestle', 'secondary_sales_value': 364520.18},
#   ...
# ]
```

---

#### **Phase 5: Response Formatting**

```python
# Format as HTML table (NO LLM CALL)
html = format_single_query_response(result)

# Output:
"""
<div class="results-table">
    <table>
        <thead><tr><th>brand_name</th><th>secondary_sales_value</th></tr></thead>
        <tbody>
            <tr><td>Brand-B-nestle</td><td>377,845.26</td></tr>
            ...
        </tbody>
    </table>
</div>
<div class="sql-section">
    <button onclick="toggleSQL()">Show SQL Query</button>
    <pre class="sql-query" style="display:none;">
        SELECT p.brand_name, SUM(net_value) AS secondary_sales_value
        FROM client_nestle.fact_secondary_sales f
        LEFT JOIN client_nestle.dim_product p ON f.product_key = p.product_key
        GROUP BY p.brand_name
        ORDER BY secondary_sales_value DESC
        LIMIT 5
    </pre>
</div>
"""
```

---

## 🛠️ Technology Stack

### **Backend**
- **Python 3.12** - Core language
- **Flask 3.1** - Web framework
- **Flask-Login 0.6** - Session management
- **DuckDB 1.4** - Analytics database (embedded)
- **SQLite 3** - User authentication database
- **Pydantic 2.12** - Data validation
- **Bcrypt 5.0** - Password hashing
- **PyYAML 6.0** - Config parsing

### **Frontend**
- **HTML5/CSS3** - Modern UI
- **JavaScript (Vanilla)** - No frameworks, lightweight
- **Fetch API** - AJAX requests

### **Optional (Not Currently Used)**
- **Ollama** - Local LLM (fallback for intent parsing)
- **Anthropic Claude** - Cloud LLM (disabled for security)

---

## 🚀 Deployment Architecture

### **Development (Current)**

```
Windows Machine
├── Python 3.12 (local)
├── Flask dev server (localhost:5000)
├── DuckDB file (~10MB)
├── SQLite file (~32KB)
└── No external dependencies
```

**Command:**
```bash
python frontend/app_with_auth.py
```

---

### **Production (Recommended)**

```
┌─────────────────────────────────────────┐
│  Load Balancer (NGINX)                  │
│  • SSL/TLS termination                  │
│  • Rate limiting                        │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Flask  │ │ Flask  │ │ Flask  │
│ Worker │ │ Worker │ │ Worker │
│ (Gunicorn)│ │(Gunicorn)│ │(Gunicorn)│
└────┬───┘ └────┬───┘ └────┬───┘
     │          │          │
     └──────────┼──────────┘
                ▼
     ┌──────────────────────┐
     │  DuckDB Database     │
     │  (Read-only mount)   │
     └──────────────────────┘
     ┌──────────────────────┐
     │  SQLite Database     │
     │  (Separate volume)   │
     └──────────────────────┘
```

**Production Stack:**
- Gunicorn (WSGI server) - 4 workers
- NGINX (Reverse proxy + SSL)
- Systemd (Process management)
- Let's Encrypt (Free SSL)

---

## 📊 Performance Characteristics

### **Query Performance**
- **Intent Parsing:** 5-15ms (rule-based, no LLM)
- **SQL Generation:** 2-5ms (AST-based)
- **Query Execution:** 10-50ms (DuckDB in-memory)
- **Total Response:** 20-80ms (sub-100ms!)

### **Scalability**
- **Concurrent Users:** 50-100 (single Flask instance)
- **Data Size:** Up to 1GB per client (DuckDB limit: 1TB)
- **Query Complexity:** Simple → Medium (no complex joins)

### **Resource Usage**
- **Memory:** 100-200MB (Flask + DuckDB)
- **Disk:** ~10MB (database) + ~5MB (code)
- **CPU:** Minimal (< 5% idle, <20% under load)

---

## 🎯 What Happens When

### **User Logs In**
```
1. User enters credentials
2. Flask validates password (bcrypt)
3. Session cookie created (HTTP-only, SameSite)
4. User redirected to /
5. Client config loaded based on user.client_id
```

### **User Asks Question**
```
1. Frontend sends POST to /api/query
2. Flask checks session (login_required)
3. Gets client_id from current_user
4. Loads client-specific YAML
5. Parses intent (rule-based)
6. Validates query
7. Applies RLS (row-level security)
8. Builds SQL AST
9. Generates SQL string
10. Executes on DuckDB
11. Formats HTML response
12. Logs to audit trail
13. Returns JSON to frontend
```

### **User Clicks Suggestion Chip**
```
1. JavaScript fills input box
2. Automatically triggers sendMessage()
3. Same flow as typing question
```

### **User Logs Out**
```
1. /logout route called
2. Flask-Login clears session
3. Session cookie deleted
4. Redirect to /login
```

### **Server Restarts**
```
1. Sessions expire (not persistent)
2. All users redirected to /login
3. Client components cache cleared
4. Fresh initialization
```

---

## 🔒 Schema Anonymization (Security Enhancement)

### **Overview**

Schema anonymization protects your database metadata (table names, column names, metric names) when using external LLM services like Claude API or OpenAI.

### **Problem**

Without anonymization, external LLMs receive real schema information:
- ❌ Real metric names: `secondary_sales_value`, `margin_amount`
- ❌ Real dimension names: `brand_name`, `distributor_name`
- ❌ Business descriptions: "Net invoiced value to retailers"
- **Risk**: Exposes your business model and data structure to third-party services

### **Solution**

Anonymization layer that:
- ✅ Converts real names to generic names before sending to LLM
- ✅ De-anonymizes LLM responses locally
- ✅ Protects intellectual property and business logic

### **How It Works**

```
YAML Config (Local)
  metrics:
    secondary_sales_value: "Net invoiced value"
        ↓
Anonymization (Local)
  secondary_sales_value → value_metric_001
        ↓
External LLM Sees
  "value_metric_001" (anonymous) ✅
        ↓
LLM Returns
  {"metric": "value_metric_001"}
        ↓
De-anonymization (Local)
  value_metric_001 → secondary_sales_value
        ↓
SQL Generation (Local)
  SELECT SUM(net_value) FROM fact_secondary_sales
```

### **Anonymization Strategies**

| Strategy | Example | Use Case |
|----------|---------|----------|
| **generic** | `metric_001`, `dimension_001` | Maximum security |
| **category** ⭐ | `value_metric_001`, `product_dimension_001` | **Recommended for production** |
| **hash** | `metric_a3b5c7d1` | Consistent across sessions |

### **What Gets Protected**

| Data Type | Without Anonymization | With Anonymization |
|-----------|----------------------|-------------------|
| Metric names | `secondary_sales_value` ❌ | `value_metric_001` ✅ |
| Dimension names | `brand_name` ❌ | `product_dimension_001` ✅ |
| Descriptions | "Net invoiced value" ❌ | "Monetary value measurement" ✅ |
| Table names | Never sent ✅ | Never sent ✅ |
| SQL queries | Never sent ✅ | Never sent ✅ |

### **Enable Anonymization**

```bash
# Set environment variable
export ANONYMIZE_SCHEMA=true

# Or in code
parser = IntentParserV2(
    semantic_layer=semantic_layer,
    anonymize_schema=True,
    anonymization_strategy="category"
)
```

### **Multi-Client Example**

**Nestlé and ITC both ask**: "Show me sales by brand"

| Client | Real Metric | Real Dimension | Sent to LLM |
|--------|------------|----------------|-------------|
| **Nestlé** | `secondary_sales_value` | `brand_name` | `value_metric_001` ✅ |
| **ITC** | `net_trade_sales` | `brand` | `value_metric_001` ✅ |

**Result**: External LLM sees identical anonymous names for both clients, cannot differentiate them!

### **Performance Impact**

- Mapping creation: ~1-2ms (one-time)
- Anonymization: ~0.1ms per request
- De-anonymization: ~0.1ms per response
- **Total overhead**: < 1% of query time

### **Documentation**

- **Quick Start**: [ANONYMIZATION_QUICKSTART.md](ANONYMIZATION_QUICKSTART.md)
- **Complete Guide**: [docs/ANONYMIZATION_GUIDE.md](docs/ANONYMIZATION_GUIDE.md)
- **Examples**: [NESTLE_ITC_EXAMPLE.md](NESTLE_ITC_EXAMPLE.md)
- **Actors & Responsibilities**: [ACTORS_AND_RESPONSIBILITIES.md](ACTORS_AND_RESPONSIBILITIES.md)

---

## 🎭 System Actors and Responsibilities

### **Who Does What in the Query Pipeline**

Understanding the actors and their responsibilities is critical for security audits and troubleshooting.

### **The Actors**

| Actor | Location | Trust Level | Responsibility |
|-------|----------|-------------|----------------|
| **End User** | Browser | Authenticated | Submit questions |
| **Flask Web Server** | Your Infrastructure | Trusted | Orchestrate flow |
| **Authentication Service** | Your Infrastructure | Trusted | Verify user identity |
| **Semantic Layer Service** | Your Infrastructure | Trusted | **Generate SQL** |
| **Anonymization Service** | Your Infrastructure | Trusted | **Anonymize/De-anonymize** |
| **External LLM** | External (Anthropic/OpenAI) | **Untrusted** | Parse intent only |
| **DuckDB Service** | Your Infrastructure | Trusted | **Execute queries** |

### **Critical Questions Answered**

#### **Q: Who creates the SQL query?**
**A**: **Semantic Layer Service** (your Flask server)
- NOT the External LLM!
- Reads from YAML files (local)
- Uses real table/column names
- Happens AFTER LLM returns intent

#### **Q: Who de-anonymizes the LLM response?**
**A**: **Anonymization Service** (your Flask server)
- Converts: `value_metric_001` → `secondary_sales_value`
- Uses in-memory mapping (never sent to LLM)
- Happens BEFORE SQL generation

#### **Q: Who executes the query on the database?**
**A**: **DuckDB Service** (your database engine)
- Executes SQL generated by Semantic Layer
- Enforces schema isolation
- Returns actual data

#### **Q: What does the External LLM do?**
**A**: **ONLY parses intent** (external, untrusted)
- Receives: Anonymous names (`value_metric_001`) ✅
- Returns: Structured intent JSON
- **NEVER** generates SQL
- **NEVER** accesses database
- **NEVER** sees real schema (with anonymization)

### **Data Flow with Actors**

```
┌─────────────────────────────────────────────────────┐
│  1. END USER (Browser)                              │
│     "Show me sales by brand for last 4 weeks"      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  2. FLASK WEB SERVER (Your Infrastructure)          │
│     • Authenticate user → client_id = "nestle"      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  3. SEMANTIC LAYER SERVICE (Your Infrastructure)    │
│     • Load client_nestle.yaml                       │
│     • Extract metrics: [secondary_sales_value, ...] │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  4. ANONYMIZATION SERVICE (Your Infrastructure)     │
│     • Anonymize: secondary_sales_value              │
│                  → value_metric_001                 │
│     • Store mapping (in-memory, local only)         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  5. EXTERNAL LLM (Anthropic/OpenAI - Untrusted)     │
│     • Receives: "value_metric_001" (anonymous) ✅   │
│     • Returns: {"metric": "value_metric_001"}       │
│     • NEVER sees SQL, tables, or database           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  6. ANONYMIZATION SERVICE (Your Infrastructure)     │
│     • De-anonymize: value_metric_001                │
│                     → secondary_sales_value         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  7. SEMANTIC LAYER SERVICE (Your Infrastructure)    │
│     • Generate SQL:                                 │
│       SELECT p.brand_name,                          │
│              SUM(f.net_value)                       │
│       FROM client_nestle.fact_secondary_sales f     │
│       ...                                           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  8. DUCKDB SERVICE (Your Infrastructure)            │
│     • Execute SQL on database                       │
│     • Return results: [(Maggi, 1500000), ...]       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  9. END USER (Browser)                              │
│     • Display results in table/chart                │
└─────────────────────────────────────────────────────┘
```

### **Security Boundaries**

```
┌─────────────────────────────────────────────────┐
│  TRUSTED ZONE (Your Infrastructure)             │
│                                                 │
│  • Flask Web Server                             │
│  • Semantic Layer Service  ← GENERATES SQL      │
│  • Anonymization Service   ← DE-ANONYMIZES      │
│  • DuckDB Service          ← EXECUTES QUERY     │
│  • YAML files (configs)                         │
│  • Database files (*.duckdb)                    │
│                                                 │
│  All schema & data stays here! ✅               │
└─────────────────────────────────────────────────┘
                    ↕
            HTTPS (encrypted)
                    ↕
┌─────────────────────────────────────────────────┐
│  UNTRUSTED ZONE (External)                      │
│                                                 │
│  • External LLM (Claude/OpenAI)                 │
│                                                 │
│  WITH ANON: Receives "value_metric_001" ✅      │
│  WITHOUT:   Receives "secondary_sales_value" ❌ │
│                                                 │
│  NEVER receives:                                │
│    - SQL queries                                │
│    - Table/column names                         │
│    - Database credentials                       │
│    - Actual data                                │
└─────────────────────────────────────────────────┘
```

### **Key Security Facts**

| Question | Answer |
|----------|--------|
| Does LLM generate SQL? | ❌ NO - Semantic Layer does (local) |
| Does LLM access database? | ❌ NO - DuckDB does (local) |
| Does LLM de-anonymize? | ❌ NO - Anonymization Service does (local) |
| What does LLM do? | ✅ ONLY parses intent (returns JSON) |
| Where is SQL generated? | ✅ Your server (Semantic Layer) |
| Where is mapping stored? | ✅ Your server (in-memory only) |

### **Component File Locations**

| Component | File Path |
|-----------|-----------|
| **Anonymization Core** | `semantic_layer/anonymizer.py` |
| **LLM Integration** | `llm/intent_parser_v2.py` |
| **SQL Generation** | `semantic_layer/query_builder.py` |
| **Semantic Layer** | `semantic_layer/semantic_layer.py` |
| **Query Execution** | `query_engine/executor.py` |

---

## 📚 Key Takeaways

### **Why This Architecture?**

1. **Security First**
   - No business data sent to LLM
   - Complete client isolation
   - Audit trail for compliance

2. **Performance**
   - Rule-based parsing (5-15ms)
   - Embedded DuckDB (no network overhead)
   - AST-based SQL generation (type-safe)

3. **Maintainability**
   - YAML configs (no code changes for new metrics)
   - Single codebase for all clients
   - Clear separation of concerns

4. **Scalability**
   - Multi-schema supports 100+ clients
   - DuckDB scales to 1TB per client
   - Stateless Flask (horizontal scaling)

---

## 🔍 Where to Find Components

| Component | File Path |
|-----------|-----------|
| **Entry Point** | `frontend/app_with_auth.py` |
| **Authentication** | `security/auth.py` |
| **Semantic Layer** | `semantic_layer/semantic_layer.py` |
| **Intent Parser** | `llm/intent_parser_v2.py` |
| **Query Builder** | `semantic_layer/query_builder.py` |
| **Executor** | `query_engine/executor.py` |
| **Orchestrator** | `semantic_layer/orchestrator.py` |
| **RLS** | `security/rls.py` |
| **Configs** | `semantic_layer/configs/client_*.yaml` |
| **Databases** | `database/` |
| **Frontend** | `frontend/templates/` |

---

**📖 For setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)**

**🔗 Quick Start: [README.md](README.md)**
