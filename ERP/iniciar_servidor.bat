@echo off
setlocal
cd /d "%~dp0"
title ERP - Servidor de pruebas

if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

echo.
echo ========================================
echo   ERP - Iniciando servidor de pruebas
echo   URL: http://127.0.0.1:8000
echo   Usuario: admin / Clave: 123456
echo ========================================
echo.

set PYTHONIOENCODING=utf-8
set ERP_OPEN_BROWSER=1

"%PYTHON%" scripts\run_server.py

if errorlevel 1 (
    echo.
    echo El servidor no pudo iniciarse.
    echo Verifique que Python y las dependencias esten instaladas:
    echo   pip install -r requirements.txt
    echo.
    pause
)

endlocal
