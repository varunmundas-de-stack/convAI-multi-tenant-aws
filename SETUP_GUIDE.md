# Quick Start Guide - CPG Conversational AI

**Get up and running in 5 minutes!**

## 1. Prerequisites Check

```bash
# Check Python version (need 3.11+)
python --version

# Check if pip works
pip --version

# Check if Ollama is installed (optional)
ollama --version
```

## 2. Install Dependencies

```bash
cd Conv-AI-Project#1
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed duckdb-1.4.4 ollama-0.1.0 pydantic-2.5.0 ...
```

## 3. Generate Sample Database

```bash
cd database
python generate_cpg_data.py
```

**Expected output:**
```
Creating CPG database at: database/cpg_olap.duckdb
Generating date dimension...
  Generated 90 date records
Generating product dimension...
  Generated 50 product records
...
Database created successfully!
```

**Result:** `cpg_olap.duckdb` file created with 1,000 sales records

## 4. Run Demo

```bash
cd ..  # back to Conv-AI-Project#1
python demo_cpg_system.py
```

**Expected output:**
```
+----------------------------------------------------+
| CPG Conversational AI System Demo                  |
| Production-Ready AST + Semantic Layer Architecture |
+----------------------------------------------------+

Demo 1: Manual SemanticQuery Construction
OK SemanticQuery constructed
...
Generated SQL:
SELECT p.brand_name AS brand_name, SUM(net_value) AS secondary_sales_value
FROM fact_secondary_sales f
LEFT JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.brand_name
ORDER BY secondary_sales_value DESC
LIMIT 5
...
✓ All demos completed successfully!
```

## 5. Try Your First Query

Create `test_query.py`:

```python
from semantic_layer.semantic_layer import SemanticLayer
from semantic_layer.schemas import *
from semantic_layer.validator import SemanticValidator
from query_engine.executor import QueryExecutor

# Initialize
semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
validator = SemanticValidator(semantic_layer)

# Create a query
query = SemanticQuery(
    intent=IntentType.RANKING,
    metric_request=MetricRequest(primary_metric="secondary_sales_value"),
    dimensionality=Dimensionality(group_by=["brand_name"]),
    time_context=TimeContext(window="this_month"),
    sorting=Sorting(order_by="secondary_sales_value", direction="DESC", limit=5),
    original_question="Top 5 brands by sales",
    confidence=1.0
)

# Validate
validator.validate_and_raise(query)
print("✓ Query validated")

# Generate SQL
sql_query = semantic_layer.semantic_query_to_sql(query)
print("\nGenerated SQL:")
print(sql_query.sql)

# Execute
executor = QueryExecutor("database/cpg_olap.duckdb")
result = executor.execute(sql_query.sql)

print(f"\nResults ({len(result.data)} rows):")
for row in result.data:
    print(f"  {row}")
```

Run it:
```bash
python test_query.py
```

**Expected output:**
```
✓ Query validated

Generated SQL:
SELECT p.brand_name AS brand_name, SUM(net_value) AS secondary_sales_value
FROM fact_secondary_sales f
LEFT JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.brand_name
ORDER BY secondary_sales_value DESC
LIMIT 5

Results (5 rows):
  {'brand_name': 'Brand-E', 'secondary_sales_value': 3490409.66}
  {'brand_name': 'Brand-D', 'secondary_sales_value': 3160415.81}
  {'brand_name': 'Brand-A', 'secondary_sales_value': 2948573.25}
  {'brand_name': 'Brand-C', 'secondary_sales_value': 2690076.55}
  {'brand_name': 'Brand-B', 'secondary_sales_value': 2513786.75}
```

## 6. (Optional) Use LLM Intent Parser

### Option A: Ollama (Local)

```bash
# Install Ollama from https://ollama.ai/
ollama pull llama3.2:3b
```

Test with LLM:
```python
from llm.intent_parser_v2 import IntentParserV2
from semantic_layer.semantic_layer import SemanticLayer

semantic_layer = SemanticLayer("semantic_layer/config_cpg.yaml")
parser = IntentParserV2(semantic_layer, use_claude=False)

# Parse natural language
query = parser.parse("Show top 10 brands by sales this month")

print(f"Intent: {query.intent}")
print(f"Metric: {query.metric_request.primary_metric}")
print(f"Group By: {query.dimensionality.group_by}")
print(f"Limit: {query.sorting.limit if query.sorting else None}")
```

### Option B: Claude API (Production)

```bash
# Set environment variables
export USE_CLAUDE_API=true
export ANTHROPIC_API_KEY=your_api_key_here
```

Use same code as above - it will automatically use Claude API!

## 7. Explore the Database

```bash
# Interactive SQL
python
```

```python
import duckdb
conn = duckdb.connect("database/cpg_olap.duckdb")

# Check table counts
print(conn.execute("SELECT COUNT(*) FROM fact_secondary_sales").fetchone())
# Output: (1000,)

# Top brands
result = conn.execute("""
    SELECT p.brand_name, SUM(s.net_value) as sales
    FROM fact_secondary_sales s
    JOIN dim_product p ON s.product_key = p.product_key
    GROUP BY p.brand_name
    ORDER BY sales DESC
    LIMIT 5
""").fetchall()

for row in result:
    print(f"{row[0]}: ${row[1]:,.2f}")
```

