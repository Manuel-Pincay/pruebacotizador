#!/usr/bin/env python3
"""
Inicializa la base de datos del ERP:
  1. (Dev) MariaDB portable si aplica
  2. Migraciones Alembic
  3. Catálogos base de productos

Uso:
  python scripts/init_database.py
  python scripts/init_database.py --skip-portable
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


def ensure_portable_mysql() -> None:
    from app.config.settings import settings

    if not settings.uses_portable_mysql:
        return

    import importlib.util

    setup_path = ROOT / "scripts" / "setup_local_mysql.py"
    spec = importlib.util.spec_from_file_location("setup_local_mysql", setup_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if module.app_database_ready():
        log("MariaDB portable: ya activo (puerto 3307).")
        return

    log("MariaDB portable: iniciando...")
    if not module.ensure_running():
        raise RuntimeError("No se pudo iniciar MariaDB portable")


def run_alembic() -> None:
    log("Aplicando migraciones Alembic...")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        check=True,
    )


def seed_catalogs() -> None:
    from app.database import SessionLocal
    from app.services.catalog_seed import seed_product_catalogs

    db = SessionLocal()
    try:
        created = seed_product_catalogs(db)
        total = sum(created.values())
        if total:
            log(f"Catálogos base: {total} registros nuevos.")
        else:
            log("Catálogos base: ya existían.")
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializar base de datos ERP")
    parser.add_argument(
        "--skip-portable",
        action="store_true",
        help="No intentar iniciar MariaDB portable",
    )
    args = parser.parse_args()

    try:
        from app.config.settings import settings

        log(f"Entorno: {settings.app_env}")
        log(f"Base de datos: {settings.database_url.split('@')[-1]}")

        if not args.skip_portable:
            ensure_portable_mysql()

        run_alembic()
        seed_catalogs()

        from app.database import SessionLocal
        from app.services.user_bootstrap import ensure_admin_user

        db = SessionLocal()
        try:
            _, created = ensure_admin_user(db)
            if created:
                log("Usuario admin creado (admin / 123456).")
            else:
                log("Usuario admin ya existía.")
        finally:
            db.close()

        log("")
        log("Base de datos lista.")
        log("Inicia la app con: python run.py")
        log("Usuario inicial: admin / 123456 (se crea al arrancar)")
        return 0
    except subprocess.CalledProcessError as exc:
        log(f"ERROR Alembic: {exc}")
        return 1
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
