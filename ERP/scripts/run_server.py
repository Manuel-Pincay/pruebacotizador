"""Inicia el servidor ERP en modo desarrollo/pruebas."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.getenv("ERP_HOST", "0.0.0.0")
PORT = os.getenv("ERP_PORT", "8000")
OPEN_BROWSER = os.getenv("ERP_OPEN_BROWSER", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
STARTUP_CREDIT = "Desarrollado por Manuel Pincay"


def get_lan_ip() -> str | None:
    """IP en la red local (ej. 192.168.x.x) para acceder desde otros equipos."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def print_startup_banner() -> None:
    lan_ip = get_lan_ip()
    print("=" * 60)
    print("ERP - Servidor de pruebas")
    print(f"  En este equipo:  http://127.0.0.1:{PORT}")
    if lan_ip:
        print(f"  En la red (LAN): http://{lan_ip}:{PORT}")
    else:
        print("  En la red (LAN): (no detectada)")
    print("  Usuario: admin / Clave: 123456")
    print("  Detener: Ctrl+C")
    print("=" * 60)
    print(STARTUP_CREDIT)
    print("=" * 60)


def run_verification() -> None:
    verify_script = ROOT / "scripts" / "verify_startup.py"
    result = subprocess.run(
        [sys.executable, str(verify_script)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    os.chdir(ROOT)

    run_verification()

    print_startup_banner()

    if OPEN_BROWSER:
        webbrowser.open(f"http://127.0.0.1:{PORT}")

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

    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
