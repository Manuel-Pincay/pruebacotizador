@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ERP - Servidor de pruebas

echo.
echo ============================================================
echo   ERP - Iniciando (instala lo necesario automaticamente)
echo ============================================================
echo.

set "PYTHONIOENCODING=utf-8"
set "ERP_OPEN_BROWSER=1"
set "ERP_HOST=0.0.0.0"

:: ── 1. Python + entorno virtual ──────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo [1/4] Preparando Python...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ensure_python.ps1"
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo instalar Python automaticamente.
        echo Verifique conexion a internet e intente de nuevo.
        echo.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Python: entorno virtual encontrado.
)

set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

:: ── 2. Dependencias pip + .env + firmador SRI ─────────────────
echo [2/4] Verificando dependencias y archivo .env...
"%PYTHON%" scripts\bootstrap_environment.py
if errorlevel 1 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias.
    echo.
    pause
    exit /b 1
)

:: ── 3. Base de datos MySQL (crear si no existe + migraciones) ─
echo [3/4] Preparando base de datos MySQL...
"%PYTHON%" scripts\ensure_database.py
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo preparar MySQL.
    echo Revise DATABASE_URL en .env ^(usuario, clave, host, base^).
    echo Ejemplo: mysql+pymysql://admin:admin123@127.0.0.1:3306/erp?charset=utf8mb4
    echo.
    pause
    exit /b 1
)

:: ── 4. Servidor (uvicorn) ─────────────────────────────────────
echo [4/4] Iniciando servidor...
echo.
"%PYTHON%" scripts\run_server.py

if errorlevel 1 (
    echo.
    echo El servidor no pudo iniciarse.
    echo Diagnostico: "%PYTHON%" scripts\verify_startup.py
    echo.
    pause
)

endlocal
