# CPG Conversational AI - Multi-Client RBAC System

**Enterprise-grade conversational analytics platform with strict multi-tenant isolation**

---

## Overview

A production-ready CPG (Consumer Packaged Goods) analytics chatbot with Role-Based Access Control (RBAC) and complete multi-client data isolation. Built to demonstrate secure, scalable conversational AI for enterprise environments.

**Key Innovation:** YAML-based semantic layer ensures client data isolation without exposing raw data to LLM prompts.

---

## Features

- **Multi-Tenant RBAC** - Complete client data isolation (Nestlé, Unilever, ITC)
- **Zero Data Leakage** - Client-specific YAML configs never cross-contaminate
- **Semantic Layer** - Business metrics abstraction without exposing database schema
- **🔒 Schema Anonymization** - Protect metadata when using external LLMs (Claude API, OpenAI)
- **AST-Based SQL Generation** - Type-safe, injection-proof query construction
- **Flask Authentication** - Secure session management with bcrypt password hashing
- **DuckDB Multi-Schema** - Isolated schemas for each client in single database
- **Audit Trail** - Complete logging of all queries with user identity
- **Intent Parsing** - Natural language queries without exposing data to LLM

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/varunmundas-de-stack/Conve-AI-Project-RelDB-Only.git
cd Conve-AI-Project-RelDB-Only

# Install dependencies
pip install duckdb ollama pydantic pyyaml rich python-dateutil flask flask-login werkzeug bcrypt

# Create databases
python database/create_user_db.py
python database/create_multi_schema_demo.py

# Start server
python frontend/app_with_auth.py

# Open browser: http://localhost:5000
# Login: nestle_analyst / nestle123
```

**Done in 5 minutes!** 🎉

---

## Documentation

### 📐 [ARCHITECTURE.md](ARCHITECTURE.md)
**Complete technical architecture documentation**
- System architecture diagrams
- Component breakdown with code examples
- Data flow visualization
- Query processing chain (7 steps)
- Multi-client isolation mechanisms
- Security architecture (5 layers)
- Database schemas
- Performance characteristics

### 🚀 [SETUP_GUIDE.md](SETUP_GUIDE.md)
**Full setup and deployment guide**
- Prerequisites and system requirements
- Detailed installation steps
- Testing procedures (7 test scenarios)
- Troubleshooting guide
- Production deployment options
- User management

---

## Architecture Highlights

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────────────────────────┐
│        Flask Frontend               │
│  • Login/Logout                     │
│  • Session Management               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│     Authentication Layer            │
│  • Flask-Login (session cookies)    │
│  • Bcrypt password hashing          │
│  • users.db (SQLite)                │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│    Semantic Layer (Client YAML)     │
│  • client_nestle.yaml               │
│  • client_unilever.yaml             │
│  • client_itc.yaml                  │
│  → ONLY user's client YAML loaded   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│       Query Builder (AST)           │
│  • Type-safe SQL generation         │
│  • Schema-qualified table names     │
│  • Injection-proof                  │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│   DuckDB Multi-Schema Database      │
│  • client_nestle (isolated)         │
│  • client_unilever (isolated)       │
│  • client_itc (isolated)            │
└─────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | Flask 3.1, Jinja2 templates, vanilla JavaScript |
| **Authentication** | Flask-Login 0.6, bcrypt 5.0 |
| **User Database** | SQLite 3 (users.db) |
| **Analytics Database** | DuckDB 1.4 (multi-schema) |
| **Semantic Layer** | YAML configs, Pydantic models |
| **SQL Generation** | AST-based (injection-proof) |
| **Language** | Python 3.12 |

---

## Security Features

1. **Session Management** - HTTP-only cookies, SameSite protection, session expiry
2. **Password Security** - Bcrypt hashing with salt rounds
3. **SQL Injection Protection** - AST-based query generation (no string concatenation)
4. **Schema Isolation** - Client schemas completely separated in database
5. **YAML Isolation** - Only authorized client config loaded per user
6. **Schema Anonymization** - Protect metadata when using external LLMs ([Quick Start](ANONYMIZATION_QUICKSTART.md))
7. **Audit Trail** - All queries logged with user identity and timestamp

---

## 🔒 Schema Anonymization (NEW)

Protect your database schema metadata when using external LLMs:

```python
# Enable anonymization for production with Claude API
export ANONYMIZE_SCHEMA=true
export USE_CLAUDE_API=true

# That's it! Your schema is now protected 🔒
```

**What gets protected:**
- ✅ Metric names: `secondary_sales_value` → `value_metric_001`
- ✅ Dimension names: `brand_name` → `product_dimension_001`
- ✅ Descriptions: "Net invoiced value" → "Monetary value measurement"

**What stays secure (never sent):**
- ✅ Table names, column names, SQL expressions
- ✅ Database credentials and connection strings
- ✅ Actual data values

**Quick Links:**
- 📖 [Quick Start Guide](ANONYMIZATION_QUICKSTART.md) - Get started in 3 steps
- 📚 [Complete Guide](docs/ANONYMIZATION_GUIDE.md) - Full documentation
- 🧪 [Demo](demos/demo_anonymization.py) - See it in action

---

## Sample Users (Development)

| Username | Password | Client | Access |
|----------|----------|--------|--------|
| nestle_analyst | nestle123 | Nestlé India | client_nestle schema only |
| unilever_analyst | unilever123 | Hindustan Unilever | client_unilever schema only |
| itc_analyst | itc123 | ITC Limited | client_itc schema only |

**Note:** Change passwords in production!

---

## Project Structure

```
Conve-AI-Project-RelDB-Only/
├── database/
│   ├── users.db                    # User authentication (SQLite)
│   ├── cpg_multi_tenant.duckdb     # Analytics data (DuckDB)
│   ├── create_user_db.py           # Setup authentication DB
│   └── create_multi_schema_demo.py # Setup multi-tenant analytics DB
├── semantic_layer/
│   ├── configs/
│   │   ├── client_nestle.yaml      # Nestlé metrics & dimensions
│   │   ├── client_unilever.yaml    # Unilever metrics & dimensions
│   │   └── client_itc.yaml         # ITC metrics & dimensions
│   ├── semantic_layer.py           # YAML loader & metric definitions
│   ├── anonymizer.py               # Schema anonymization (NEW!)
│   ├── query_builder.py            # AST-based SQL generation
│   └── models.py                   # Pydantic data models
├── frontend/
│   ├── app_with_auth.py            # Main Flask application
│   └── templates/
│       ├── login.html              # Login interface
│       └── chat.html               # Chat interface
├── docs/
│   ├── ANONYMIZATION_GUIDE.md      # Detailed anonymization guide
│   └── supplementary/              # Additional references
├── demos/
│   └── demo_anonymization.py       # Interactive anonymization demo
├── tests/
│   └── test_anonymization.py       # Unit tests
├── README.md                       # This file (quick start)
├── ARCHITECTURE.md                 # Complete technical architecture
└── SETUP_GUIDE.md                  # Full Windows setup guide
```

---

## License

MIT License - See LICENSE file for details

---

## Contributing

This is a demonstration project. For production use:
1. Change default passwords
2. Configure HTTPS/TLS
3. Set up database backups
4. Enable monitoring and logging
5. Use production WSGI server (Waitress/Gunicorn)

---

**For detailed technical documentation, see [ARCHITECTURE.md](ARCHITECTURE.md)**

**For setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)**
