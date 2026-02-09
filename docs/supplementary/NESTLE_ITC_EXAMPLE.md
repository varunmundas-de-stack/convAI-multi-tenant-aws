# Real-World Examples: Nestlé vs ITC with Anonymization

## 📋 Scenario

Two users from different companies ask similar questions:
- **Nestlé analyst**: "Show me sales by brand for last 4 weeks"
- **ITC analyst**: "Show me sales by brand for last 4 weeks"

Same question, but different YAMLs, different schemas, different data!

---

## 🏢 Example 1: Nestlé India

### Step 1: YAML Configuration (Always Local)

**File**: `semantic_layer/configs/client_nestle.yaml`

```yaml
client:
  id: "nestle"
  name: "Nestlé India"
  schema: "client_nestle"

database:
  path: "database/cpg_multi_tenant.duckdb"
  schema: "client_nestle"

metrics:
  secondary_sales_value:
    description: "Net invoiced value to retailers"
    sql: "SUM(net_value)"
    table: "fact_secondary_sales"
    aggregation: "sum"
    format: "currency"

  secondary_sales_volume:
    description: "Total units sold to retailers"
    sql: "SUM(invoice_quantity)"
    table: "fact_secondary_sales"
    aggregation: "sum"

dimensions:
  product:
    table: "dim_product"
    levels:
      - name: "brand_name"
        column: "brand_name"
        description: "Brand name"
      - name: "category_name"
        column: "category_name"
        description: "Product category"
```

**Note**: This YAML contains Nestlé-specific terminology and stays on your server.

---

### Step 2: User Question

```
User: nestle_analyst
Question: "Show me sales by brand for last 4 weeks"
```

---

### Step 3A: WITHOUT Anonymization ❌

#### What Gets Sent to External LLM (Claude API):

```json
System Prompt:
{
  "domain": "CPG/Sales analytics",
  "metrics": [
    {
      "name": "secondary_sales_value",
      "description": "Net invoiced value to retailers"
    },
    {
      "name": "secondary_sales_volume",
      "description": "Total units sold to retailers"
    }
  ],
  "dimensions": [
    {
      "name": "brand_name",
      "description": "Brand name"
    },
    {
      "name": "category_name",
      "description": "Product category"
    }
  ]
}

User Question: "Show me sales by brand for last 4 weeks"
```

