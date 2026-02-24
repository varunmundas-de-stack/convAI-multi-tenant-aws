@echo off
echo ============================================================
echo RBAC Setup for Conv-AI Multi-Client System
echo ============================================================
echo.

echo Step 1: Installing Python dependencies...
pip install flask-login werkzeug bcrypt

echo.
echo Step 2: Creating user database...
python database\create_user_db.py

echo.
echo Step 3: Creating multi-schema database...
python database\create_multi_schema_demo.py

echo.
echo Step 4: Creating client configs...
if not exist "semantic_layer\configs" mkdir semantic_layer\configs
copy semantic_layer\config_cpg.yaml semantic_layer\configs\client_nestle.yaml

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo Sample users created:
echo   - nestle_admin / nestle123
echo   - unilever_admin / unilever123
echo   - itc_admin / itc123
echo.
echo To start the authenticated app:
echo   python frontend\app_with_auth.py
echo.
echo Then open: http://localhost:5000
echo ============================================================
pause
