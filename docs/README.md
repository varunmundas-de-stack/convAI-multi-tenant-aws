# Conversational AI Project - Relational DB Only

A conversational AI chatbot for CPG (Consumer Packaged Goods) sales analytics using **DuckDB only** as the backend database.

## Overview

This version uses **DuckDB** as the sole backend for all analytics queries. It does NOT include vector databases or semantic search capabilities.

## Key Features

- ✅ Natural language queries for CPG sales data
- ✅ DuckDB-based relational analytics
- ✅ Intent parsing with Ollama LLM
- ✅ Semantic layer for query translation
- ✅ Row-level security and audit logging
- ✅ Diagnostic workflows for root cause analysis

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure Ollama is running:**
   ```bash
   ollama serve
   ```

3. **Start the web interface:**
   ```bash
   python frontend/app.py
   ```

4. Open your browser to `http://localhost:5000`

## Architecture

- **Frontend**: Flask web app with chat interface
- **Backend Database**: DuckDB (relational OLAP database)
- **LLM**: Ollama for intent parsing (local)
- **Semantic Layer**: YAML-based configuration for business logic
- **Query Engine**: SQL generation and execution

## Sample Questions

- "Show top 5 brands by sales value"
- "Weekly sales trend for last 6 weeks"
- "Why did sales change?"
- "Total sales this month"
- "Sales by state"

## Documentation

- [Setup Guide](docs/SETUP_GUIDE.md) - Detailed setup instructions
- [Testing Guide](docs/TESTING_GUIDE.md) - How to test the system
- [Architecture](docs/ARCHITECTURE.md) - System architecture details

## Technology Stack

- **Database**: DuckDB
- **LLM**: Ollama (Mistral/Llama)
- **Web Framework**: Flask
- **Python Libraries**: duckdb, pydantic, pyyaml, ollama

## Differences from ChromaDB Version

This is the **RelDB-Only** version that:
- Uses only DuckDB (no ChromaDB)
- No semantic/vector search capabilities
- Simpler architecture focused on relational queries
- For the version with vector database integration, see: [Conv-AI-ChromaDB](https://github.com/varunmundas-de-stack/Conv-AI-ChromaDB)
