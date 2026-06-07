#!/usr/bin/env python3
"""
Reinicia la base de datos de DESARROLLO (borra tablas y vuelve a crear).

Solo permitido con ERP_ENV=development.

Uso:
  python scripts/reset_dev_database.py
  python scripts/reset_dev_database.py --yes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(msg, flush=True)


def recreate_database() -> None:
    from urllib.parse import urlparse

    from sqlalchemy import create_engine, text

    from app.config.settings import settings

    parsed = urlparse(settings.database_url.replace("+pymysql", "", 1))
    db_name = (parsed.path or "/erp").lstrip("/").split("?")[0]
    server_url = settings.database_url.rsplit("/", 1)[0] + "/"

    engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{db_name}`"))
        conn.execute(
            text(
                f"CREATE DATABASE `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )

    log(f"Base `{db_name}` recreada.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset BD desarrollo ERP")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirmar sin preguntar",
    )
    args = parser.parse_args()

    from app.config.settings import settings

    if settings.is_production:
        log("ERROR: reset_dev_database solo está permitido en desarrollo.")
        return 1

    if settings.uses_portable_mysql:
        import importlib.util

        setup_path = ROOT / "scripts" / "setup_local_mysql.py"
        spec = importlib.util.spec_from_file_location("setup_local_mysql", setup_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not module.app_database_ready() and not module.ensure_running():
            log("ERROR: MariaDB portable no disponible.")
            return 1

    if not args.yes:
        log("Se eliminarán TODAS las tablas y datos del ERP en esta base.")
        log(f"URL: {settings.database_url.split('@')[-1]}")
        confirm = input("Escriba 'si' para continuar: ").strip().lower()
        if confirm not in {"si", "sí", "yes"}:
            log("Cancelado.")
            return 0

    try:
        recreate_database()
        log("Aplicando migraciones...")
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(ROOT),
            check=True,
        )

        from app.database import SessionLocal
        from app.services.catalog_seed import seed_product_catalogs

        db = SessionLocal()
        try:
            created = seed_product_catalogs(db)
            log(f"Catálogos base: {sum(created.values())} registros.")
        finally:
            db.close()

        log("Reset completado. Reinicia la app (python run.py) para recrear admin.")
        return 0
    except subprocess.CalledProcessError as exc:
        log(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
