#!/usr/bin/env python3
"""
Migración segura SQLite → MySQL preservando IDs y relaciones.

Uso:
    python scripts/migrate_sqlite_to_mysql.py \\
        --mysql-url mysql+pymysql://erp_user:pass@127.0.0.1:3306/erp?charset=utf8mb4

    python scripts/migrate_sqlite_to_mysql.py --mysql-url ... --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SQLITE = ROOT / "database" / "innova.db"
LOG_DIR = ROOT / "logs"

MIGRATION_TABLES = [
    "company_config",
    "users",
    "clients",
    "product_categories",
    "product_colors",
    "product_materials",
    "product_themes",
    "product_thicknesses",
    "measurement_units",
    "products",
    "quotations",
    "quotation_items",
    "production_orders",
    "shipments",
    "inventory_movements",
    "activity_logs",
]

NULLABLE_FK_COLUMNS = {
    "quotation_items": {"product_id"},
    "quotations": {"client_id"},
    "production_orders": {"quotation_id"},
    "shipments": {"quotation_id"},
    "inventory_movements": {"product_id"},
}


def log(message: str, log_file: Path | None = None) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(line)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def normalize_row(table: str, row: dict) -> dict:
    cleaned = dict(row)
    nullable_fks = NULLABLE_FK_COLUMNS.get(table, set())
    for key, value in list(cleaned.items()):
        if value == "" and key in nullable_fks:
            cleaned[key] = None
    return cleaned


def fetch_sqlite_rows(engine: Engine, table: str) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table} ORDER BY id"))
        return [dict(row._mapping) for row in result]


def mysql_table_empty(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
    return count == 0


def reset_auto_increment(engine: Engine, table: str) -> None:
    with engine.connect() as conn:
        max_id = conn.execute(text(f"SELECT MAX(id) FROM `{table}`")).scalar()
        next_id = (max_id or 0) + 1
        conn.execute(text(f"ALTER TABLE `{table}` AUTO_INCREMENT = {next_id}"))
        conn.commit()


def run_alembic_upgrade(mysql_url: str) -> None:
    os.environ["DATABASE_URL"] = mysql_url
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)
    command.upgrade(alembic_cfg, "head")


def migrate_table(
    sqlite_engine: Engine,
    mysql_engine: Engine | None,
    table: str,
    dry_run: bool,
    log_file: Path | None,
) -> int:
    rows = fetch_sqlite_rows(sqlite_engine, table)
    if dry_run:
        log(f"  {table}: {len(rows)} filas (dry-run)", log_file)
        return len(rows)

    if not rows:
        log(f"  {table}: 0 filas", log_file)
        return 0

    metadata = MetaData()
    metadata.reflect(bind=mysql_engine, only=[table])
    mysql_table = metadata.tables[table]

    with mysql_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for row in rows:
            payload = normalize_row(table, row)
            conn.execute(mysql_table.insert().values(**payload))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    reset_auto_increment(mysql_engine, table)
    log(f"  {table}: {len(rows)} filas migradas", log_file)
    return len(rows)


def ensure_mysql_is_ready(mysql_engine: Engine, force: bool) -> None:
    inspector = inspect(mysql_engine)
    existing = set(inspector.get_table_names())
    if not existing:
        return

    populated = [
        table
        for table in MIGRATION_TABLES
        if table in existing and not mysql_table_empty(mysql_engine, table)
    ]
    if populated and not force:
        raise RuntimeError(
            "MySQL ya contiene datos en: "
            + ", ".join(populated)
            + ". Usa --force para sobrescribir (elimina tablas primero)."
        )


def clear_mysql_tables(mysql_engine: Engine) -> None:
    with mysql_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(MIGRATION_TABLES):
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar SQLite → MySQL")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE))
    parser.add_argument("--mysql-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--skip-alembic", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite no encontrado: {sqlite_path}", file=sys.stderr)
        return 1

    log_file = LOG_DIR / f"migration_{datetime.now():%Y%m%d_%H%M%S}.log"

    if not args.dry_run and not args.skip_backup:
        import subprocess

        log("Creando backup SQLite...", log_file)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "backup_sqlite.py"), "--source", str(sqlite_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            log(f"ERROR backup: {result.stderr or result.stdout}", log_file)
            return 1
        log(result.stdout.strip(), log_file)

    sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    if args.dry_run:
        log("Modo dry-run: solo conteo de registros (SQLite)", log_file)
        total = 0
        for table in MIGRATION_TABLES:
            total += migrate_table(sqlite_engine, None, table, True, log_file)
        log(f"Total registros a migrar: {total}", log_file)
        log("Dry-run completado. MySQL no requerido.", log_file)
        return 0

    mysql_engine = create_engine(args.mysql_url, pool_pre_ping=True)

    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log("Conexión MySQL OK", log_file)
    except Exception as exc:
        log(f"ERROR conexión MySQL: {exc}", log_file)
        return 1

    ensure_mysql_is_ready(mysql_engine, args.force)
    if args.force:
        log("--force: eliminando tablas existentes en MySQL", log_file)
        clear_mysql_tables(mysql_engine)

    if not args.skip_alembic:
        log("Ejecutando alembic upgrade head...", log_file)
        run_alembic_upgrade(args.mysql_url)

    log("Migrando datos...", log_file)
    migrated_total = 0
    for table in MIGRATION_TABLES:
        migrated_total += migrate_table(
            sqlite_engine, mysql_engine, table, False, log_file
        )

    log("Validando migración...", log_file)
    from scripts.validate_migration import compare_engines, verify_mysql_foreign_keys

    comparison = compare_engines(sqlite_engine, mysql_engine, MIGRATION_TABLES)
    fk_checks = verify_mysql_foreign_keys(mysql_engine)
    success = comparison["all_ok"] and all(item["ok"] for item in fk_checks)

    log(f"Total filas migradas: {migrated_total}", log_file)
    log(f"Validación conteos: {'OK' if comparison['all_ok'] else 'FALLÓ'}", log_file)
    log(
        f"Validación FKs: {'OK' if all(i['ok'] for i in fk_checks) else 'FALLÓ'}",
        log_file,
    )
    log(f"Log: {log_file}", log_file)

    if success:
        log("MIGRACIÓN COMPLETADA CON ÉXITO", log_file)
        log("Actualiza DATABASE_URL en .env y reinicia la aplicación.", log_file)
        return 0

    log("MIGRACIÓN COMPLETADA CON ERRORES DE VALIDACIÓN", log_file)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