## Common Issues

### Issue: "Database not found"
**Solution:**
```bash
cd database
python generate_cpg_data.py
```

### Issue: "Module not found"
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Ollama not running"
**Solution:**
- Install Ollama from https://ollama.ai/
- Or use Claude API instead (set `USE_CLAUDE_API=true`)

### Issue: "Validation error: Unknown metric"
**Solution:**
Check available metrics:
```python
from semantic_layer.semantic_layer import SemanticLayer
sl = SemanticLayer("semantic_layer/config_cpg.yaml")
print([m['name'] for m in sl.list_available_metrics()])
```

## Next Steps

1. **Read the full documentation:** `README_CPG.md`
2. **Check implementation details:** `IMPLEMENTATION_SUMMARY.md`
3. **Explore the code:** Start with `semantic_layer/schemas.py`
4. **Try more queries:** Modify `test_query.py` with different metrics/dimensions
5. **Add your own metrics:** Edit `semantic_layer/config_cpg.yaml`

## Architecture Overview

```
User Question
    ↓
LLM Parser (Ollama/Claude) → SemanticQuery
    ↓
Validator → Check rules
    ↓
Row-Level Security → Apply filters
    ↓
AST Builder → Build query tree
    ↓
SQL Compiler → Generate SQL
    ↓
Executor → Run on DuckDB
    ↓
Results + Audit Log
```

## Key Files

| File | Purpose |
|------|---------|
| `demo_cpg_system.py` | Comprehensive demo with 4 scenarios |
| `semantic_layer/schemas.py` | SemanticQuery model definitions |
| `semantic_layer/config_cpg.yaml` | Metrics & dimensions config |
| `semantic_layer/ast_builder.py` | AST node definitions |
| `semantic_layer/query_builder.py` | Converts SemanticQuery → SQL |
| `llm/intent_parser_v2.py` | LLM intent parser |
| `security/rls.py` | Row-level security |
| `security/audit.py` | Audit logging |

## Support

- **Documentation:** `README_CPG.md`
- **Examples:** `demo_cpg_system.py`
- **Issues:** Check error messages, they're designed to be helpful!

---

**You're ready to go! 🚀**

Start with the demo, then try your own queries.

---

## 8. Web Chatbot Interface (NEW!)

**Interact with your CPG data through a beautiful chat interface!**

### Quick Start

**Option 1: Windows Batch File (Easiest)**

```bash
# Double-click this file or run from command prompt:
start_chatbot.bat
```

**Option 2: Manual Start**

```bash
# From project root (Conv-AI-Project#1)
python frontend\app.py
```

### Access the Chatbot

1. Open your web browser
2. Go to: **http://localhost:5000**
3. Start asking questions!

### Example Questions

**Meta Commands:**
- Type **"give me examples"** to see a comprehensive list of 35+ categorized questions

Try these in the chatbot:
- "Show top 5 brands by sales value"
- "Weekly sales trend for last 6 weeks"
- "Top 10 SKUs by volume this month"
- "Sales by state this month"
- "Top distributors by sales value"
- "Compare sales by channel"
- "Why did sales change?" (triggers diagnostic workflow)

### Features

- **Natural Language Input:** Ask questions in plain English
- **Help System:** Type "give me examples" for 35+ categorized sample questions
- **Rich Results:** Tables, trends, and diagnostic insights
- **Query Suggestions:** Click quick suggestions to get started
- **SQL Visibility:** View the generated SQL query
- **Metadata Display:** See query intent, confidence, and execution time
- **Diagnostic Workflows:** Automatic multi-query analysis for "why" questions
- **Enhanced Intent Parsing:** Better detection of dimensions (channel, distributor, SKU, etc.)

### Chatbot Architecture

```
Web Browser (http://localhost:5000)
    ↓
Flask Backend (frontend/app.py)
    ↓
Intent Parser → Validator → RLS → Orchestrator
    ↓
Query Execution + Results Formatting
    ↓
JSON Response → Chat UI
```

### Troubleshooting

**Issue: "Address already in use"**
```bash
# Another process is using port 5000. Stop it or use a different port:
python frontend\app.py --port 5001
```

**Issue: "Template not found"**
```bash
# Make sure you're running from project root:
cd Conv-AI-Project#1
python frontend\app.py
```

**Issue: "Database connection failed"**
```bash
# Generate the database first:
cd database
python generate_cpg_data.py
cd ..
```

### Customization

Edit `frontend/app.py` to:
- Change user context (role, access level, territories)
- Add authentication
- Customize result formatting
- Add more query suggestions

Edit `frontend/templates/chat.html` to:
- Change UI colors/styling
- Add charts/visualizations
- Customize message formatting

### Production Deployment

For production use:
1. Use a production WSGI server (gunicorn, waitress)
2. Add authentication/authorization
3. Enable Claude API for better accuracy
4. Set up HTTPS
5. Configure proper logging

Example production start:
```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 frontend.app:app
```

---

**Now you have both CLI and Web interfaces! Choose what works best for you.**
