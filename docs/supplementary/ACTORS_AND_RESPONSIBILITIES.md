# Actors and Responsibilities: Who Does What?

## 🎭 The Actors

| Actor | Description | Location | Trust Level |
|-------|-------------|----------|-------------|
| **End User** | Business analyst (e.g., nestle_analyst, itc_analyst) | Browser | Authenticated |
| **Flask Web Server** | Your application server running Python | Your Infrastructure | Trusted |
| **Semantic Layer Service** | Python service that loads YAML configs | Your Infrastructure | Trusted |
| **Anonymization Service** | Python service that anonymizes/de-anonymizes | Your Infrastructure | Trusted |
| **External LLM** | Claude API / OpenAI (third-party) | External (Anthropic/OpenAI servers) | **Untrusted** |
| **Local LLM** | Ollama (self-hosted) | Your Infrastructure | Trusted |
| **DuckDB Service** | Database service account | Your Infrastructure | Trusted |
| **Authentication Service** | Flask-Login + SQLite users.db | Your Infrastructure | Trusted |

---

## 🔄 Complete Flow: Who Does What

### Step-by-Step with Actors

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: User Submits Question                                      │
└─────────────────────────────────────────────────────────────────────┘

Actor: END USER (nestle_analyst)
Action: Types question in browser
Example: "Show me sales by brand for last 4 weeks"
Location: Browser → HTTPS → Flask Server

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Authentication Check                                        │
└─────────────────────────────────────────────────────────────────────┘

Actor: AUTHENTICATION SERVICE (Flask-Login)
Action: Verifies user session and client_id
Data Access: Queries users.db (SQLite)
Result: Confirms user is "nestle_analyst" → client_id = "nestle"
Location: Your Infrastructure (Flask Server)

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Load Client-Specific YAML                                   │
└─────────────────────────────────────────────────────────────────────┘

Actor: SEMANTIC LAYER SERVICE
Action: Loads client_nestle.yaml from filesystem
Data Access: Reads semantic_layer/configs/client_nestle.yaml
Result: Loads metrics (secondary_sales_value, etc.) and dimensions
Location: Your Infrastructure (Flask Server)
Security: Only loads YAML for authenticated client

Code:
  semantic_layer = SemanticLayer('configs/client_nestle.yaml')

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4A: WITHOUT ANONYMIZATION - Build LLM Prompt                   │
└─────────────────────────────────────────────────────────────────────┘

Actor: FLASK WEB SERVER
Action: Extracts metrics/dimensions from YAML
Data Sent: Real names (secondary_sales_value, brand_name)
Destination: External LLM (Claude API/OpenAI)
Security Risk: ❌ Real schema exposed

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4B: WITH ANONYMIZATION - Anonymize Before Sending              │
└─────────────────────────────────────────────────────────────────────┘

Actor: ANONYMIZATION SERVICE
Action: Anonymizes metric/dimension names
Input: Real names (secondary_sales_value, brand_name)
Output: Anonymous names (value_metric_001, product_dimension_001)
Mapping Stored: In-memory (never leaves your infrastructure)
Location: Your Infrastructure (Flask Server)
Security: ✅ Real schema protected

Code:
  anonymizer = AnonymizationMapper(strategy='category')
  anon_metrics, mapping = anonymizer.anonymize_metrics(metrics)
  # mapping stored locally: value_metric_001 → secondary_sales_value

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: Send to External LLM                                        │
└─────────────────────────────────────────────────────────────────────┘

Actor: FLASK WEB SERVER (making API call)
Action: Sends prompt to external LLM via HTTPS
Data Sent:
  - WITHOUT ANON: "secondary_sales_value", "brand_name" ❌
  - WITH ANON: "value_metric_001", "product_dimension_001" ✅
Destination: External (Anthropic/OpenAI servers)
Security: This data leaves your infrastructure!

