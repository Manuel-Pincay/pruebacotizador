"""Prepara el entorno ERP: venv, dependencias pip y archivo .env."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

REQUIRED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pymysql",
    "alembic",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def header(title: str) -> None:
    log("")
    log("=" * 60)
    log(title)
    log("=" * 60)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    log(f"  >> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(ROOT), check=check)


def python_exe() -> Path:
    if VENV_PYTHON.exists():
        return VENV_PYTHON
    if sys.version_info >= (3, 10):
        return Path(sys.executable)
    raise SystemExit(
        "Python 3.10+ no disponible. Ejecute primero: scripts\\ensure_python.ps1"
    )


def dependencies_ok(python: Path) -> bool:
    for name in REQUIRED_IMPORTS:
        result = run(
            [str(python), "-c", f"import {name}"],
            check=False,
        )
        if result.returncode != 0:
            return False
    return True


def install_dependencies(python: Path) -> None:
    log("")
    log("  Instalando dependencias Python (primera vez puede tardar varios minutos)...")
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=False)
    run([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        log("  [OK] .env encontrado")
        return

    if ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        log("  [OK] .env creado desde .env.example")
        return

    log("  [!] .env.example no encontrado; se usaran valores por defecto")


def main() -> int:
    header("ERP - Preparando entorno")

    python = python_exe()
    log(f"  Python: {python}")

    if not REQUIREMENTS.exists():
        log("  [X] No se encontro requirements.txt")
        return 1

    if not dependencies_ok(python):
        try:
            install_dependencies(python)
        except subprocess.CalledProcessError as exc:
            log(f"  [X] Error instalando dependencias: {exc}")
            log("  Verifique conexion a internet e intente de nuevo.")
            return 1
    else:
        log("  [OK] Dependencias Python instaladas")

    ensure_env_file()

    log("")
    log("=" * 60)
    log("Entorno listo.")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
