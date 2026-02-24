# CPG Conversational AI — Deployment Guide

> End-to-end setup guide for running the platform on a Windows 11 machine.
> Covers system requirements, installation, data setup, and starting the app.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Software Prerequisites](#2-software-prerequisites)
3. [Clone the Repository](#3-clone-the-repository)
4. [Python Environment](#4-python-environment)
5. [LLM Setup](#5-llm-setup)
6. [Database Initialisation](#6-database-initialisation)
7. [Starting the Application](#7-starting-the-application)
8. [Login Credentials](#8-login-credentials)
9. [Environment Variables](#9-environment-variables)
10. [Sharing the App (ngrok / LAN)](#10-sharing-the-app-ngrok--lan)
11. [AWS Cloud Deployment](#11-aws-cloud-deployment)
12. [Windows Firewall & Ports](#12-windows-firewall--ports)
13. [Auto-Start on Boot](#13-auto-start-on-boot)
14. [Troubleshooting](#14-troubleshooting)
15. [Directory Structure](#15-directory-structure)
16. [Quick-Start Checklist](#16-quick-start-checklist)

---

## 1. System Requirements

### Option A — Ollama (local LLM, no internet needed after setup)

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 11 Home/Pro 22H2+ | Windows 11 Pro 23H2+ |
| **CPU** | 4-core x64 | 8-core x64 |
| **RAM** | 8 GB | 16 GB |
| **Disk (free)** | 12 GB | 20 GB |
| **GPU** | Not required | NVIDIA 6 GB VRAM (speeds up LLM) |
| **Network** | Setup only | — |

### Option B — Claude API (recommended for demos, needs internet)

| Component | Minimum |
|---|---|
| **RAM** | 4 GB |
| **Disk (free)** | 2 GB |
| **Network** | Always-on internet |
| **Anthropic API key** | Required — get one at https://console.anthropic.com |

> Claude API gives better query accuracy and requires no local model download.
> See [Section 5.2](#52-option-b--claude-api-recommended) to enable it.

---

## 2. Software Prerequisites

### 2.1 Python 3.11 or later

**Download:** https://www.python.org/downloads/windows/
Choose the latest **Python 3.13.x Windows installer (64-bit)**.

**During installation:**
- Check **"Add Python to PATH"** on the first screen
- Click **"Install Now"**

**Verify:**
```
python --version
pip --version
```

---

### 2.2 Git

**Download:** https://git-scm.com/download/win — use all default options.

**Verify:**
```
git --version
```

> If you have the project as a ZIP, skip this — extract and go to Section 4.

---

### 2.3 Node.js 20+ (for React frontend build)

**Download:** https://nodejs.org — choose the **LTS** version.

**Verify:**
```
node --version
npm --version
```

> Node is only needed once to build the React frontend. It does not need to run permanently.

---

### 2.4 Ollama (only if using local LLM — skip if using Claude API)

**Download:** https://ollama.com/download — run the installer.
Ollama installs as a Windows service and starts automatically.

**Verify:**
```
ollama --version
ollama list
```

---

## 3. Clone the Repository

Open **PowerShell** or **Command Prompt** and run:

```
git clone https://github.com/varunmundas-de-stack/convAI-multi-tenant-cubejs.git
cd convAI-multi-tenant-cubejs
```

> If you received the project as a ZIP, extract it and `cd` into the folder instead.

After cloning, confirm these folders exist:
```
frontend\
frontend_react\
database\
semantic_layer\
llm\
insights\
query_engine\
security\
config\
aws-deploy\
docs\
scripts\
```

---

## 4. Python Environment

All commands below run from the project root folder.

### 4.1 Create a virtual environment

```
python -m venv venv
venv\Scripts\activate
```

Your prompt should now show `(venv)`. Re-run `venv\Scripts\activate` any time you open a new terminal.

### 4.2 Install all dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

This installs everything — Flask, DuckDB, Ollama client, Claude API client, auth packages, and test tools.

**Verify key packages:**
```
pip list | findstr /I "flask duckdb ollama bcrypt anthropic"
```

---

## 5. LLM Setup

The app supports two LLM backends. Choose one.

### 5.1 Option A — Ollama (local, offline)

**Pull the model (~2 GB download, runs once):**
```
ollama pull llama3.2:3b
```

**Verify:**
```
ollama list
```
You should see `llama3.2:3b` listed.

**Test it:**
```
ollama run llama3.2:3b "Say hello in one sentence"
```

**Keep Ollama running** (it installs as a Windows service — starts automatically on boot):
```
curl http://localhost:11434
```
Expected: `Ollama is running`

If not running, start it manually:
```
ollama serve
```

---

### 5.2 Option B — Claude API (recommended)

No model download needed. Requires an Anthropic API key.

1. Get your API key: https://console.anthropic.com → API Keys → Create Key

2. Set the environment variables before starting the app:
   ```
   set USE_CLAUDE_API=true
   set ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

3. Ollama does **not** need to be installed when using this option.

> Cost: ~$0.01–$0.05 per query. For light demo usage, typically under $1/day.

---

## 6. Database Initialisation

This step creates two database files. Run it once on first setup.

```
cd convAI-multi-tenant-cubejs
venv\Scripts\activate
```

### 6.1 Create the users and insights database

```
python database\create_user_db.py
```

Expected output:
```
[OK] User database created at: ...database\users.db
```

### 6.2 Create the analytics database with tenant data

```
python database\create_multi_schema_demo.py
```

This creates `database\cpg_multi_tenant.duckdb` with three isolated schemas:
- `client_nestle` — Nestlé India sample sales data
- `client_unilever` — Unilever India sample sales data
- `client_itc` — ITC Limited sample sales data

Expected output:
```
[OK] Multi-tenant database created at: ...database\cpg_multi_tenant.duckdb
```

### 6.3 Verify

```
dir database\*.db database\*.duckdb
```

Both files should appear.

---

## 7. Starting the Application

### 7.1 Build the React frontend (first time only)

```
cd frontend_react
npm install
npm run build
cd ..
```

This compiles the React app into `frontend\static\react\` where Flask serves it.

> You only need to re-run this if you make changes to the React source in `frontend_react\src\`.

### 7.2 Start the Flask app

```
venv\Scripts\activate
python frontend\app_with_auth.py
```

You will see:
```
============================================================
CPG Conversational AI Chatbot (RBAC Enabled)
============================================================
Open your browser and go to: http://localhost:5000
 * Running on http://0.0.0.0:5000
```

### 7.3 Open in browser

```
http://localhost:5000
```

The login page will appear.

### 7.4 Quick-launch batch file

A convenience script is included in `scripts\`:

```
scripts\start_chatbot.bat
```

Double-click it or run from PowerShell. It activates the venv and starts the app automatically.

---

## 8. Login Credentials

All users are created by `database\create_user_db.py`.

### Standard users

| Username | Password | Tenant | Role |
|---|---|---|---|
| `nestle_admin` | `admin123` | Nestlé India | Admin — full access |
| `nestle_analyst` | `analyst123` | Nestlé India | Analyst |
| `unilever_admin` | `admin123` | Unilever India | Admin |
| `unilever_analyst` | `analyst123` | Unilever India | Analyst |
| `itc_admin` | `admin123` | ITC Limited | Admin |
| `itc_analyst` | `analyst123` | ITC Limited | Analyst |

### Sales hierarchy users (Nestlé — Insights tab enabled)

| Username | Password | Role | Data Scope |
|---|---|---|---|
| `nsm_rajesh` | `nsm123` | NSM | Full national view |
| `zsm_amit` | `zsm123` | ZSM | Zone North only |
| `asm_rahul` | `asm123` | ASM | Area ZSM01_ASM1 only |
| `so_field1` | `so123` | SO | Territory ZSM01_ASM1_SO01 only |

> Row-Level Security is enforced — each user can only query data within their assigned scope.

---

## 9. Environment Variables

Set these in the terminal before starting the app, or add to Windows System Environment Variables.

| Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-key-change-in-production` | Flask session signing key. **Always change in production.** |
| `USE_CLAUDE_API` | `false` | Set `true` to use Claude API instead of Ollama |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when `USE_CLAUDE_API=true` |
| `ANONYMIZE_SCHEMA` | `false` | Anonymise DB schema names before sending to external LLM |

**Set in PowerShell:**
```powershell
$env:FLASK_SECRET_KEY = "your-long-random-secret"
$env:USE_CLAUDE_API = "true"
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

**Set permanently (Windows):**
1. Start → search "Edit the system environment variables"
2. Click **Environment Variables** → **New** under System variables

---

## 10. Sharing the App (ngrok / LAN)

### Option A — ngrok (share publicly via URL, works from anywhere)

Useful for remote demos where attendees are not on the same network.

1. Download ngrok: https://ngrok.com/download (or `winget install ngrok.ngrok`)
2. Sign up free at https://dashboard.ngrok.com and get your authtoken
3. Configure:
   ```
   ngrok config add-authtoken YOUR_TOKEN
   ```
4. Start the app on port 5000, then in a second terminal:
   ```
   ngrok http 5000
   ```
5. Share the `https://xxxx.ngrok-free.app` URL with attendees

> The ngrok window must stay open for the URL to work. Free tier generates a new random URL on each restart.

### Option B — LAN IP (in-room demo, same Wi-Fi)

No extra software needed. Everyone on the same network accesses via your machine's IP.

1. Find your IP:
   ```
   ipconfig
   ```
   Look for **IPv4 Address** (e.g. `192.168.1.100`)

2. Share: `http://192.168.1.100:5000`

3. Allow port 5000 through Windows Firewall (see [Section 12](#12-windows-firewall--ports))

---

## 11. AWS Cloud Deployment

For a production-grade cloud deployment on AWS EC2, all scripts are in `aws-deploy\`.

See: [`aws-deploy/README.md`](../aws-deploy/README.md)

**Quick summary:**
- Launch EC2 `t3.medium` (Ubuntu 22.04)
- Run `aws-deploy/setup.sh` on the instance
- Set `ANTHROPIC_API_KEY` in `.env`
- App runs behind Nginx on port 80
- Cost: ~$33/month

---

## 12. Windows Firewall & Ports

| Service | Port | When used |
|---|---|---|
| Flask app | **5000** | Always |
| Ollama LLM | **11434** | When `USE_CLAUDE_API=false` |

### Allow port 5000 for LAN access

1. Start → **Windows Defender Firewall → Advanced Settings**
2. **Inbound Rules → New Rule → Port → TCP → 5000**
3. Allow the connection → name it `CPG Analytics App`

---

## 13. Auto-Start on Boot

Create `start_cpg_app.bat` in the project root:

```bat
@echo off
cd /d "C:\path\to\convAI-multi-tenant-cubejs"
call venv\Scripts\activate
set FLASK_SECRET_KEY=your-secret-key-here
python frontend\app_with_auth.py >> logs\app.log 2>&1
```

Create the logs folder:
```
mkdir logs
```

Then add it to **Task Scheduler**:
1. Start → **Task Scheduler → Create Basic Task**
2. Name: `CPG Analytics App`
3. Trigger: **When the computer starts**
4. Action: **Start a program** → browse to `start_cpg_app.bat`
5. Check **Run with highest privileges** → Finish

---

## 14. Troubleshooting

### `sqlite3.OperationalError: unable to open database file`
Databases not created yet.
```
python database\create_user_db.py
python database\create_multi_schema_demo.py
```

### `ModuleNotFoundError: No module named 'flask_login'`
```
pip install -r requirements.txt
```

### Login returns 500 error
Virtual environment not active. Start fresh:
```
venv\Scripts\activate
python frontend\app_with_auth.py
```

### `Connection refused` on port 11434 (Ollama)
```
ollama serve
```
Leave that terminal open, then start Flask in a second terminal.

### Insights tab is empty
Wait 15–30 seconds after app starts — insights are generated in a background thread.
Check terminal for `[Insights]` log lines.

### Port 5000 already in use
```
netstat -ano | findstr :5000
taskkill /PID <pid> /F
```
Or change the port in the last line of `frontend\app_with_auth.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
```

### `bcrypt` fails to install on Python 3.13
```
pip install "bcrypt>=4.1.0"
```

### React frontend not loading (blank page / 404 on `/`)
The React build hasn't been run yet:
```
cd frontend_react
npm install
npm run build
cd ..
```

---

## 15. Directory Structure

```
convAI-multi-tenant-cubejs\
│
├── frontend\                        # Flask web application
│   ├── app_with_auth.py             # Main app entry point (RBAC-enabled)
│   └── static\
│       └── react\                   # Built React frontend (generated by npm run build)
│
├── frontend_react\                  # React source code
│   ├── src\
│   │   ├── components\              # ChatTab, DashboardTab, InsightsTab, etc.
│   │   ├── pages\                   # LoginPage, DashboardPage
│   │   └── api\client.js            # API client
│   ├── package.json
│   └── vite.config.js
│
├── database\                        # Database scripts and files
│   ├── create_user_db.py            # Creates users.db
│   ├── create_multi_schema_demo.py  # Creates cpg_multi_tenant.duckdb
│   ├── generate_cpg_data.py         # Sample data generator
│   ├── multi_db_manager.py          # Multi-DB connection manager
│   ├── schema_cpg.sql               # CPG schema reference
│   ├── users.db                     # ← created on first run
│   └── cpg_multi_tenant.duckdb      # ← created on first run
│
├── semantic_layer\                  # NL → SQL translation
│   ├── semantic_layer.py
│   ├── query_builder.py
│   ├── orchestrator.py
│   ├── validator.py
│   ├── config_cpg.yaml              # Master config template
│   └── configs\                     # Per-tenant configs
│       ├── client_nestle.yaml
│       ├── client_unilever.yaml
│       └── client_itc.yaml
│
├── llm\                             # LLM intent parsing
│   └── intent_parser_v2.py          # Ollama + Claude dual-provider parser
│
├── insights\                        # Targeted insights engine
│   └── hierarchy_insights_engine.py
│
├── query_engine\                    # SQL execution
│   ├── executor.py
│   └── query_validator.py
│
├── security\                        # Auth and access control
│   ├── auth.py
│   ├── rls.py                       # Row-Level Security
│   └── audit.py
│
├── config\
│   └── database_config.yaml         # Multi-tenant DB connection config
│
├── aws-deploy\                      # AWS EC2 deployment scripts
│   ├── setup.sh                     # One-time EC2 setup
│   ├── deploy.sh                    # Re-deploy after code changes
│   ├── docker-compose.prod.yml      # Production Docker config
│   ├── nginx.conf                   # Nginx reverse proxy config
│   └── README.md                    # AWS deployment guide
│
├── docs\                            # Documentation
│   ├── DEPLOYMENT_GUIDE.md          # This file
│   ├── ARCHITECTURE.md
│   ├── SETUP_GUIDE.md
│   └── MULTI_DB_SETUP.md
│
├── scripts\                         # Utility scripts
│   ├── start_chatbot.bat            # Quick-launch the app
│   ├── setup_rbac.bat               # One-time RBAC setup helper
│   └── explore_db.bat               # Database explorer
│
├── tests\
│   └── test_anonymization.py
│
├── Dockerfile                       # Docker image build
├── docker-compose.yml               # Local Docker (with Ollama)
└── requirements.txt                 # Python dependencies
```

---

## 16. Quick-Start Checklist

Use this before going live or handing off to someone new.

**Environment:**
- [ ] Windows 11, 8+ GB RAM (or 4 GB if using Claude API)
- [ ] Python 3.11+ installed and on PATH
- [ ] Node.js 20+ installed (for React build)
- [ ] Git installed

**Setup:**
- [ ] Repo cloned from https://github.com/varunmundas-de-stack/convAI-multi-tenant-cubejs
- [ ] `venv\Scripts\activate` active
- [ ] `pip install -r requirements.txt` completed successfully
- [ ] React built: `cd frontend_react && npm install && npm run build`
- [ ] `python database\create_user_db.py` ran successfully
- [ ] `python database\create_multi_schema_demo.py` ran successfully
- [ ] `database\users.db` exists
- [ ] `database\cpg_multi_tenant.duckdb` exists

**LLM (choose one):**
- [ ] Ollama: `ollama pull llama3.2:3b` done and `ollama serve` is running
- [ ] Claude API: `USE_CLAUDE_API=true` and `ANTHROPIC_API_KEY` set

**Verification:**
- [ ] `python frontend\app_with_auth.py` starts without errors
- [ ] Browser opens `http://localhost:5000` and shows login page
- [ ] Login with `nestle_admin / admin123` succeeds
- [ ] Chat tab: `"What are total sales?"` returns a number
- [ ] Insights tab loads (wait 15 sec on first start)
- [ ] Dashboard tab loads with charts

---

*Last updated: February 2026*
