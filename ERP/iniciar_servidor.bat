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
    echo [1/3] Preparando Python...
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
    echo [1/3] Python: entorno virtual encontrado.
)

set "PYTHON=venv\Scripts\python.exe"

:: ── 2. Dependencias pip + .env ───────────────────────────────
echo [2/3] Verificando dependencias...
"%PYTHON%" scripts\bootstrap_environment.py
if errorlevel 1 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias.
    echo.
    pause
    exit /b 1
)

:: ── 3. Servidor (MySQL portable + verificacion + uvicorn) ─────
echo [3/3] Iniciando servidor...
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
