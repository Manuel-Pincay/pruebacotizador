#!/usr/bin/env python3
"""
Limpieza de archivos huérfanos en uploads/.

Uso:
    python scripts/cleanup_storage.py              # reporte (dry-run)
    python scripts/cleanup_storage.py --delete     # eliminar huérfanos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.storage_stats import collect_storage_stats
from app.utils.image_storage import format_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpiar archivos huérfanos")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Eliminar archivos huérfanos (por defecto solo reporte)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = collect_storage_stats(db)
    finally:
        db.close()

    orphans = stats["orphans"]
    total_bytes = stats["totals"]["orphan_bytes"]

    print(f"Huérfanos detectados: {len(orphans)} ({format_bytes(total_bytes)})")
    print("")

    if not orphans:
        print("Nada que limpiar.")
        return 0

    for item in orphans:
        print(f"  {'[DEL]' if args.delete else '[---]'} {item['path']} ({format_bytes(item['size'])})")

    if not args.delete:
        print("")
        print("Modo reporte. Para eliminar: python scripts/cleanup_storage.py --delete")
        return 0

    removed = 0
    for item in orphans:
        path = Path(item["path"])
        if path.exists():
            path.unlink()
            removed += 1
    print(f"\nEliminados: {removed} archivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
