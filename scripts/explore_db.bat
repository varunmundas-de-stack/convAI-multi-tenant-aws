@echo off
echo ============================================================
echo CPG Database Explorer
echo ============================================================
echo.
echo Showing database metadata, row counts, and sample data...
echo.

cd %~dp0
python demos\explore_database.py

echo.
pause