Code:
  response = claude_client.messages.create(
      model="claude-3-5-sonnet",
      messages=[{"role": "user", "content": prompt}]
  )

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: LLM Returns Intent                                          │
└─────────────────────────────────────────────────────────────────────┘

Actor: EXTERNAL LLM (Claude API/OpenAI)
Action: Parses question and returns structured intent
Data Returned:
  - WITHOUT ANON: {"metric": "secondary_sales_value", ...} ❌
  - WITH ANON: {"metric": "value_metric_001", ...} ✅
Location: External → Your Infrastructure
Note: LLM NEVER sees your database, NEVER generates SQL

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: De-Anonymization (WITH ANONYMIZATION ONLY)                  │
└─────────────────────────────────────────────────────────────────────┘

Actor: ANONYMIZATION SERVICE
Action: Converts anonymous names back to real names
Input: {"metric": "value_metric_001", "group_by": ["product_dimension_001"]}
Mapping Used: value_metric_001 → secondary_sales_value (from memory)
Output: {"metric": "secondary_sales_value", "group_by": ["brand_name"]}
Location: Your Infrastructure (Flask Server)
Security: ✅ Mapping never left your server

Code:
  real_query = anonymizer.deanonymize_semantic_query(llm_response)
  # Result: Real names restored locally

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: SQL Generation                                              │
└─────────────────────────────────────────────────────────────────────┘

Actor: SEMANTIC LAYER SERVICE (AST Query Builder)
Action: Generates SQL using real schema from YAML
Input: De-anonymized intent with real names
Data Access: Reads YAML for SQL expressions, table names, column names
Output: Complete SQL query
Location: Your Infrastructure (Flask Server)
Security: ✅ Real schema never sent to LLM

Code:
  from semantic_layer.query_builder import ASTQueryBuilder

  builder = ASTQueryBuilder(semantic_layer)
  query_ast = builder.build_query(semantic_query)
  sql = query_ast.to_sql(dialect="duckdb")

Generated SQL:
  SELECT
    p.brand_name,
    SUM(f.net_value) AS secondary_sales_value
  FROM client_nestle.fact_secondary_sales f
  LEFT JOIN client_nestle.dim_product p
    ON f.product_key = p.product_key
  WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'
  GROUP BY p.brand_name

Note: LLM NEVER sees this SQL!

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: Execute Query on Database                                   │
└─────────────────────────────────────────────────────────────────────┘

Actor: DUCKDB SERVICE (database engine)
Action: Executes SQL query on actual database
Database: cpg_multi_tenant.duckdb
Schema: client_nestle (isolated from other clients)
Query: SQL generated in Step 8
Location: Your Infrastructure (same machine as Flask)
Security: ✅ Client isolation enforced by schema

Code:
  import duckdb
  conn = duckdb.connect('database/cpg_multi_tenant.duckdb')
  results = conn.execute(sql).fetchall()

↓

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 10: Return Results to User                                     │
└─────────────────────────────────────────────────────────────────────┘

