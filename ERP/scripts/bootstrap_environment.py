"""Prepara el entorno ERP: venv, dependencias pip, .env y claves."""
from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
SRI_SIGNER_DIR = ROOT / "scripts" / "sri-signer"

REQUIRED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pymysql",
    "alembic",
    "cryptography",
    "dotenv",
    "requests",
    "httpx",
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


def _upsert_env_line(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    return content.rstrip() + "\n" + line + "\n"


def ensure_env_file() -> None:
    created = False
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
            log("  [OK] .env creado desde .env.example")
            created = True
        else:
            log("  [!] .env.example no encontrado")
            return
    else:
        log("  [OK] .env encontrado")

    content = ENV_FILE.read_text(encoding="utf-8")
    updated = False

    if re.search(r"^ERP_ENCRYPTION_KEY=\s*$", content, re.MULTILINE) or (
        created and "ERP_ENCRYPTION_KEY=" in content
    ):
        key = secrets.token_hex(32)
        content = _upsert_env_line(content, "ERP_ENCRYPTION_KEY", key)
        updated = True
        log("  [OK] ERP_ENCRYPTION_KEY generada en .env")

    if updated:
        ENV_FILE.write_text(content, encoding="utf-8")

    if created:
        log("  [!] Revise DATABASE_URL en .env (usuario, clave y nombre de base)")


def ensure_sri_signer() -> None:
    package_json = SRI_SIGNER_DIR / "package.json"
    node_modules = SRI_SIGNER_DIR / "node_modules"
    if not package_json.exists():
        return
    if node_modules.exists():
        log("  [OK] Firmador SRI (Node) listo")
        return

    npm = shutil.which("npm")
    if not npm:
        log("  [!] Node.js/npm no encontrado — facturación SRI requerirá npm install en scripts/sri-signer")
        return

    log("  Instalando firmador SRI (npm)...")
    result = subprocess.run(
        [npm, "install"],
        cwd=str(SRI_SIGNER_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        log("  [OK] Firmador SRI instalado")
    else:
        log("  [!] No se pudo instalar firmador SRI (npm install falló)")


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
    ensure_sri_signer()

    log("")
    log("=" * 60)
    log("Entorno listo.")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
