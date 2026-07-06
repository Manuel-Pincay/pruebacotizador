"""Verifica Python, dependencias y conexión MySQL antes de iniciar el ERP."""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

# import_name -> nombre en pip (solo si difiere)
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
        print(f"      {detail}")
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
        return _ok(".env encontrado")

    print("  [!] .env no encontrado (se usaran valores por defecto)")
    if example_path.exists():
        print("      Recomendado: copy .env.example .env")
    return CheckResult(True, ".env no encontrado (opcional)")


def _load_database_url() -> str:
    sys.path.insert(0, str(ROOT))
    from app.config.settings import settings

    return settings.database_url


def _parse_mysql_url(database_url: str) -> dict:
    if not database_url.startswith("mysql"):
        raise ValueError("DATABASE_URL debe ser MySQL (mysql+pymysql://...)")

    parsed = urlparse(database_url.replace("+pymysql", "", 1))
    port = parsed.port or 3306
    database = (parsed.path or "").lstrip("/").split("?")[0]
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": port,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": database,
    }


def _try_mysql_connect(params: dict) -> tuple[bool, str]:
    try:
        import pymysql
    except ImportError:
        return False, "pymysql no instalado"

    try:
        conn = pymysql.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            database=params["database"],
            connect_timeout=3,
            charset="utf8mb4",
        )
        conn.close()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _mysql_help(params: dict, error: str) -> str:
    host = params["host"]
    port = params["port"]
    db = params["database"]

    lines = [
        f"No se pudo conectar a MySQL en {host}:{port} (base: {db}).",
        "",
        "Verifique:",
        "  1. MySQL 8+ instalado y el servicio en ejecución",
        "  2. Usuario, contraseña y base en DATABASE_URL (.env)",
        f"  3. La base '{db}' existe (docs/mysql_setup.sql)",
        "",
        f"Detalle: {error}",
    ]
    return "\n      ".join(lines)


def check_mysql() -> CheckResult:
    try:
        database_url = _load_database_url()
    except Exception as exc:
        return _fail("No se pudo leer DATABASE_URL", str(exc))

    if not database_url.startswith("mysql"):
        return _fail(
            "DATABASE_URL no es MySQL",
            "Configure mysql+pymysql://usuario:clave@host:puerto/base?charset=utf8mb4",
        )

    params = _parse_mysql_url(database_url)
    connected, error = _try_mysql_connect(params)

    if connected:
        return _ok(
            f"MySQL conectado ({params['host']}:{params['port']}/{params['database']})",
        )

    return _fail("MySQL no disponible", _mysql_help(params, error))


def run_all_checks() -> int:
    _header("ERP - Verificacion de requisitos")

    checks = [
        check_python_version(),
        check_dependencies(),
        check_env_file(),
    ]

    if all(item.ok for item in checks):
        checks.append(check_mysql())
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
        print("Dependencias:  ejecute iniciar_servidor.bat o python scripts/bootstrap_environment.py")
        print("MySQL:         revise DATABASE_URL en .env y docs/mysql_setup.sql")
        print("=" * 60)
        return 1

    print("=" * 60)
    print("Todo listo. Iniciando servidor...")
    print("=" * 60)
    return 0


def main() -> int:
    return run_all_checks()


if __name__ == "__main__":
    raise SystemExit(main())