Actor: FLASK WEB SERVER
Action: Sends query results back to user's browser
Data Returned: Actual data (brand names, sales values)
Destination: End User's browser via HTTPS
Location: Your Infrastructure → User's Browser
```

---

## 📊 Summary Table: Who Does What

| Task | Actor | Location | Has Access To |
|------|-------|----------|---------------|
| **1. Submit Question** | End User | Browser | Question text only |
| **2. Authenticate User** | Authentication Service | Your Server | users.db, session cookies |
| **3. Load YAML Config** | Semantic Layer Service | Your Server | YAML files, client configs |
| **4. Anonymize Names** | Anonymization Service | Your Server | Real & anonymous names mapping |
| **5. Call External LLM** | Flask Web Server | Your Server → External | Anonymous names only ✅ |
| **6. Parse Intent** | External LLM (Claude/OpenAI) | External Servers | Anonymous names only ✅ |
| **7. De-anonymize Response** | Anonymization Service | Your Server | Mapping (real ↔ anonymous) |
| **8. Generate SQL** | Semantic Layer Service | Your Server | YAML (tables, columns, SQL) |
| **9. Execute Query** | DuckDB Service | Your Server | Database (client_nestle schema) |
| **10. Return Results** | Flask Web Server | Your Server → Browser | Query results |

---

## 🔐 Security Boundaries

### Trusted Zone (Your Infrastructure)

```
┌─────────────────────────────────────────────────────────┐
│              YOUR INFRASTRUCTURE (TRUSTED)              │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐           │
│  │ Flask Web Server │  │ Semantic Layer   │           │
│  │                  │  │ Service          │           │
│  └──────────────────┘  └──────────────────┘           │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐           │
│  │ Anonymization    │  │ DuckDB Service   │           │
│  │ Service          │  │                  │           │
│  └──────────────────┘  └──────────────────┘           │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐           │
│  │ YAML Files       │  │ Database Files   │           │
│  │ (client configs) │  │ (*.duckdb)       │           │
│  └──────────────────┘  └──────────────────┘           │
│                                                         │
│  All data stays here: ✅                                │
│  - Real metric names                                   │
│  - Table/column names                                  │
│  - SQL queries                                         │
│  - Anonymization mapping                               │
│  - Actual data                                         │
└─────────────────────────────────────────────────────────┘
                            ↕
                    HTTPS (encrypted)
                            ↕
┌─────────────────────────────────────────────────────────┐
│          EXTERNAL LLM (UNTRUSTED)                       │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Claude API / OpenAI                              │  │
│  │                                                  │  │
│  │ WITH ANONYMIZATION:                              │  │
│  │   Receives: "value_metric_001" ✅                │  │
│  │   Returns: {"metric": "value_metric_001"}        │  │
│  │                                                  │  │
│  │ WITHOUT ANONYMIZATION:                           │  │
│  │   Receives: "secondary_sales_value" ❌           │  │
│  │   Returns: {"metric": "secondary_sales_value"}   │  │
│  │                                                  │  │
│  │ NEVER RECEIVES:                                  │  │
│  │   - SQL queries                                  │  │
│  │   - Table/column names                           │  │
│  │   - Database credentials                         │  │
│  │   - Actual data values                           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Actors and Their Responsibilities

### 1️⃣ **END USER** (Business Analyst)
- **What they do**: Ask questions in natural language
- **What they access**: Web browser interface
- **What they see**: Query results (actual data)
- **Security**: Authenticated via Flask-Login, can only access their client's data

---

### 2️⃣ **FLASK WEB SERVER** (Your Application)
- **What it does**: Orchestrates the entire flow
- **What it accesses**:
  - Users database (authentication)
  - YAML configs (via Semantic Layer Service)
  - External LLM API (via HTTPS)
  - DuckDB (via database connector)
- **Runs as**: Application service account on your server
- **Security**: Runs in your infrastructure, enforces authentication

---

### 3️⃣ **SEMANTIC LAYER SERVICE** (Python Module)
- **What it does**:
  - Loads YAML configs
  - Generates SQL from intent
- **What it accesses**:
  - YAML files (client_nestle.yaml, etc.)
  - Nothing else - no database, no external services
- **Runs as**: Part of Flask process
- **Security**: Only loads YAML for authenticated client
- **Key Point**: **GENERATES SQL LOCALLY** - LLM never sees it!

---

### 4️⃣ **ANONYMIZATION SERVICE** (Python Module)
- **What it does**:
  - Anonymizes metric/dimension names before sending to LLM
  - De-anonymizes LLM responses
- **What it accesses**: In-memory mapping only
- **Runs as**: Part of Flask process
- **Security**: Mapping never leaves your server
- **Key Point**: **PROTECTS YOUR SCHEMA** from external LLM!

---

### 5️⃣ **EXTERNAL LLM** (Claude API / OpenAI)
- **What it does**: Parses natural language and returns structured intent
- **What it accesses**:
  - User's question (text)
  - Anonymized metric/dimension names (with anonymization)
  - Real metric/dimension names (without anonymization) ❌
