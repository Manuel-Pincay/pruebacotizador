@echo off
REM Backup MySQL del ERP. Programar en Windows Task Scheduler (diario 2:00 AM).
cd /d "%~dp0.."
call .venv\Scripts\activate.bat 2>nul
python -c "from app.services.backup_service import create_mysql_backup; p=create_mysql_backup(); print('OK', p)"
if errorlevel 1 (
  echo ERROR al crear backup
  exit /b 1
)
exit /b 0
