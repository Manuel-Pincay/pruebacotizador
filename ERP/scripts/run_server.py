"""Inicia el servidor ERP en modo desarrollo/pruebas."""
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.getenv("ERP_HOST", "127.0.0.1")
PORT = os.getenv("ERP_PORT", "8000")
OPEN_BROWSER = os.getenv("ERP_OPEN_BROWSER", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}


def main() -> int:
    os.chdir(ROOT)

    if OPEN_BROWSER:
        webbrowser.open(f"http://{HOST}:{PORT}")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        HOST,
        "--port",
        PORT,
    ]

    print("=" * 60)
    print("ERP - Servidor de pruebas")
    print(f"URL: http://{HOST}:{PORT}")
    print("Detener: Ctrl+C")
    print("=" * 60)

    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
