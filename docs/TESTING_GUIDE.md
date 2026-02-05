# Cross-Verification & Testing Guide
## DuckDB vs ChromaDB Results Comparison

**Purpose**: Validate that ChromaDB integration works correctly and understand the differences between query modes.

---

## 🎯 Testing Strategy

This guide will help you:
1. ✅ Verify data sync between DuckDB and ChromaDB
2. ✅ Test the same query across all 3 modes
3. ✅ Compare and validate results
4. ✅ Understand when to use each mode
5. ✅ Troubleshoot issues

---

## Step 1: Verify Data Sync

### Check DuckDB Data

```bash
# Run DuckDB CLI
python -c "import duckdb; conn = duckdb.connect('database/cpg_olap.duckdb'); print('Tables:', [r[0] for r in conn.execute('SHOW TABLES').fetchall()]); print('\\nRow Counts:'); [print(f'{t}: {conn.execute(f\"SELECT COUNT(*) FROM {t}\").fetchone()[0]} rows') for t in ['dim_date', 'dim_product', 'dim_geography', 'dim_customer', 'fact_secondary_sales', 'dim_channel']]; conn.close()"
```

**Expected Output:**
```
Tables: ['dim_date', 'dim_product', 'dim_geography', 'dim_customer', 'fact_secondary_sales', 'dim_channel']

Row Counts:
dim_date: 90 rows
dim_product: 50 rows
dim_geography: 200 rows
dim_customer: 120 rows
fact_secondary_sales: 1000 rows
dim_channel: 5 rows
```

### Check ChromaDB Data

```bash
# Run ChromaDB verification
python -c "from vector_store.chromadb_client import get_chroma_client; client = get_chroma_client(); collections = client.list_collections(); print('Collections:', collections); [print(f'{col}: {client.get_collection_stats(col)[\"count\"]} documents') for col in collections if col.startswith('duckdb_')]"
```

**Expected Output:**
```
Collections: ['test_queries', 'duckdb_dim_product', 'duckdb_dim_geography', 'duckdb_dim_date', 'duckdb_dim_customer', 'duckdb_fact_secondary_sales', 'duckdb_dim_channel']

duckdb_dim_product: 50 documents
duckdb_dim_geography: 200 documents
duckdb_dim_date: 90 documents
duckdb_dim_customer: 120 documents
duckdb_fact_secondary_sales: 1000 documents
duckdb_dim_channel: 5 documents
```

**✅ PASS Criteria**: Row counts match between DuckDB and ChromaDB collections.

---

## Step 2: Side-by-Side Query Testing

### Test Case 1: Simple Ranking Query

**Question**: "Show top 5 brands by sales"

#### Test in Web UI:

1. **Start the chatbot**:
   ```bash
   python frontend/app.py
   # Open http://localhost:5000
   ```

2. **Test Standard Mode** (📊):
   - Select "Standard" mode
   - Type: "Show top 5 brands by sales"
   - Click Send

3. **Test AI-Enhanced Mode** (🤖):
   - Select "AI-Enhanced" mode
   - Type: "Show top 5 brands by sales"
   - Click Send

4. **Test ChromaDB Direct Mode** (🔍):
   - Select "ChromaDB Direct" mode
   - Type: "Show top 5 brands by sales"
   - Click Send

#### Expected Results:

**Standard Mode:**
```
SQL Query Generated: SELECT brand_name, SUM(net_value) as sales_value
                     FROM fact_secondary_sales
                     LEFT JOIN dim_product ...
                     GROUP BY brand_name
                     ORDER BY sales_value DESC
                     LIMIT 5

Results Table:
| brand_name | sales_value |
|------------|-------------|
| Brand-A    | 45,234.56   |
| Brand-B    | 38,912.34   |
| Brand-C    | 32,567.89   |
| Brand-D    | 28,345.67   |
| Brand-E    | 25,678.90   |
```

