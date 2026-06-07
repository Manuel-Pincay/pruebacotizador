import importlib.util
import socket
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
SETUP_MYSQL = ROOT / "scripts" / "setup_local_mysql.py"


def _load_setup_mysql():
    spec = importlib.util.spec_from_file_location("setup_local_mysql", SETUP_MYSQL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_local_database() -> None:
    """Arranca MariaDB portable en desarrollo si la URL apunta al puerto 3307."""
    from app.config.settings import settings

    if not settings.uses_portable_mysql:
        return

    setup = _load_setup_mysql()
    if setup.app_database_ready():
        return

    print("\nMariaDB no está activo. Iniciando...\n")
    if not setup.ensure_running():
        print(
            "No se pudo iniciar MariaDB. Ejecuta manualmente:\n"
            "  python scripts/setup_local_mysql.py\n",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    ensure_local_database()

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("\n")
    print("=" * 50)
    print("ERP disponible en:\n")
    print(f"http://{local_ip}:8000")
    print(f"http://localhost:8000")
    print("=" * 50)
    print("\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
