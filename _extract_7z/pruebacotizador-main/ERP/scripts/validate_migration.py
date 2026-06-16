#!/usr/bin/env python3
"""
Valida que los conteos SQLite vs MySQL coincidan tras la migración.

Uso:
    python scripts/validate_migration.py
    python scripts/validate_migration.py --sqlite database/innova.db \\
        --mysql-url mysql+pymysql://user:pass@localhost/erp?charset=utf8mb4
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = ROOT / "database" / "innova.db"

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

CRITICAL_CHECKS = [
    ("users", "SELECT COUNT(*) FROM users"),
    ("clients", "SELECT COUNT(*) FROM clients"),
    ("products", "SELECT COUNT(*) FROM products"),
    ("quotations", "SELECT COUNT(*) FROM quotations"),
    ("quotation_items", "SELECT COUNT(*) FROM quotation_items"),
    ("company_config", "SELECT COUNT(*) FROM company_config"),
]


def count_rows(engine, table: str) -> int:
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return -1
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0


def compare_engines(sqlite_engine, mysql_engine, tables: list[str]) -> dict:
    rows = []
    all_ok = True

    for table in tables:
        sqlite_count = count_rows(sqlite_engine, table)
        mysql_count = count_rows(mysql_engine, table)
        ok = sqlite_count == mysql_count and sqlite_count >= 0 and mysql_count >= 0
        if not ok:
            all_ok = False
        rows.append(
            {
                "table": table,
                "sqlite": sqlite_count,
                "mysql": mysql_count,
                "ok": ok,
            }
        )

    return {"tables": rows, "all_ok": all_ok}


def verify_mysql_foreign_keys(mysql_engine) -> list[dict]:
    checks = [
        ("quotations.client_id -> clients.id", """
            SELECT COUNT(*) FROM quotations t
            LEFT JOIN clients r ON t.client_id = r.id
            WHERE t.client_id IS NOT NULL AND r.id IS NULL
        """),
        ("quotation_items.quotation_id -> quotations.id", """
            SELECT COUNT(*) FROM quotation_items t
            LEFT JOIN quotations r ON t.quotation_id = r.id
            WHERE t.quotation_id IS NOT NULL AND r.id IS NULL
        """),
        ("quotation_items.product_id -> products.id", """
            SELECT COUNT(*) FROM quotation_items t
            LEFT JOIN products r ON t.product_id = r.id
            WHERE t.product_id IS NOT NULL AND r.id IS NULL
        """),
        ("production_orders.quotation_id -> quotations.id", """
            SELECT COUNT(*) FROM production_orders t
            LEFT JOIN quotations r ON t.quotation_id = r.id
            WHERE t.quotation_id IS NOT NULL AND r.id IS NULL
        """),
        ("shipments.quotation_id -> quotations.id", """
            SELECT COUNT(*) FROM shipments t
            LEFT JOIN quotations r ON t.quotation_id = r.id
            WHERE t.quotation_id IS NOT NULL AND r.id IS NULL
        """),
        ("inventory_movements.product_id -> products.id", """
            SELECT COUNT(*) FROM inventory_movements t
            LEFT JOIN products r ON t.product_id = r.id
            WHERE t.product_id IS NOT NULL AND r.id IS NULL
        """),
    ]
    results = []
    with mysql_engine.connect() as conn:
        for label, sql in checks:
            orphans = conn.execute(text(sql)).scalar() or 0
            results.append({"check": label, "orphans": orphans, "ok": orphans == 0})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validar migración SQLite → MySQL")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE))
    parser.add_argument("--mysql-url", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite no encontrado: {sqlite_path}", file=sys.stderr)
        return 1

    sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    mysql_engine = create_engine(args.mysql_url, pool_pre_ping=True)

    comparison = compare_engines(sqlite_engine, mysql_engine, MIGRATION_TABLES)
    fk_checks = verify_mysql_foreign_keys(mysql_engine)

    report = {
        "generated_at": datetime.now().isoformat(),
        "sqlite": str(sqlite_path),
        "mysql_url": args.mysql_url.split("@")[-1],
        "comparison": comparison,
        "foreign_keys": fk_checks,
        "success": comparison["all_ok"] and all(item["ok"] for item in fk_checks),
    }

    output_path = args.output or ROOT / f"migration_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{'Tabla':<25} {'SQLite':>8} {'MySQL':>8}  OK")
    print("-" * 50)
    for row in comparison["tables"]:
        mark = "OK" if row["ok"] else "FAIL"
        print(f"{row['table']:<25} {row['sqlite']:>8} {row['mysql']:>8}  {mark}")

    print("\nIntegridad referencial MySQL:")
    for item in fk_checks:
        mark = "OK" if item["ok"] else f"FAIL ({item['orphans']} huérfanos)"
        print(f"  {item['check']}: {mark}")

    print(f"\nReporte: {output_path}")
    print("RESULTADO:", "ÉXITO" if report["success"] else "FALLÓ")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