- **Runs as**: External service (Anthropic/OpenAI infrastructure)
- **Security**: **UNTRUSTED** - third-party service
- **Key Point**: **NEVER generates SQL, NEVER sees database!**

---

### 6️⃣ **DUCKDB SERVICE** (Database Engine)
- **What it does**: Executes SQL queries on actual data
- **What it accesses**: Database files (cpg_multi_tenant.duckdb)
- **Runs as**: Database process on your server
- **Security**: Schema isolation (client_nestle, client_itc, etc.)
- **Key Point**: **ONLY executes SQL generated locally by Semantic Layer**

---

## 🔍 Critical Security Questions Answered

### Q1: Who creates the SQL query?
**Answer**: **SEMANTIC LAYER SERVICE** (local, trusted)
- **NOT** the External LLM
- **NOT** the user
- Generated locally using YAML config and de-anonymized intent
- LLM only provides the **intent** (what to query), not the **SQL** (how to query)

---

### Q2: Who de-anonymizes the LLM response?
**Answer**: **ANONYMIZATION SERVICE** (local, trusted)
- Runs on your Flask server
- Uses in-memory mapping: `value_metric_001` → `secondary_sales_value`
- Mapping NEVER sent to external LLM
- Happens BEFORE SQL generation

---

### Q3: Who executes the query on the actual database?
**Answer**: **DUCKDB SERVICE** (local, trusted)
- Database engine running on your infrastructure
- Executes SQL generated by Semantic Layer Service
- Enforces schema isolation (client_nestle, client_itc)
- Returns results to Flask Web Server

---

### Q4: Does the External LLM ever access the database?
**Answer**: **NO, NEVER**
- LLM is stateless, doesn't connect to databases
- LLM only sees:
  - WITH ANON: Anonymous names (`value_metric_001`) ✅
  - WITHOUT ANON: Real names (`secondary_sales_value`) ❌
- LLM returns structured intent, not SQL
- SQL generation happens **after** LLM response, **locally**

---

### Q5: Who has access to real schema (table/column names)?
**Answer**: Only **local services** (trusted)
- ✅ Semantic Layer Service - reads from YAML
- ✅ DuckDB Service - executes SQL
- ❌ External LLM - NEVER sees it (even without anonymization!)

---

### Q6: Where is the anonymization mapping stored?
**Answer**: **IN-MEMORY, YOUR SERVER ONLY**
- Created when `IntentParserV2` is initialized
- Stored in Python object (`AnonymizationMapper`)
- Exists only during the session
- NEVER persisted to disk
- NEVER sent to external LLM

---

## 🛡️ What Anonymization Protects

### WITHOUT Anonymization ❌

| Data | Exposed to External LLM? | Risk |
|------|-------------------------|------|
| Metric names (`secondary_sales_value`) | ✅ YES | ⚠️ Business model visible |
| Dimension names (`brand_name`) | ✅ YES | ⚠️ Data structure visible |
| Table names (`fact_secondary_sales`) | ❌ NO | ✅ Always protected |
| SQL queries | ❌ NO | ✅ Always protected |

---

### WITH Anonymization ✅

| Data | Exposed to External LLM? | Risk |
|------|-------------------------|------|
| Anonymous names (`value_metric_001`) | ✅ YES | ✅ Generic, no risk |
| Real metric names | ❌ NO | ✅ Protected |
| Real dimension names | ❌ NO | ✅ Protected |
| Table names | ❌ NO | ✅ Always protected |
| SQL queries | ❌ NO | ✅ Always protected |

---

## 📝 Code Examples: Who Runs What