**AI-Enhanced Mode:**
```
Mode: AI-Enhanced

📚 Similar Queries Found (3):
1. "Show top 5 brands by sales value" - 98% match (RANKING intent)
2. "Top 10 SKUs by volume" - 75% match (RANKING intent)
3. "Best performing brands" - 72% match (RANKING intent)

[Same SQL and results table as Standard Mode]
```

**ChromaDB Direct Mode:**
```
Mode: ChromaDB Direct

Semantic Search Results
Searched 6 collections

Results Table:
| collection                  | document                                      | similarity_score |
|-----------------------------|-----------------------------------------------|------------------|
| duckdb_dim_product         | [dim_product] Brand Name: Brand-A, ...       | 0.6234          |
| duckdb_fact_secondary_sales| [fact_secondary_sales] Brand Name: Brand-A...| 0.5891          |
| duckdb_dim_product         | [dim_product] Brand Name: Brand-B, ...       | 0.5234          |
...
```

**✅ PASS Criteria**:
- Standard and AI-Enhanced return **identical SQL results**
- AI-Enhanced shows similar queries
- ChromaDB Direct returns **different format** (semantic matches, not aggregated)

---

### Test Case 2: Ambiguous Question

**Question**: "Which products are doing well?"

**Purpose**: Test how AI-Enhanced mode handles ambiguity vs Standard mode.

#### Expected Behavior:

**Standard Mode:**
- May struggle with "doing well" (not a specific metric)
- Might interpret as sales value by default
- Returns structured SQL results

**AI-Enhanced Mode:**
- Finds similar queries like "top brands by sales"
- Uses examples to infer "doing well" = sales or volume
- Better confidence score
- Returns structured SQL results

**ChromaDB Direct Mode:**
- Semantic search for product-related documents
- Finds all documents mentioning products
- Sorted by similarity

**✅ PASS Criteria**:
- AI-Enhanced should have higher confidence than Standard
- ChromaDB Direct should return product-related documents

---

### Test Case 3: Typo Tolerance

**Question**: "Show top brends by revenu"

(Intentional typos: "brends" instead of "brands", "revenu" instead of "revenue")

#### Expected Behavior:

**Standard Mode:**
- May fail with low confidence
- Keyword matching won't catch typos
- Might return error

**AI-Enhanced Mode:**
- Similar query search is typo-tolerant
- Finds "Show top brands by revenue"
- Better intent parsing
- Returns results

**ChromaDB Direct Mode:**
- Semantic embeddings are typo-tolerant
- Finds brand and revenue related documents
- Returns results sorted by similarity

**✅ PASS Criteria**:
- AI-Enhanced and ChromaDB Direct handle typos better than Standard

---

## Step 3: Performance Comparison

### Measure Query Latency

Create a test script:

```python
# test_performance.py
import time
import requests

def test_query_mode(question, mode):
    """Test a query in a specific mode and measure time."""
    start = time.time()
    response = requests.post('http://localhost:5000/api/query', json={
        'question': question,
        'mode': mode
    })
    elapsed = (time.time() - start) * 1000  # Convert to ms

    data = response.json()
    backend_time = data.get('metadata', {}).get('exec_time_ms', 0)

    return {
        'mode': mode,
        'total_time_ms': round(elapsed, 2),
        'backend_time_ms': backend_time,
        'success': data.get('success', False)
    }

# Test question
question = "Show top 5 brands by sales"

print("Performance Comparison:")
print("=" * 60)

for mode in ['standard', 'ai-enhanced', 'chromadb']:
    result = test_query_mode(question, mode)
    print(f"\n{result['mode'].upper()}:")
    print(f"  Total Time: {result['total_time_ms']}ms")
    print(f"  Backend Time: {result['backend_time_ms']}ms")
    print(f"  Success: {result['success']}")
```

**Run the test:**
```bash
python test_performance.py
```

