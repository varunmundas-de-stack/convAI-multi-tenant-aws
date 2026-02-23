# CPG Conversational AI — Windows 11 Standalone Deployment Guide

> Full service guide for spinning up the platform on a single Windows 11 machine.
> Covers system requirements, software installation, data setup, and starting the app.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Software Prerequisites](#2-software-prerequisites)
3. [Project Setup](#3-project-setup)
4. [Python Environment](#4-python-environment)
5. [Ollama LLM Setup](#5-ollama-llm-setup)
6. [Database Initialisation](#6-database-initialisation)
7. [Client Config Verification](#7-client-config-verification)
8. [Starting the Application](#8-starting-the-application)
9. [Login Credentials Reference](#9-login-credentials-reference)
10. [Environment Variables (Optional)](#10-environment-variables-optional)
11. [Switching to Claude API (Production LLM)](#11-switching-to-claude-api-production-llm)
12. [Windows Firewall & Port Reference](#12-windows-firewall--port-reference)
13. [Auto-Start on Boot (Optional)](#13-auto-start-on-boot-optional)
14. [Troubleshooting](#14-troubleshooting)
15. [Directory Structure Reference](#15-directory-structure-reference)

---

## 1. System Requirements

### Minimum (Ollama local LLM — llama3.2:3b)

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 11 Home/Pro 22H2+ | Windows 11 Pro 23H2+ |
| **CPU** | 4-core x64 (Intel/AMD) | 8-core x64 |
| **RAM** | 8 GB | 16 GB |
| **Disk (free space)** | 12 GB | 20 GB |
| **GPU** | Not required | NVIDIA GPU with 6 GB VRAM (speeds up LLM significantly) |
| **Network** | Required during setup only | — |

> **Why 12 GB disk?**
> The `llama3.2:3b` Ollama model is ~2 GB. Python packages ~500 MB. DuckDB + SQLite databases are small (< 50 MB). Leave headroom for logs and growth.

### Minimum (Claude API — no local LLM)

| Component | Minimum | Recommended |
|---|---|---|
| **RAM** | 4 GB | 8 GB |
| **Disk (free space)** | 2 GB | 5 GB |
| **Network** | Always-on internet required | — |
| **Anthropic API key** | Required | — |

> Use Claude API mode if the machine has limited RAM or no GPU. See [Section 11](#11-switching-to-claude-api-production-llm).

---

## 2. Software Prerequisites

Install the following in order. Each section includes the exact download source and verification command.

### 2.1 Python 3.11 or later

The app was built and tested on **Python 3.13**. Python 3.11+ is required.

**Download:** https://www.python.org/downloads/windows/
Choose the latest **Python 3.13.x Windows installer (64-bit)**.

**During installation — critical settings:**
- Check **"Add Python to PATH"** (checkbox at the bottom of the first screen)
- Click **"Install Now"**

**Verify:**
```
python --version
```
Expected output: `Python 3.13.x` (or 3.11 / 3.12)

```
pip --version
```
Expected output: `pip 25.x from ...`

---

### 2.2 Git (for cloning the repository)

**Download:** https://git-scm.com/download/win
Use all default options during install.

**Verify:**
```
git --version
```

> If you already have the project as a ZIP file, Git is not required — skip to Section 3.

---

### 2.3 Ollama (local LLM runtime)

Ollama runs the `llama3.2:3b` language model locally. This is the default LLM the app uses to understand natural language queries.

**Download:** https://ollama.com/download
Run the installer. Ollama installs as a Windows service and starts automatically.

**Verify:**
```
ollama --version
```
Expected output: `ollama version 0.x.x`

**Check Ollama is running:**
```
ollama list
```
If Ollama is not running, start it manually:
```
ollama serve
```

> Ollama listens on `http://localhost:11434` by default. Keep this port free.

---

## 3. Project Setup

### Option A — Clone from Git

Open **Command Prompt** or **PowerShell** and run:

```
git clone <your-repo-url> C:\ProgramData\projects\convAI-multi-tenant-cubejs
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
```

### Option B — Copy from ZIP / USB

Extract the project to:
```
C:\ProgramData\projects\convAI-multi-tenant-cubejs\
```

Confirm the folder contains these items:
```
C:\ProgramData\projects\convAI-multi-tenant-cubejs\
├── frontend\
├── database\
├── semantic_layer\
├── llm\
├── insights\
├── query_engine\
├── security\
├── requirements.txt
└── start_chatbot.bat
```

---

## 4. Python Environment

All commands below assume your working directory is the project root.

```
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
```

### 4.1 (Recommended) Create a virtual environment

```
python -m venv venv
venv\Scripts\activate
```

Your prompt should now show `(venv)` at the start.

> Use the virtual environment for every subsequent step. If you open a new terminal later, re-activate with `venv\Scripts\activate` before running anything.

### 4.2 Install core dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `flask>=3.0.0` | Web framework |
| `duckdb>=0.9.0` | Analytics database |
| `ollama>=0.1.0` | Ollama Python client |
| `pydantic>=2.5.0` | Data validation / schemas |
| `pyyaml>=6.0.1` | Client YAML config loading |
| `rich>=13.7.0` | Terminal output formatting |
| `python-dateutil>=2.8.2` | Date parsing for queries |
| `anthropic>=0.18.0` | Claude API client (optional) |
| `pytest>=7.0.0` | Test runner |

### 4.3 Install authentication dependencies

These are not in `requirements.txt` and must be installed separately:

```
pip install flask-login bcrypt werkzeug
```

### 4.4 Verify all packages installed

```
pip list | findstr /I "flask duckdb ollama bcrypt pydantic"
```

You should see rows for each of these packages.

---

## 5. Ollama LLM Setup

### 5.1 Pull the llama3.2:3b model

This downloads ~2 GB. Run once — it caches locally.

```
ollama pull llama3.2:3b
```

Wait for the download to complete. You will see a progress bar.

**Verify the model is available:**
```
ollama list
```
Expected output includes a row with `llama3.2:3b`.

### 5.2 Test the model works

```
ollama run llama3.2:3b "Say hello in one sentence"
```

You should get a short response. Press `Ctrl+C` to exit the interactive mode.

### 5.3 Keep Ollama running

Ollama installs as a background Windows service. It starts automatically on boot.

To confirm it is running:
```
curl http://localhost:11434
```
Expected response: `Ollama is running`

If it is not running, start it:
```
ollama serve
```
Leave this terminal open (or run it minimised).

---

## 6. Database Initialisation

This step creates two databases:
- `database\users.db` — SQLite file for users, roles, and insights
- `database\cpg_multi_tenant.duckdb` — DuckDB file with 3 tenant schemas (Nestle, Unilever, ITC) and sample sales data

Run both scripts from the project root with the virtual environment active:

```
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
venv\Scripts\activate
```

### 6.1 Create the user + insights database

```
python database\create_user_db.py
```

Expected output ends with:
```
[OK] User database created successfully!
[OK] Database created at: ...database\users.db
```

### 6.2 Create the analytics database with tenant schemas

```
python database\create_multi_schema_demo.py
```

This creates three isolated DuckDB schemas:
- `client_nestle` — Nestlé India sales data
- `client_unilever` — Unilever India sales data
- `client_itc` — ITC Limited sales data

Expected output ends with:
```
[OK] Multi-tenant database created at: ...database\cpg_multi_tenant.duckdb
[OK] File size: ... KB
```

### 6.3 Verify databases exist

```
dir database\*.db database\*.duckdb
```

You should see both files listed.

---

## 7. Client Config Verification

The semantic layer uses per-client YAML config files to know which DuckDB schema and metrics to expose. These should already exist in the project.

**Check they exist:**
```
dir semantic_layer\configs\
```

Expected files:
```
client_nestle.yaml
client_unilever.yaml
client_itc.yaml
```

If the `configs\` folder is missing or empty, recreate it:

```
mkdir semantic_layer\configs
copy semantic_layer\config_cpg.yaml semantic_layer\configs\client_nestle.yaml
copy semantic_layer\config_cpg.yaml semantic_layer\configs\client_unilever.yaml
copy semantic_layer\config_cpg.yaml semantic_layer\configs\client_itc.yaml
```

Then open each file and update the `client.id`, `client.name`, and `database.schema` fields to match the tenant (nestle / unilever / itc).

---

## 8. Starting the Application

### 8.1 Standard start (recommended)

```
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
venv\Scripts\activate
python frontend\app_with_auth.py
```

You will see:
```
============================================================
CPG Conversational AI Chatbot (RBAC Enabled)
============================================================
Starting Flask server...
Open your browser and go to: http://localhost:5000
...
 * Running on http://0.0.0.0:5000
```

### 8.2 Open the application

Open any browser and go to:
```
http://localhost:5000
```

You will see the login page. Use any of the credentials from [Section 9](#9-login-credentials-reference).

### 8.3 Using the batch file (quick launch)

The project includes a convenience batch file. However, it launches the unauthenticated `app.py`. For the full RBAC-enabled app, use the command above or create your own batch file:

Create `start_app.bat` in the project root:
```bat
@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python frontend\app_with_auth.py
pause
```

Double-click `start_app.bat` to launch.

---

## 9. Login Credentials Reference

All sample users are created by `database\create_user_db.py`.

### Standard (non-hierarchy) users

| Username | Password | Client | Role |
|---|---|---|---|
| `nestle_admin` | `admin123` | Nestlé India | Admin |
| `nestle_analyst` | `analyst123` | Nestlé India | Analyst |
| `unilever_admin` | `admin123` | Unilever India | Admin |
| `unilever_analyst` | `analyst123` | Unilever India | Analyst |
| `itc_admin` | `admin123` | ITC Limited | Admin |
| `itc_analyst` | `analyst123` | ITC Limited | Analyst |

### Sales hierarchy users (Nestlé — Push Insights enabled)

These users see the **Targeted Insights** tab on login with role-filtered nudges.

| Username | Password | Role | Scope |
|---|---|---|---|
| `nsm_rajesh` | `nsm123` | NSM | Full national view |
| `zsm_amit` | `zsm123` | ZSM | Zone North only |
| `asm_rahul` | `asm123` | ASM | Area ZSM01_ASM1 only |
| `so_field1` | `so123` | SO | Territory ZSM01_ASM1_SO01 only |

> **Row-Level Security is enforced.** Each user only sees data for their assigned territory, area, zone, or nation. They cannot query data outside their scope.

---

## 10. Environment Variables (Optional)

You can configure the app behaviour using environment variables. Set them in the terminal before starting the app, or add them to a `.env` file (Flask does not auto-load `.env` — set them in the shell or in System Properties).

### Setting in Command Prompt

```
set FLASK_SECRET_KEY=change-this-to-a-long-random-string
set USE_CLAUDE_API=false
set ANTHROPIC_API_KEY=sk-ant-...
set ANONYMIZE_SCHEMA=false
```

### Setting permanently (System Properties)

1. Open **Start → Search → "Edit the system environment variables"**
2. Click **Environment Variables**
3. Under **System variables**, click **New** for each variable

### Variable reference

| Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-key-change-in-production` | Flask session signing key. **Change this in production.** |
| `USE_CLAUDE_API` | `false` | Set to `true` to use Claude API instead of Ollama |
| `ANTHROPIC_API_KEY` | _(none)_ | Required if `USE_CLAUDE_API=true` |
| `ANONYMIZE_SCHEMA` | `false` | Anonymise schema names before sending to external LLM |

---

## 11. Switching to Claude API (Production LLM)

By default the app uses **Ollama + llama3.2:3b** locally. For better query accuracy and to avoid needing Ollama or a large model download, you can switch to the **Claude API**.

### Requirements

- Anthropic account with API access
- `ANTHROPIC_API_KEY` environment variable set
- Always-on internet connection

### Steps

1. Get your API key from https://console.anthropic.com/

2. Set the environment variable:
   ```
   set USE_CLAUDE_API=true
   set ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

3. Start the app normally:
   ```
   python frontend\app_with_auth.py
   ```

The app will use Claude (currently defaults to `claude-sonnet-4-6`) for all NL→SQL intent parsing. Ollama does not need to be installed.

> **Cost note:** Each user query makes one Claude API call. For internal demos and light usage, cost is typically < $1/day. For production usage, monitor your Anthropic usage dashboard.

---

## 12. Windows Firewall & Port Reference

| Service | Port | Protocol | When Used |
|---|---|---|---|
| Flask (app) | **5000** | TCP | Always — main web interface |
| Ollama (LLM) | **11434** | TCP | When `USE_CLAUDE_API=false` |
| Metabase (optional) | **3000** | TCP | If Docker/Metabase is running |

### Allowing Flask through Windows Firewall (for LAN access)

If you want other machines on the same network to access the app:

1. Open **Start → Windows Defender Firewall → Advanced Settings**
2. Click **Inbound Rules → New Rule**
3. Select **Port**, click Next
4. Select **TCP**, enter port `5000`, click Next
5. Select **Allow the connection**, click Next through remaining steps
6. Name it `CPG Analytics App`, click Finish

Then users on the same network access via:
```
http://<this-machine-ip>:5000
```

Find your machine IP:
```
ipconfig
```
Look for **IPv4 Address** under your active adapter.

---

## 13. Auto-Start on Boot (Optional)

To have the app start automatically when Windows boots, create a Scheduled Task.

### Method: Task Scheduler

1. Create a file `start_cpg_app.bat` in the project root:

```bat
@echo off
cd /d "C:\ProgramData\projects\convAI-multi-tenant-cubejs"
call venv\Scripts\activate
set FLASK_SECRET_KEY=your-secret-key-here
python frontend\app_with_auth.py >> logs\app.log 2>&1
```

2. Create the logs directory:
```
mkdir C:\ProgramData\projects\convAI-multi-tenant-cubejs\logs
```

3. Open **Task Scheduler** (search in Start menu)
4. Click **Create Basic Task**
5. Name: `CPG Analytics App`
6. Trigger: **When the computer starts**
7. Action: **Start a program**
8. Program: `C:\ProgramData\projects\convAI-multi-tenant-cubejs\start_cpg_app.bat`
9. Check **Run with highest privileges**
10. Click Finish

> Ollama installs its own Windows service and starts automatically — no extra config needed for Ollama on boot.

---

## 14. Troubleshooting

### App crashes on start with `sqlite3.OperationalError: unable to open database file`

**Cause:** Databases have not been created yet, or paths are wrong.

**Fix:**
```
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
python database\create_user_db.py
python database\create_multi_schema_demo.py
```

---

### `ModuleNotFoundError: No module named 'flask_login'` or `'bcrypt'`

**Cause:** Auth packages not installed.

**Fix:**
```
pip install flask-login bcrypt werkzeug
```

---

### `ModuleNotFoundError: No module named 'ollama'`

**Cause:** `requirements.txt` not installed, or wrong Python environment.

**Fix:**
```
pip install -r requirements.txt
```
If using a virtual environment, make sure it is activated first: `venv\Scripts\activate`

---

### Login returns 500 error / server crashes

**Cause:** Often the virtual environment is not activated, or a package is missing.

**Fix:** Start a fresh terminal, re-activate the venv, then start the app:
```
cd C:\ProgramData\projects\convAI-multi-tenant-cubejs
venv\Scripts\activate
python frontend\app_with_auth.py
```

---

### Ollama not found / `Connection refused` on port 11434

**Cause:** Ollama is not running.

**Fix:**
```
ollama serve
```
Leave that terminal open, then start the Flask app in a separate terminal.

---

### Queries return `LLM unavailable` or fallback responses

**Cause:** Ollama is running but the model has not been pulled, or Ollama is unreachable.

**Fix:**
```
ollama pull llama3.2:3b
ollama list
```
Confirm `llama3.2:3b` appears in the list.

---

### "No insights yet" in the Targeted Insights tab

**Cause:** The background insights thread runs 10 seconds after startup, then every 6 hours. It may not have run yet, or the analytics database is empty.

**Fix:** Wait 15–30 seconds after starting the app, then refresh the Insights tab. If still empty, check the terminal output for `[Insights]` log lines and any errors.

---

### Port 5000 already in use

**Cause:** Another process is using port 5000 (e.g. AirPlay Receiver on older Windows builds, or another Flask instance).

**Fix — find and kill the process:**
```
netstat -ano | findstr :5000
taskkill /PID <pid-from-above> /F
```

Or change the Flask port in `frontend\app_with_auth.py` (last line):
```python
app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
```

---

### `bcrypt` install fails on Python 3.13

**Cause:** Some versions of bcrypt do not have pre-built wheels for Python 3.13.

**Fix:**
```
pip install bcrypt --pre
```
Or install the latest release candidate:
```
pip install "bcrypt>=4.1.0"
```

---

## 15. Directory Structure Reference

```
convAI-multi-tenant-cubejs\
│
├── frontend\                    # Flask web application
│   ├── app_with_auth.py         # Main app — ALWAYS use this (RBAC-enabled)
│   ├── app.py                   # Legacy app (no auth) — do not use in production
│   ├── visualization_helper.py  # Chart rendering helpers
│   ├── static\
│   │   └── chart-renderer.js    # Client-side chart utilities
│   └── templates\
│       ├── login.html           # Login page
│       └── chat.html            # Main chatbot UI (two-pillar layout)
│
├── database\                    # Database scripts and data files
│   ├── create_user_db.py        # Creates users.db (SQLite)
│   ├── create_multi_schema_demo.py  # Creates cpg_multi_tenant.duckdb
│   ├── users.db                 # ← CREATED on first run
│   └── cpg_multi_tenant.duckdb  # ← CREATED on first run
│
├── semantic_layer\              # NL → SQL translation layer
│   ├── semantic_layer.py        # Core semantic layer
│   ├── query_builder.py         # SQL query construction
│   ├── orchestrator.py          # Query orchestration
│   ├── validator.py             # Query validation
│   ├── config_cpg.yaml          # Master config template
│   └── configs\                 # Per-tenant configs
│       ├── client_nestle.yaml
│       ├── client_unilever.yaml
│       └── client_itc.yaml
│
├── llm\                         # LLM intent parsing
│   └── intent_parser_v2.py      # Ollama + Claude dual-provider parser
│
├── insights\                    # Push insights engine
│   ├── hierarchy_insights_engine.py  # Generates role-targeted nudges
│   └── push_insights_engine.py
│
├── query_engine\                # SQL execution layer
│   ├── executor.py              # DuckDB query execution with RLS
│   └── query_validator.py       # Query safety validation
│
├── security\                    # Auth and access control
│   ├── auth.py                  # AuthManager (bcrypt login)
│   ├── rls.py                   # Row-Level Security enforcement
│   └── audit.py                 # Audit logging
│
├── requirements.txt             # Python dependencies
├── start_chatbot.bat            # Quick-launch (legacy, no auth)
├── setup_rbac.bat               # One-time setup helper
└── DEPLOYMENT_GUIDE.md          # This file
```

---

## Quick-Start Checklist

Use this as a final checklist before going live:

- [ ] Windows 11 machine with 8+ GB RAM
- [ ] Python 3.11+ installed and on PATH
- [ ] `pip install -r requirements.txt` completed
- [ ] `pip install flask-login bcrypt werkzeug` completed
- [ ] Ollama installed and `ollama serve` is running
- [ ] `ollama pull llama3.2:3b` completed
- [ ] `python database\create_user_db.py` ran successfully
- [ ] `python database\create_multi_schema_demo.py` ran successfully
- [ ] `database\users.db` exists
- [ ] `database\cpg_multi_tenant.duckdb` exists
- [ ] `semantic_layer\configs\client_nestle.yaml` exists
- [ ] `semantic_layer\configs\client_unilever.yaml` exists
- [ ] `semantic_layer\configs\client_itc.yaml` exists
- [ ] `FLASK_SECRET_KEY` set to a secure value
- [ ] `python frontend\app_with_auth.py` starts without errors
- [ ] Browser opens `http://localhost:5000` and shows login page
- [ ] Login with `nestle_admin / admin123` succeeds
- [ ] Insights tab loads (may take 15 sec on first run)
- [ ] Chat tab accepts a query and returns a response

---

*Last updated: February 2026*