#### LLM Response:
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "secondary_sales_value"
  },
  "dimensionality": {
    "group_by": ["brand_name"]
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### SQL Generated (Local):
```sql
SELECT
  p.brand_name,
  SUM(f.net_value) AS secondary_sales_value
FROM client_nestle.fact_secondary_sales f
LEFT JOIN client_nestle.dim_product p ON f.product_key = p.product_key
LEFT JOIN client_nestle.dim_date d ON f.date_key = d.date_key
WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'
GROUP BY p.brand_name
```

**⚠️ RISK**: Claude API now knows:
- You track "secondary_sales_value" (reveals CPG domain)
- You have "brand_name" and "category_name" dimensions
- Your business focuses on retail sales tracking

---

### Step 3B: WITH Anonymization ✅

#### What Gets Sent to External LLM (Claude API):

```json
System Prompt:
{
  "domain": "Business analytics",  ← Generic!
  "metrics": [
    {
      "name": "value_metric_001",  ← Anonymized!
      "description": "Monetary value measurement"  ← Generic!
    },
    {
      "name": "volume_metric_001",  ← Anonymized!
      "description": "Quantity measurement"  ← Generic!
    }
  ],
  "dimensions": [
    {
      "name": "product_dimension_001",  ← Anonymized!
      "description": "Product hierarchy attribute"  ← Generic!
    },
    {
      "name": "product_dimension_002",  ← Anonymized!
      "description": "Product hierarchy attribute"  ← Generic!
    }
  ]
}

User Question: "Show me sales by brand for last 4 weeks"
```

#### Anonymization Mapping (Stored Locally, Never Sent):
```
Nestlé Mapping (in memory only):
  value_metric_001      → secondary_sales_value
  volume_metric_001     → secondary_sales_volume
  product_dimension_001 → brand_name
  product_dimension_002 → category_name
```

#### LLM Response (with anonymous names):
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "value_metric_001"  ← Anonymous!
  },
  "dimensionality": {
    "group_by": ["product_dimension_001"]  ← Anonymous!
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### De-Anonymization (Local):
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "secondary_sales_value"  ← Real name restored!
  },
  "dimensionality": {
    "group_by": ["brand_name"]  ← Real name restored!
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### SQL Generated (Local, Same as Before):
```sql
SELECT
  p.brand_name,
  SUM(f.net_value) AS secondary_sales_value
FROM client_nestle.fact_secondary_sales f
LEFT JOIN client_nestle.dim_product p ON f.product_key = p.product_key
LEFT JOIN client_nestle.dim_date d ON f.date_key = d.date_key
WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'
GROUP BY p.brand_name
```

**✅ SAFE**: Claude API only knows:
- Generic "value_metric_001" (could be anything)
- Generic "product_dimension_001" (could be anything)
- No business domain info leaked!

---

## 🏢 Example 2: ITC Limited

### Step 1: YAML Configuration (Always Local)

**File**: `semantic_layer/configs/client_itc.yaml`

```yaml
client:
  id: "itc"
  name: "ITC Limited"
  schema: "client_itc"

database:
  path: "database/cpg_multi_tenant.duckdb"
  schema: "client_itc"

metrics:
  net_trade_sales:
    description: "Net trade sales value"
    sql: "SUM(trade_value)"
    table: "fact_trade_sales"
    aggregation: "sum"
    format: "currency"

  volume_sales:
    description: "Volume of units sold"
    sql: "SUM(volume_units)"
    table: "fact_trade_sales"
    aggregation: "sum"

dimensions:
  product:
    table: "dim_product_hierarchy"
    levels:
      - name: "brand"
        column: "brand"
        description: "ITC brand"
      - name: "sub_brand"
        column: "sub_brand"
        description: "Sub-brand"
```

**Note**: ITC has different metric names, table names, column names than Nestlé!

---

### Step 2: User Question

```
User: itc_analyst
Question: "Show me sales by brand for last 4 weeks"
```

---

### Step 3A: WITHOUT Anonymization ❌

#### What Gets Sent to External LLM (Claude API):

```json
System Prompt:
{
  "domain": "CPG/Sales analytics",
  "metrics": [
    {
      "name": "net_trade_sales",  ← ITC-specific!
      "description": "Net trade sales value"
    },
    {
      "name": "volume_sales",  ← ITC-specific!
      "description": "Volume of units sold"
    }
  ],
  "dimensions": [
    {
      "name": "brand",  ← Different from Nestlé!
      "description": "ITC brand"
    },
    {
      "name": "sub_brand",
      "description": "Sub-brand"
    }
  ]
}

User Question: "Show me sales by brand for last 4 weeks"
```

#### LLM Response:
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "net_trade_sales"  ← ITC's metric name
  },
  "dimensionality": {
    "group_by": ["brand"]  ← ITC's dimension name
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### SQL Generated (Local):
```sql
SELECT
  p.brand,
  SUM(f.trade_value) AS net_trade_sales
FROM client_itc.fact_trade_sales f
LEFT JOIN client_itc.dim_product_hierarchy p ON f.product_key = p.product_key
LEFT JOIN client_itc.dim_date d ON f.date_key = d.date_key
WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'
GROUP BY p.brand
```

**⚠️ RISK**: Claude API now knows:
- ITC tracks "net_trade_sales" (different from Nestlé)
- ITC uses "trade_value" terminology
- Can infer ITC's data model is different from others

---

### Step 3B: WITH Anonymization ✅

#### What Gets Sent to External LLM (Claude API):

```json
System Prompt:
{
  "domain": "Business analytics",  ← Generic!
  "metrics": [
    {
      "name": "value_metric_001",  ← Same anonymous name as Nestlé!
      "description": "Monetary value measurement"
    },
    {
      "name": "volume_metric_001",  ← Same anonymous name as Nestlé!
      "description": "Quantity measurement"
    }
  ],
  "dimensions": [
    {
      "name": "product_dimension_001",  ← Same anonymous name as Nestlé!
      "description": "Product hierarchy attribute"
    },
    {
      "name": "product_dimension_002",
      "description": "Product hierarchy attribute"
    }
  ]
}

User Question: "Show me sales by brand for last 4 weeks"
```

#### Anonymization Mapping (Stored Locally, Different from Nestlé):
```
ITC Mapping (in memory only):
  value_metric_001      → net_trade_sales  (NOT secondary_sales_value!)
  volume_metric_001     → volume_sales     (NOT secondary_sales_volume!)
  product_dimension_001 → brand            (NOT brand_name!)
  product_dimension_002 → sub_brand        (NOT category_name!)
```

**🔑 KEY INSIGHT**: Same anonymous names sent to LLM, but map to different real names!

#### LLM Response (Same Anonymous Structure):
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "value_metric_001"  ← Same anonymous name
  },
  "dimensionality": {
    "group_by": ["product_dimension_001"]  ← Same anonymous name
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### De-Anonymization (Local, Maps to ITC's Real Names):
```json
{
  "intent": "trend",
  "metric_request": {
    "primary_metric": "net_trade_sales"  ← ITC's real metric!
  },
  "dimensionality": {
    "group_by": ["brand"]  ← ITC's real dimension!
  },
  "time_context": {
    "window": "last_4_weeks"
  }
}
```

#### SQL Generated (Local, ITC-Specific):
```sql
SELECT
  p.brand,
  SUM(f.trade_value) AS net_trade_sales
FROM client_itc.fact_trade_sales f
LEFT JOIN client_itc.dim_product_hierarchy p ON f.product_key = p.product_key
LEFT JOIN client_itc.dim_date d ON f.date_key = d.date_key
WHERE d.date >= CURRENT_DATE - INTERVAL '4 weeks'
GROUP BY p.brand
```

**✅ SAFE**: Claude API:
- Sees exact same anonymous names for both clients
- Cannot tell Nestlé from ITC
- Cannot infer different schemas or business models!

---

## 🔄 Side-by-Side Comparison

### What External LLM Sees

| Component | Nestlé (Without Anon) ❌ | ITC (Without Anon) ❌ | Both (With Anon) ✅ |
|-----------|-------------------------|---------------------|---------------------|
| **Metric Name** | `secondary_sales_value` | `net_trade_sales` | `value_metric_001` |
| **Metric Desc** | "Net invoiced value to retailers" | "Net trade sales value" | "Monetary value measurement" |
| **Dimension Name** | `brand_name` | `brand` | `product_dimension_001` |
| **Table Names** | Never sent ✅ | Never sent ✅ | Never sent ✅ |
| **SQL** | Never sent ✅ | Never sent ✅ | Never sent ✅ |
| **Schema Info** | Reveals CPG retail focus ❌ | Reveals CPG trade focus ❌ | Reveals nothing ✅ |

### Local Mapping (Never Sent to LLM)

| Anonymous Name | Nestlé Real Name | ITC Real Name |
|----------------|------------------|---------------|
| `value_metric_001` | `secondary_sales_value` | `net_trade_sales` |
| `volume_metric_001` | `secondary_sales_volume` | `volume_sales` |
| `product_dimension_001` | `brand_name` | `brand` |
| `product_dimension_002` | `category_name` | `sub_brand` |

### SQL Generated (Local Only)

| Client | Table Used | Column Used | Schema |
|--------|-----------|-------------|--------|
| **Nestlé** | `fact_secondary_sales` | `net_value` | `client_nestle` |
| **ITC** | `fact_trade_sales` | `trade_value` | `client_itc` |

---

## 🎯 The Key Benefits

### 1. **Client Isolation Enhanced**
- External LLM cannot tell different clients apart
- Same anonymous names for both clients
- No cross-client information leakage

### 2. **Schema Privacy**
- Real metric names hidden (`secondary_sales_value` vs `net_trade_sales`)
- Real dimension names hidden (`brand_name` vs `brand`)
- Business terminology protected

### 3. **Multi-Tenancy Security**
- Each client's YAML stays separate
- Mapping happens per-session, per-client
- No mapping stored permanently (in-memory only)

### 4. **Zero Functionality Impact**
- SQL generation unchanged
- Query accuracy unchanged
- Client data isolation unchanged
- Only difference: LLM sees anonymous names

---

## 📊 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUESTIONS                            │
│                                                              │
│  Nestlé Analyst: "Show sales by brand"                      │
│  ITC Analyst:    "Show sales by brand"                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴──────────────────┐
        ↓                                      ↓
┌──────────────────┐                  ┌──────────────────┐
│ Nestlé YAML      │                  │ ITC YAML         │
│ (Local)          │                  │ (Local)          │
├──────────────────┤                  ├──────────────────┤
│ secondary_sales  │                  │ net_trade_sales  │
│ brand_name       │                  │ brand            │
│ SUM(net_value)   │                  │ SUM(trade_value) │
└──────────────────┘                  └──────────────────┘
        ↓                                      ↓
┌──────────────────┐                  ┌──────────────────┐
│ Anonymize        │                  │ Anonymize        │
│ (Local)          │                  │ (Local)          │
├──────────────────┤                  ├──────────────────┤
│ Map:             │                  │ Map:             │
│ value_metric_001 │                  │ value_metric_001 │
│ → secondary..    │                  │ → net_trade..    │
└──────────────────┘                  └──────────────────┘
        ↓                                      ↓
        └───────────────────┬──────────────────┘
                            ↓
                ┌──────────────────────┐
                │  EXTERNAL LLM SEES:  │
                │  (Same for both!)    │
                ├──────────────────────┤
                │  value_metric_001    │
                │  product_dimension_  │
                │        001           │
                │                      │
                │  ✅ No client info!  │
                └──────────────────────┘
                            ↓
                ┌──────────────────────┐
                │  LLM Returns:        │
                ├──────────────────────┤
                │  "value_metric_001"  │
                │  "product_dim_001"   │
                └──────────────────────┘
                            ↓
        ┌───────────────────┴──────────────────┐
        ↓                                      ↓
┌──────────────────┐                  ┌──────────────────┐
│ De-anonymize     │                  │ De-anonymize     │
│ (Local)          │                  │ (Local)          │
├──────────────────┤                  ├──────────────────┤
│ value_metric_001 │                  │ value_metric_001 │
│ → secondary..    │                  │ → net_trade..    │
└──────────────────┘                  └──────────────────┘
        ↓                                      ↓
┌──────────────────┐                  ┌──────────────────┐
│ SQL (Nestlé)     │                  │ SQL (ITC)        │
├──────────────────┤                  ├──────────────────┤
│ SELECT           │                  │ SELECT           │
│   p.brand_name,  │                  │   p.brand,       │
│   SUM(net_value) │                  │   SUM(trade_val) │
│ FROM             │                  │ FROM             │
│   client_nestle  │                  │   client_itc     │
│   .fact_sec..    │                  │   .fact_trade..  │
└──────────────────┘                  └──────────────────┘
```

---

## ✅ Summary

### What Changed:
- **Nothing** in YAML files
- **Added** anonymization layer between YAML and LLM
- **Same** SQL generation, same data isolation

### What's Protected Now:
- ✅ Nestlé's "secondary_sales_value" → `value_metric_001`
- ✅ ITC's "net_trade_sales" → `value_metric_001`
- ✅ LLM cannot tell them apart!

### What Was Always Safe:
- ✅ Table names: `fact_secondary_sales` vs `fact_trade_sales`
- ✅ Column names: `net_value` vs `trade_value`
- ✅ SQL expressions: `SUM(...)` in YAML
- ✅ Client schemas: `client_nestle` vs `client_itc`

### Enable It:
```bash
export ANONYMIZE_SCHEMA=true
```

**Result**: Both Nestlé and ITC are protected. External LLM sees identical anonymous names, but they map to each client's unique schema locally! 🎉
