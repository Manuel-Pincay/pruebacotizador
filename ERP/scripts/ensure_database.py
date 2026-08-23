"""Crea la base MySQL si no existe y aplica migraciones Alembic."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_database_url() -> str:
    sys.path.insert(0, str(ROOT))
    from app.config.settings import settings

    url = (settings.database_url or "").strip()
    if not url:
        raise ValueError(
            "DATABASE_URL no está configurada. Edite el archivo .env en la carpeta ERP."
        )
    if not url.startswith("mysql"):
        raise ValueError(
            "DATABASE_URL debe ser MySQL, por ejemplo:\n"
            "  mysql+pymysql://usuario:clave@127.0.0.1:3306/erp?charset=utf8mb4"
        )
    return url


def parse_mysql_url(database_url: str) -> dict:
    parsed = urlparse(database_url.replace("+pymysql", "", 1))
    database = (parsed.path or "").lstrip("/").split("?")[0]
    if not database:
        raise ValueError("DATABASE_URL debe incluir el nombre de la base de datos.")
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": database,
    }


def _connect(params: dict, *, use_database: bool = True):
    import pymysql

    kwargs = {
        "host": params["host"],
        "port": params["port"],
        "user": params["user"],
        "password": params["password"],
        "connect_timeout": 8,
        "charset": "utf8mb4",
    }
    if use_database:
        kwargs["database"] = params["database"]
    return pymysql.connect(**kwargs)


def _mysql_error_code(exc: Exception) -> int | None:
    args = getattr(exc, "args", None)
    if args and isinstance(args[0], int):
        return args[0]
    return None


def create_database(params: dict) -> None:
    db_name = params["database"]
    if not re.match(r"^[A-Za-z0-9_]+$", db_name):
        raise ValueError(f"Nombre de base de datos no válido: {db_name}")

    conn = _connect(params, use_database=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _get_alembic_version(params: dict) -> str | None:
    try:
        conn = _connect(params, use_database=True)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _has_core_tables(params: dict) -> bool:
    try:
        conn = _connect(params, use_database=True)
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'quotations'")
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False


def run_migrations(params: dict) -> None:
    version = _get_alembic_version(params)
    if version is None and _has_core_tables(params):
        _log("  [!] Tablas ERP detectadas sin registro Alembic. Sincronizando historial...")
        stamp = subprocess.run(
            [sys.executable, "-m", "alembic", "stamp", "003_quotation_enhancements"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if stamp.returncode != 0:
            detail = (stamp.stderr or stamp.stdout or "").strip()
            raise RuntimeError(f"No se pudo sincronizar Alembic:\n{detail}")

    _log("  → Aplicando migraciones pendientes (alembic upgrade head)...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Error desconocido").strip()
        # Instalación ya migrada: ignorar duplicados conocidos
        if "Duplicate column name 'company_icon'" in detail or "already exists" in detail.lower():
            _log("  [!] Esquema ya actualizado; sincronizando version Alembic...")
            stamp = subprocess.run(
                [sys.executable, "-m", "alembic", "stamp", "head"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if stamp.returncode == 0:
                return
        raise RuntimeError(f"No se pudieron aplicar migraciones Alembic:\n{detail}")

    new_version = _get_alembic_version(params) or "head"
    if version and version != new_version:
        _log(f"  [OK] Migraciones aplicadas: {version} → {new_version}")
    else:
        _log(f"  [OK] Esquema al día (revisión: {new_version})")


def ensure_database(*, verbose: bool = True) -> tuple[bool, str]:
    """
    Garantiza que la base exista y esté migrada.
    Retorna (ok, mensaje).
    """
    try:
        database_url = load_database_url()
        params = parse_mysql_url(database_url)
    except ValueError as exc:
        return False, str(exc)

    if not params["user"]:
        return False, "DATABASE_URL debe incluir usuario y contraseña de MySQL."

    try:
        conn = _connect(params, use_database=True)
        conn.close()
        if verbose:
            _log(f"  [OK] Base de datos '{params['database']}' encontrada")
        run_migrations(params)
        return True, f"MySQL listo ({params['host']}:{params['port']}/{params['database']})"

    except Exception as exc:
        code = _mysql_error_code(exc)
        err_text = str(exc)

        if code == 1049 or "Unknown database" in err_text:
            if verbose:
                _log(f"  [!] La base '{params['database']}' no existe. Creándola...")
            try:
                create_database(params)
                if verbose:
                    _log(f"  [OK] Base '{params['database']}' creada")
                run_migrations(params)
                return True, f"Base '{params['database']}' creada y migrada"
            except Exception as create_exc:
                return False, f"No se pudo crear la base de datos: {create_exc}"

        if code == 1045 or "Access denied" in err_text:
            return False, (
                "Acceso denegado a MySQL. Verifique usuario y contraseña en DATABASE_URL (.env).\n"
                f"  Host: {params['host']}:{params['port']}\n"
                f"  Usuario: {params['user']}\n"
                f"  Base: {params['database']}"
            )

        if code == 2003 or "Can't connect" in err_text or "Connection refused" in err_text:
            return False, (
                "No se pudo conectar al servidor MySQL.\n"
                "  1. Verifique que MySQL 8+ esté instalado\n"
                "  2. Inicie el servicio MySQL (Windows: servicios.msc → MySQL80)\n"
                f"  3. Host configurado: {params['host']}:{params['port']}"
            )

        return False, f"Error MySQL: {err_text}"


def main() -> int:
    print("=" * 60)
    print("ERP - Base de datos MySQL")
    print("=" * 60)
    ok, message = ensure_database(verbose=True)
    print()
    if ok:
        print(f"  [OK] {message}")
        print("=" * 60)
        return 0
    print(f"  [X] {message}")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