### Flask Web Server (Orchestrator)
```python
# File: frontend/app_with_auth.py
# Runs as: Flask application process

@app.route('/query', methods=['POST'])
@login_required
def handle_query():
    # 1. Get authenticated user
    user = current_user  # Authentication Service
    client_id = user.client_id  # "nestle"

    # 2. Load client YAML (Semantic Layer Service)
    semantic_layer = SemanticLayer(
        f'configs/client_{client_id}.yaml',
        client_id=client_id
    )

    # 3. Initialize parser with anonymization (Anonymization Service)
    parser = IntentParserV2(
        semantic_layer=semantic_layer,
        anonymize_schema=True  # ← Anonymization enabled
    )

    # 4. Parse question (calls External LLM)
    question = request.json['question']
    semantic_query = parser.parse(question)
    # Inside parse():
    #   - Anonymize names
    #   - Send to External LLM
    #   - Receive response
    #   - De-anonymize locally

    # 5. Generate SQL (Semantic Layer Service - LOCAL)
    sql_query = semantic_layer.semantic_query_to_sql(semantic_query)

    # 6. Execute query (DuckDB Service)
    conn = duckdb.connect('database/cpg_multi_tenant.duckdb')
    results = conn.execute(sql_query.sql).fetchall()

    # 7. Return results to user
    return jsonify({'results': results})
```

### Anonymization Service (Protects Schema)
```python
# File: semantic_layer/anonymizer.py
# Runs as: Part of Flask process (in-memory)

class AnonymizationMapper:
    def __init__(self):
        self.metric_map = {}  # Stored in memory only

    def anonymize_metrics(self, metrics):
        anon_metrics = []
        for idx, metric in enumerate(metrics):
            # Create anonymous name
            anon_name = f"value_metric_{idx:03d}"

            # Store mapping (in memory, never sent out)
            self.metric_map[metric['name']] = anon_name

            anon_metrics.append({
                'name': anon_name,  # ← This goes to LLM
                'description': 'Monetary value measurement'
            })
        return anon_metrics

    def deanonymize_semantic_query(self, llm_response):
        # Map anonymous names back to real names
        real_metric = self.metric_map[llm_response['metric']]
        return {'metric': real_metric}
```

### Semantic Layer Service (Generates SQL)
```python
# File: semantic_layer/query_builder.py
# Runs as: Part of Flask process (local)

class ASTQueryBuilder:
    def build_query(self, semantic_query):
        # Get real metric from YAML
        metric = self.semantic_layer.get_metric(
            semantic_query.metric_request.primary_metric
        )
        # metric = {
        #   'name': 'secondary_sales_value',
        #   'sql': 'SUM(net_value)',  ← From YAML
        #   'table': 'fact_secondary_sales'  ← From YAML
        # }

        # Build SQL using real schema (LLM never sees this!)
        sql = f"""
        SELECT
          p.brand_name,
          {metric['sql']} AS {metric['name']}
        FROM {metric['table']} f
        JOIN dim_product p ON ...
        """
        return sql
```

---

## ✅ Final Summary

| Actor | Trusted? | Location | Responsibility |
|-------|----------|----------|----------------|
| **End User** | Yes (authenticated) | Browser | Ask questions |
| **Flask Web Server** | Yes | Your Infrastructure | Orchestrate flow |
| **Semantic Layer Service** | Yes | Your Infrastructure | **Generate SQL** |
| **Anonymization Service** | Yes | Your Infrastructure | **Anonymize/De-anonymize** |
| **External LLM** | **NO** | External | Parse intent only |
| **DuckDB Service** | Yes | Your Infrastructure | **Execute SQL** |

**Key Points**:
1. ✅ **SQL generated by**: Semantic Layer Service (local, trusted)
2. ✅ **De-anonymization done by**: Anonymization Service (local, trusted)
3. ✅ **Query executed by**: DuckDB Service (local, trusted)
4. ❌ **External LLM**: NEVER sees SQL, NEVER accesses database, NEVER de-anonymizes
5. 🔒 **With anonymization**: External LLM only sees generic names

**Enable with**: `export ANONYMIZE_SCHEMA=true`
