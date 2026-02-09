# 🚀 Complete Setup Guide - CPG Conversational AI with RBAC

**From Zero to Running - Comprehensive Windows Setup Guide**

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Feature Configuration](#feature-configuration)
5. [Testing the System](#testing-the-system)
6. [Troubleshooting](#troubleshooting)
7. [Production Deployment](#production-deployment)

---

## ✅ Prerequisites

### **System Requirements**

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 | Windows 11 |
| **RAM** | 4GB | 8GB+ |
| **Disk Space** | 1GB | 2GB+ |
| **Python** | 3.10+ | 3.12+ |
| **Internet** | Required for setup | - |

### **Required Software**

#### **1. Python 3.12+**
- **Download**: https://www.python.org/downloads/
- **Installation Tips**:
  - ✅ **CHECK** "Add Python to PATH" during installation
  - ✅ **CHECK** "Install pip"
  - Click "Customize installation" → Check "Add Python to environment variables"

**Verify Installation**:
```bash
python --version
# Expected: Python 3.12.x

pip --version
# Expected: pip 24.x from C:\Users\...
```

#### **2. Git (Optional but Recommended)**
- **Download**: https://git-scm.com/downloads
- **Installation**: Use default settings
- **Verify**:
  ```bash
  git --version
  # Expected: git version 2.x.x
  ```

#### **3. Text Editor (Optional)**
- **VS Code**: https://code.visualstudio.com/
- **Notepad++**: https://notepad-plus-plus.org/
- **Or use:** Windows Notepad (built-in)

---

## ⚡ Quick Start (5 Minutes)

**For experienced users who want to get running immediately:**

### **Windows PowerShell/Command Prompt**

```bash
# 1. Navigate to your projects folder
cd D:\
mkdir projects
cd projects

# 2. Clone repository
git clone https://github.com/varunmundas-de-stack/Conve-AI-Project-RelDB-Only.git
cd Conve-AI-Project-RelDB-Only

# 3. Install dependencies (one command)
pip install duckdb ollama pydantic pyyaml rich python-dateutil flask flask-login werkzeug bcrypt

# 4. Setup databases
python database/create_user_db.py
python database/create_multi_schema_demo.py

# 5. Start server
python frontend/app_with_auth.py

# 6. Open browser and go to:
# http://localhost:5000
# Login: nestle_analyst / nestle123
```

**Done!** 🎉 Skip to [Testing the System](#testing-the-system)

---

## 📦 Step-by-Step Setup

### **Step 1: Prepare Your System**

#### **1.1 Open PowerShell or Command Prompt**

**Option A: PowerShell (Recommended)**
- Press `Win + X`
- Select "Windows PowerShell" or "Terminal"

**Option B: Command Prompt**
- Press `Win + R`
- Type `cmd` and press Enter

#### **1.2 Check Python Installation**

```bash
python --version
```

**Expected Output**: `Python 3.12.x` or `Python 3.10.x` or higher

**If Python is not found**:
1. Download from https://www.python.org/downloads/
2. Run installer
3. **CRITICAL**: Check "Add Python to PATH"
4. Click "Install Now"
5. Restart your terminal

---

### **Step 2: Download the Project**

#### **Option A: Using Git (Recommended)**

```bash
# Navigate to where you want to install
cd D:\
mkdir projects
cd projects

# Clone the repository
git clone https://github.com/varunmundas-de-stack/Conve-AI-Project-RelDB-Only.git

# Enter the project folder
cd Conve-AI-Project-RelDB-Only

# Verify you're in the right place
dir
# You should see: database/, frontend/, semantic_layer/, etc.
```

#### **Option B: Download ZIP (If no Git)**

1. Open browser: https://github.com/varunmundas-de-stack/Conve-AI-Project-RelDB-Only
2. Click green **"Code"** button
3. Click **"Download ZIP"**
4. Extract ZIP to `D:\projects\Conve-AI-Project-RelDB-Only`
5. Open PowerShell in that folder:
   - Navigate to folder in File Explorer
   - Hold `Shift` + Right-click in folder
   - Select "Open PowerShell window here"

---

### **Step 3: Install Python Dependencies**

#### **3.1 Core Dependencies**

```bash
# Install all required packages
pip install duckdb ollama pydantic pyyaml rich python-dateutil flask flask-login werkzeug bcrypt
```

**Expected Output**:
```
Collecting duckdb
  Downloading duckdb-x.x.x-cp312-...
Successfully installed duckdb-x.x.x ollama-x.x.x ...
```

#### **3.2 Verify Installation**

```bash
python -c "import duckdb; import flask; import pydantic; print('All packages installed successfully!')"
```

**Expected Output**: `All packages installed successfully!`

**If you get errors**, install packages individually:

```bash
pip install duckdb
pip install ollama
pip install pydantic
pip install pyyaml
pip install rich
pip install python-dateutil
pip install flask
pip install flask-login
pip install werkzeug
pip install bcrypt
```

---

### **Step 4: Create Databases**

#### **4.1 Create User Authentication Database**

```bash
python database/create_user_db.py
```

**Expected Output**:
```
Creating user authentication database...
Created user: nestle_analyst (password: nestle123)
Created user: unilever_analyst (password: unilever123)
Created user: itc_analyst (password: itc123)
User database created successfully: database/users.db
```

**Verify**:
```bash
dir database\users.db
# Should show: users.db with file size
```

#### **4.2 Create Multi-Tenant Analytics Database**

```bash
python database/create_multi_schema_demo.py
```

**Expected Output**:
```
Creating multi-tenant CPG database...
Creating schema: client_nestle
Creating schema: client_unilever
Creating schema: client_itc
Populating data...
Database created successfully: database/cpg_multi_tenant.duckdb
```

**Verify**:
```bash
dir database\cpg_multi_tenant.duckdb
# Should show: cpg_multi_tenant.duckdb (~10-50 MB)
```

---

### **Step 5: Verify Project Structure**

```bash
# Check that everything is in place
dir

# You should see:
# - database/ (folder)
# - frontend/ (folder)
# - semantic_layer/ (folder)
# - llm/ (folder)
# - security/ (folder)
# - query_engine/ (folder)
# - README.md
# - ARCHITECTURE.md
# - SETUP_GUIDE.md (this file)
```

---

### **Step 6: Start the Application**

```bash
python frontend/app_with_auth.py
```

**Expected Output**:
```
 * Serving Flask app 'app_with_auth'
 * Debug mode: on
WARNING: This is a development server.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

**🎉 Success!** The server is now running.

**⚠️ Important**:
- Keep this terminal window open
- Do NOT close it while using the application
- To stop the server: Press `Ctrl+C`

---

### **Step 7: Access the Application**

1. **Open your web browser** (Chrome, Firefox, Edge)
2. **Navigate to**: http://localhost:5000
3. **You should see**: Login page

---

## 🔧 Feature Configuration

### **Enable Schema Anonymization (Recommended for Production)**

Schema anonymization protects your database metadata when using external LLMs like Claude API.

#### **Option 1: Environment Variable**

**PowerShell**:
```powershell
$env:ANONYMIZE_SCHEMA="true"
python frontend/app_with_auth.py
```

**Command Prompt**:
```cmd
set ANONYMIZE_SCHEMA=true
python frontend/app_with_auth.py
```

#### **Option 2: Create .env File**

Create file `.env` in project root:
```bash
ANONYMIZE_SCHEMA=true
```

Then start the application normally.

#### **What Anonymization Does**:
- ✅ Protects metric names: `secondary_sales_value` → `value_metric_001`
- ✅ Protects dimension names: `brand_name` → `product_dimension_001`
- ✅ External LLM sees only generic names
- ✅ Real schema never exposed to external services

**See**: [ARCHITECTURE.md - Schema Anonymization](ARCHITECTURE.md#-schema-anonymization-security-enhancement)

---

### **Use External LLM (Claude API)**

By default, the system uses local Ollama. To use Claude API:

#### **Step 1: Get API Key**
1. Sign up at https://console.anthropic.com/
2. Create an API key
3. Copy the key (starts with `sk-ant-...`)

#### **Step 2: Set Environment Variables**

**PowerShell**:
```powershell
$env:USE_CLAUDE_API="true"
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
$env:ANONYMIZE_SCHEMA="true"
python frontend/app_with_auth.py
```

**Command Prompt**:
```cmd
set USE_CLAUDE_API=true
set ANTHROPIC_API_KEY=sk-ant-your-key-here
set ANONYMIZE_SCHEMA=true
python frontend/app_with_auth.py
```

**⚠️ Security**: Always enable `ANONYMIZE_SCHEMA=true` when using external LLMs!

---

## 🧪 Testing the System

### **Test 1: Login and Authentication**

1. Open browser: http://localhost:5000
2. **Login as Nestlé analyst**:
   - Username: `nestle_analyst`
   - Password: `nestle123`
3. **Expected**: Redirect to chat interface with "Welcome, nestle_analyst (Nestlé India)"

### **Test 2: Run Sample Queries**

Try these queries (one at a time):

#### **Query 1: Simple Aggregation**
```
Show total sales value
```
**Expected**: Single number showing total sales

#### **Query 2: Grouping by Brand**
```
Show sales by brand
```
**Expected**: Table with brand names and sales values

#### **Query 3: Top N Ranking**
```
Show top 5 brands by sales value
```
**Expected**: Table with 5 brands, sorted by sales (highest first)

#### **Query 4: Time-based Query**
```
Show sales by week for last 4 weeks
```
**Expected**: Table with week numbers and sales values

#### **Query 5: Multi-dimensional**
```
Show sales by brand and state
```
**Expected**: Table with brand, state, and sales columns

### **Test 3: Multi-Client Isolation**

1. **Logout** (click Logout button)
2. **Login as ITC analyst**:
   - Username: `itc_analyst`
   - Password: `itc123`
3. **Try same query**: "Show sales by brand"
4. **Expected**: Different data (ITC's data, not Nestlé's)

### **Test 4: Schema Isolation Verification**

**As Nestlé user**, try:
```
Show sales by brand
```
**Result**: Sees Nestlé brands (Maggi, KitKat, etc.)

**As ITC user**, try:
```
Show sales by brand
```
**Result**: Sees ITC brands (different from Nestlé)

**Verification**: No cross-client data leakage! ✅

---

## 🔍 Troubleshooting

### **Issue 1: "Python not recognized"**

**Error**:
```
'python' is not recognized as an internal or external command
```

**Solution**:
1. Reinstall Python
2. **CHECK** "Add Python to PATH" during installation
3. Restart terminal
4. Try: `py` instead of `python` (Windows alias)

---

### **Issue 2: "ModuleNotFoundError: No module named 'xyz'"**

**Error**:
```
ModuleNotFoundError: No module named 'duckdb'
```

**Solution**:
```bash
pip install duckdb
# Or install all dependencies again:
pip install duckdb ollama pydantic pyyaml rich python-dateutil flask flask-login werkzeug bcrypt
```

---

### **Issue 3: "Address already in use" (Port 5000 occupied)**

**Error**:
```
OSError: [Errno 48] Address already in use
```

**Solution**:

**Option A: Change Port**
Edit `frontend/app_with_auth.py`, line at bottom:
```python
# Change from:
app.run(debug=True, port=5000)
# To:
app.run(debug=True, port=5001)
```

Then access: http://localhost:5001

**Option B: Kill Process on Port 5000**
```bash
# Find process
netstat -ano | findstr :5000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

---

### **Issue 4: Database File Not Found**

**Error**:
```
FileNotFoundError: database/users.db not found
```

**Solution**:
```bash
# Recreate databases
python database/create_user_db.py
python database/create_multi_schema_demo.py

# Verify files exist
dir database\users.db
dir database\cpg_multi_tenant.duckdb
```

---

### **Issue 5: Login Fails / Wrong Password**

**Default Credentials**:
| Username | Password | Client |
|----------|----------|--------|
| `nestle_analyst` | `nestle123` | Nestlé India |
| `unilever_analyst` | `unilever123` | Hindustan Unilever |
| `itc_analyst` | `itc123` | ITC Limited |

**To reset passwords**:
```bash
# Delete and recreate user database
del database\users.db
python database/create_user_db.py
```

---

### **Issue 6: Ollama Not Installed (If Using Local LLM)**

**Error**:
```
Connection refused: Ollama server not running
```

**Solution**:

**Option A: Install Ollama**
1. Download: https://ollama.ai/download
2. Install for Windows
3. Start Ollama
4. Pull model: `ollama pull llama3.2:3b`

**Option B: Use Claude API Instead**
```bash
set USE_CLAUDE_API=true
set ANTHROPIC_API_KEY=your-key-here
python frontend/app_with_auth.py
```

---

### **Issue 7: Browser Shows "Connection Refused"**

**Checklist**:
1. ✅ Is the Flask server running? (Check terminal)
2. ✅ Did you see "Running on http://127.0.0.1:5000"?
3. ✅ Are you using the correct URL? http://localhost:5000
4. ✅ Try: http://127.0.0.1:5000 instead

---

### **Issue 8: Slow Query Performance**

**Possible Causes**:
1. Large dataset in database
2. External LLM API latency
3. No indexes on database

**Solutions**:
- Use local Ollama instead of external LLM
- Limit query results: "Show top 10 brands"
- Check internet connection (for external LLM)

---

### **Issue 9: Windows Firewall Blocking**

**Symptom**: Can't access http://localhost:5000

**Solution**:
1. Windows Defender Firewall → Allow an app
2. Find Python → Check "Private" and "Public"
3. Click OK
4. Restart Flask server

---

## 🚀 Production Deployment

### **1. Security Checklist**

Before deploying to production:

- [ ] Change default passwords in `database/create_user_db.py`
- [ ] Set strong `SECRET_KEY` in Flask app
- [ ] Enable HTTPS/TLS
- [ ] Enable `ANONYMIZE_SCHEMA=true`
- [ ] Use production WSGI server (Waitress/Gunicorn)
- [ ] Set up database backups
- [ ] Enable audit logging
- [ ] Configure firewalls
- [ ] Use environment variables for secrets (not hardcoded)

### **2. Use Production Server (Waitress)**

**Install Waitress**:
```bash
pip install waitress
```

**Create production startup script** `start_production.py`:
```python
from waitress import serve
from frontend.app_with_auth import app

# Production configuration
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = 'change-this-to-random-secret-key'

# Serve on all interfaces, port 8080
serve(app, host='0.0.0.0', port=8080, threads=4)
```

**Start production server**:
```bash
python start_production.py
```

### **3. Environment Variables for Production**

Create `.env` file:
```bash
# Security
SECRET_KEY=your-super-secret-key-here-change-this
FLASK_ENV=production
DEBUG=False

# Anonymization (required for external LLM)
ANONYMIZE_SCHEMA=true

# LLM Configuration
USE_CLAUDE_API=true
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Database
DATABASE_PATH=database/cpg_multi_tenant.duckdb
USER_DB_PATH=database/users.db

# Server
HOST=0.0.0.0
PORT=8080
```

### **4. Backup Strategy**

**Backup databases**:
```bash
# Create backup folder
mkdir backups

# Backup daily
xcopy database\*.db backups\ /Y
xcopy database\*.duckdb backups\ /Y
```

**Automated backup (Windows Task Scheduler)**:
1. Create `backup.bat`:
   ```batch
   @echo off
   xcopy D:\projects\Conve-AI-Project-RelDB-Only\database\*.db D:\backups\%date:~-4,4%%date:~-10,2%%date:~-7,2%\ /Y
   xcopy D:\projects\Conve-AI-Project-RelDB-Only\database\*.duckdb D:\backups\%date:~-4,4%%date:~-10,2%%date:~-7,2%\ /Y
   ```
2. Schedule in Task Scheduler to run daily

### **5. Monitoring**

**Enable logging** in Flask app:
```python
import logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 📚 Additional Resources

### **Documentation**

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Quick overview and features |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Complete technical architecture |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | This file - setup instructions |

### **Supplementary Documentation** (in `docs/` folder)

| Document | Purpose |
|----------|---------|
| [docs/ANONYMIZATION_GUIDE.md](docs/ANONYMIZATION_GUIDE.md) | Complete anonymization guide |
| [docs/supplementary/](docs/supplementary/) | Additional examples and references |

### **Key Features**

- ✅ Multi-tenant RBAC with complete data isolation
- ✅ Schema anonymization for external LLM protection
- ✅ AST-based SQL generation (injection-proof)
- ✅ Natural language to SQL conversion
- ✅ Audit trail for all queries

### **Getting Help**

1. Check [Troubleshooting](#troubleshooting) section above
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
3. Check logs: `app.log` (if enabled)
4. GitHub Issues: https://github.com/varunmundas-de-stack/Conve-AI-Project-RelDB-Only/issues

---

## ✅ Quick Reference

### **Start Application**
```bash
cd D:\projects\Conve-AI-Project-RelDB-Only
python frontend/app_with_auth.py
```

### **Access Application**
```
http://localhost:5000
```

### **Default Users**
- `nestle_analyst` / `nestle123`
- `unilever_analyst` / `unilever123`
- `itc_analyst` / `itc123`

### **Stop Application**
Press `Ctrl+C` in terminal

### **Enable Anonymization**
```bash
set ANONYMIZE_SCHEMA=true
```

### **Use External LLM**
```bash
set USE_CLAUDE_API=true
set ANTHROPIC_API_KEY=your-key
```

---

**🎉 You're all set! The system is ready to use.**

For technical architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md)
