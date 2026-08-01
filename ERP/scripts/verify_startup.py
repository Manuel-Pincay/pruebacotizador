"""Verifica Python, dependencias y MySQL antes de iniciar el ERP."""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PACKAGES: tuple[tuple[str, str], ...] = (
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "SQLAlchemy"),
    ("pymysql", "pymysql"),
    ("alembic", "alembic"),
    ("dotenv", "python-dotenv"),
    ("jinja2", "Jinja2"),
    ("passlib", "passlib"),
    ("bcrypt", "bcrypt"),
    ("openpyxl", "openpyxl"),
    ("reportlab", "reportlab"),
    ("PIL", "pillow"),
    ("cryptography", "cryptography"),
    ("itsdangerous", "itsdangerous"),
)

MIN_PYTHON = (3, 10)


@dataclass
class CheckResult:
    ok: bool
    title: str
    detail: str = ""


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)


def _fail(title: str, detail: str = "") -> CheckResult:
    print(f"  [X] {title}")
    if detail:
        for line in detail.splitlines():
            print(f"      {line}")
    return CheckResult(False, title, detail)


def _ok(title: str, detail: str = "") -> CheckResult:
    print(f"  [OK] {title}")
    if detail:
        print(f"       {detail}")
    return CheckResult(True, title, detail)


def check_python_version() -> CheckResult:
    version = sys.version_info[:3]
    label = f"{version[0]}.{version[1]}.{version[2]}"
    if version[:2] < MIN_PYTHON:
        return _fail(
            f"Python {label} (se requiere {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+)",
            "Instale Python 3.10 o superior desde https://www.python.org/downloads/",
        )
    return _ok(f"Python {label}")


def check_dependencies() -> CheckResult:
    missing: list[str] = []
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        unique = sorted(set(missing))
        return _fail(
            f"Faltan {len(unique)} paquete(s)",
            "Ejecute: pip install -r requirements.txt",
        )

    return _ok(f"{len(REQUIRED_PACKAGES)} dependencias principales")


def check_env_file() -> CheckResult:
    env_path = ROOT / ".env"
    example_path = ROOT / ".env.example"

    if env_path.exists():
        sys.path.insert(0, str(ROOT))
        from app.config.settings import settings

        if not (settings.database_url or "").strip():
            return _fail(
                "DATABASE_URL vacía en .env",
                "Configure mysql+pymysql://usuario:clave@127.0.0.1:3306/erp?charset=utf8mb4",
            )
        return _ok(".env encontrado")

    print("  [!] .env no encontrado")
    if example_path.exists():
        print("      Ejecute iniciar_servidor.bat para crearlo automaticamente")
    return _fail(
        ".env no encontrado",
        "Copie .env.example a .env o ejecute iniciar_servidor.bat",
    )


def check_and_prepare_mysql() -> CheckResult:
    from ensure_database import ensure_database

    ok, message = ensure_database(verbose=True)
    if ok:
        return _ok(message)
    return _fail("MySQL no disponible", message)


def run_all_checks() -> int:
    _header("ERP - Verificacion de requisitos")

    checks = [
        check_python_version(),
        check_dependencies(),
        check_env_file(),
    ]

    if all(item.ok for item in checks):
        checks.append(check_and_prepare_mysql())
    else:
        print("\n  [!] Se omitio la verificacion de MySQL hasta corregir lo anterior.")

    print()
    failed = [item for item in checks if not item.ok]

    if failed:
        print("=" * 60)
        print("INICIO BLOQUEADO - Corrija lo siguiente:")
        print("=" * 60)
        for item in failed:
            print(f"  - {item.title}")
            if item.detail:
                for line in item.detail.splitlines():
                    print(f"    {line}")
        print()
        print("Pasos sugeridos:")
        print("  1. Edite DATABASE_URL en ERP\\.env (usuario, clave, base)")
        print("  2. Verifique que MySQL este en ejecucion")
        print("  3. Vuelva a ejecutar iniciar_servidor.bat")
        print("=" * 60)
        return 1

    print("=" * 60)
    print("Todo listo. Iniciando servidor...")
    print("=" * 60)
    return 0


def main() -> int:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return run_all_checks()


if __name__ == "__main__":
    raise SystemExit(main())