**Expected Results:**
```
Performance Comparison:
============================================================

STANDARD:
  Total Time: 156.32ms
  Backend Time: 145.67ms
  Success: True

AI-ENHANCED:
  Total Time: 198.45ms
  Backend Time: 187.23ms
  Success: True

CHROMADB:
  Total Time: 78.91ms
  Backend Time: 68.34ms
  Success: True
```

**✅ PASS Criteria**:
- ChromaDB Direct: 50-100ms (fastest - no SQL generation)
- Standard: 100-200ms (SQL generation + DuckDB query)
- AI-Enhanced: 150-250ms (ChromaDB search + SQL generation + DuckDB query)

---

## Step 4: Result Accuracy Verification

### Verify SQL Results Match

**Script**: `verify_results.py`

```python
import duckdb
from vector_store.chromadb_client import get_chroma_client
from query_engine.executor import QueryExecutor

# Test query
sql = """
SELECT
    p.brand_name,
    SUM(f.net_value) as sales_value
FROM fact_secondary_sales f
LEFT JOIN dim_product p ON f.product_key = p.product_key
WHERE f.return_flag = false
GROUP BY p.brand_name
ORDER BY sales_value DESC
LIMIT 5
"""

# Get DuckDB results
executor = QueryExecutor("database/cpg_olap.duckdb")
duckdb_results = executor.execute_query(sql)

print("DuckDB Results:")
print("=" * 60)
for row in duckdb_results['results']:
    print(f"{row['brand_name']}: {row['sales_value']:,.2f}")

# Check if same brands exist in ChromaDB
client = get_chroma_client()
results = client.query_similar(
    collection_name="duckdb_dim_product",
    query_text="brand",
    n_results=10
)

print("\n\nChromaDB Brand Documents:")
print("=" * 60)
brand_names = set()
for metadata in results['metadatas'][0]:
    brand_name = metadata.get('brand_name', '')
    if brand_name:
        brand_names.add(brand_name)

for brand in sorted(brand_names):
    print(f"- {brand}")

# Verify overlap
duckdb_brands = set(row['brand_name'] for row in duckdb_results['results'])
overlap = duckdb_brands.intersection(brand_names)

print("\n\nVerification:")
print("=" * 60)
print(f"DuckDB brands: {duckdb_brands}")
print(f"ChromaDB brands found: {len(brand_names)}")
print(f"Overlap: {overlap}")
print(f"✅ PASS: All brands exist in ChromaDB" if overlap == duckdb_brands else "❌ FAIL: Missing brands")
```

**Run verification:**
```bash
python verify_results.py
```

**✅ PASS Criteria**: All brands from DuckDB query exist in ChromaDB collections.

---

## Step 5: Common Test Scenarios

### Scenario 1: Data Integrity Check

**Verify row counts match:**

```python
# check_sync.py
import duckdb
from vector_store.chromadb_client import get_chroma_client

conn = duckdb.connect('database/cpg_olap.duckdb')
client = get_chroma_client()

tables = ['dim_date', 'dim_product', 'dim_geography', 'dim_customer',
          'fact_secondary_sales', 'dim_channel']

print("Data Integrity Check:")
print("=" * 70)
print(f"{'Table':<25} {'DuckDB Rows':<15} {'ChromaDB Docs':<15} {'Match':<10}")
print("-" * 70)

all_match = True
for table in tables:
    # DuckDB count
    duckdb_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # ChromaDB count
    collection_name = f"duckdb_{table}"
    chroma_stats = client.get_collection_stats(collection_name)
    chroma_count = chroma_stats['count']

    match = "✅" if duckdb_count == chroma_count else "❌"
    if duckdb_count != chroma_count:
        all_match = False

    print(f"{table:<25} {duckdb_count:<15} {chroma_count:<15} {match:<10}")

print("-" * 70)
print(f"Overall: {'✅ ALL MATCH' if all_match else '❌ MISMATCH DETECTED'}")

conn.close()
```

**Expected Output:**
```
Data Integrity Check:
======================================================================
Table                     DuckDB Rows     ChromaDB Docs   Match
----------------------------------------------------------------------
dim_date                  90              90              ✅
dim_product               50              50              ✅
dim_geography             200             200             ✅
dim_customer              120             120             ✅
fact_secondary_sales      1000            1000            ✅
dim_channel               5               5               ✅
----------------------------------------------------------------------
Overall: ✅ ALL MATCH
```

---

### Scenario 2: Semantic Search Quality

**Test semantic understanding:**

```python
# test_semantic.py
from vector_store.chromadb_client import get_chroma_client

client = get_chroma_client()

test_queries = [
    ("Maggi products", "duckdb_dim_product"),
    ("Tamil Nadu", "duckdb_dim_geography"),
    ("sales in January", "duckdb_dim_date"),
    ("distributor customers", "duckdb_dim_customer"),
]

print("Semantic Search Quality Test:")
print("=" * 70)

for query, collection in test_queries:
    print(f"\nQuery: '{query}' in {collection}")
    print("-" * 70)

    results = client.query_similar(
        collection_name=collection,
        query_text=query,
        n_results=3
    )

    if results['documents'][0]:
        for i, (doc, distance) in enumerate(zip(
            results['documents'][0][:3],
            results['distances'][0][:3]
        ), 1):
            similarity = 1 / (1 + distance)
            print(f"{i}. Similarity: {similarity:.4f}")
            print(f"   Document: {doc[:80]}...")
            print()
    else:
        print("   ❌ No results found")
```

**✅ PASS Criteria**:
- Each query should return relevant documents
- Similarity scores should be > 0.3 (higher is better)
- Top result should be most relevant

---

## Step 6: Troubleshooting Guide

### Issue 1: No Results in ChromaDB Direct Mode

**Symptoms:**
```
ChromaDB Direct Mode returns: "No results found"
```

**Diagnosis:**
```bash
# Check if collections exist
python -c "from vector_store.chromadb_client import get_chroma_client; print(get_chroma_client().list_collections())"
```

**Fix:**
```bash
# Re-sync data
python vector_store/sync_duckdb_to_chroma.py
```

---

### Issue 2: Different Results Between Standard and AI-Enhanced

**Symptoms:**
```
Standard Mode returns different SQL results than AI-Enhanced Mode
```

**Diagnosis:**
This is **EXPECTED** if the questions are interpreted differently. AI-Enhanced mode might:
- Interpret ambiguous terms differently
- Apply different filters
- Choose different metrics

**How to Verify:**
1. Check the SQL queries generated (click "Show SQL Query")
2. Compare the WHERE clauses and GROUP BY columns
3. If intents differ, the results will differ

**✅ PASS**: Results differ because interpretations differ (this is the feature!)
**❌ FAIL**: Results differ with identical SQL (this is a bug)

---

### Issue 3: AI-Enhanced Mode Shows No Similar Queries

**Symptoms:**
```
AI-Enhanced Mode doesn't show "Similar Queries Found" section
```

**Diagnosis:**
```bash
# Check if test_queries collection has data
python -c "from vector_store.chromadb_client import get_chroma_client; stats = get_chroma_client().get_collection_stats('test_queries'); print(f'Query patterns: {stats[\"count\"]}')"
```

**Fix:**
```python
# Add query patterns manually
from vector_store.chromadb_client import get_chroma_client

client = get_chroma_client()
client.add_documents(
    collection_name="test_queries",
    documents=[
        "Show top 5 brands by sales",
        "Top 10 SKUs by volume",
        "Weekly sales trend",
        "Compare sales by channel",
        "Why did sales drop?"
    ],
    metadatas=[
        {"intent": "RANKING", "metric": "sales"},
        {"intent": "RANKING", "metric": "volume"},
        {"intent": "TREND", "metric": "sales"},
        {"intent": "COMPARISON", "metric": "sales"},
        {"intent": "DIAGNOSTIC", "metric": "sales"}
    ]
)
```

---

### Issue 4: Slow Performance

**Symptoms:**
```
Queries take > 5 seconds to execute
```

**Diagnosis:**
1. Check DuckDB indexes:
   ```python
   import duckdb
   conn = duckdb.connect('database/cpg_olap.duckdb')
   print(conn.execute("PRAGMA show_tables_expanded").fetchall())
   ```

2. Check ChromaDB collection size:
   ```python
   from vector_store.chromadb_client import get_chroma_client
   client = get_chroma_client()
   for col in client.list_collections():
       stats = client.get_collection_stats(col)
       print(f"{col}: {stats['count']} docs")
   ```

**Expected Performance:**
- DuckDB queries: < 200ms
- ChromaDB search: < 50ms
- Total (AI-Enhanced): < 300ms

**Fix if slow:**
- Reduce `n_results` parameter in ChromaDB queries
- Add indexes to DuckDB fact tables
- Clear ChromaDB cache: delete `database/chroma/` and re-sync

---

## Step 7: Acceptance Criteria

### ✅ All Tests Pass If:

1. **Data Sync**
   - [x] All row counts match between DuckDB and ChromaDB
   - [x] All 6 collections created successfully
   - [x] No missing or duplicate documents

2. **Query Functionality**
   - [x] Standard Mode returns SQL results
   - [x] AI-Enhanced Mode returns SQL results + similar queries
   - [x] ChromaDB Direct returns semantic search results
   - [x] All modes handle the same question

3. **Result Quality**
   - [x] Standard and AI-Enhanced return identical SQL for identical intents
   - [x] ChromaDB Direct returns relevant documents
   - [x] Similarity scores are meaningful (> 0.3 for good matches)

4. **Performance**
   - [x] Standard Mode: < 200ms
   - [x] AI-Enhanced Mode: < 300ms
   - [x] ChromaDB Direct: < 100ms

5. **Error Handling**
   - [x] Out-of-scope questions are rejected
   - [x] Typos are handled gracefully in AI-Enhanced/ChromaDB modes
   - [x] Empty results show appropriate messages

---

## Step 8: Sample Test Report

```markdown
# Test Execution Report

**Date**: 2026-02-06
**Tester**: [Your Name]
**Environment**: Local Development

## Test Results Summary

| Test Case | Standard | AI-Enhanced | ChromaDB Direct | Status |
|-----------|----------|-------------|-----------------|--------|
| Simple Ranking | ✅ Pass | ✅ Pass | ✅ Pass | PASS |
| Ambiguous Question | ⚠️ Low Conf | ✅ Pass | ✅ Pass | PASS |
| Typo Tolerance | ❌ Fail | ✅ Pass | ✅ Pass | PASS |
| Performance | ✅ 145ms | ✅ 187ms | ✅ 68ms | PASS |
| Data Sync | ✅ All Match | - | - | PASS |

## Overall: ✅ PASS

**Recommendation**: Deploy to production after adding more query patterns to test_queries collection.
```

---

## Quick Reference Commands

```bash
# Verify sync
python -c "from vector_store.chromadb_client import get_chroma_client; c = get_chroma_client(); [print(f'{col}: {c.get_collection_stats(col)[\"count\"]}') for col in c.list_collections() if col.startswith('duckdb_')]"

# Start chatbot
python frontend/app.py

# Re-sync if needed
python vector_store/sync_duckdb_to_chroma.py

# Check DuckDB directly
python -c "import duckdb; conn = duckdb.connect('database/cpg_olap.duckdb'); print(conn.execute('SELECT COUNT(*) FROM fact_secondary_sales').fetchone()[0])"

# Test ChromaDB query
python vector_store/chromadb_query_executor.py
```

---

## Next Steps After Testing

1. ✅ Document any bugs found
2. ✅ Add more query patterns to improve AI-Enhanced mode
3. ✅ Fine-tune similarity thresholds if needed
4. ✅ Deploy to production with confidence!

---

**Happy Testing! 🧪**

*For issues, check the Troubleshooting section or review logs in `logs/audit.jsonl`*
