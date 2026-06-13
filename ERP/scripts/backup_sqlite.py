#!/usr/bin/env python3
"""
Respaldo completo de SQLite antes de migrar a MySQL.

Uso:
    python scripts/backup_sqlite.py
    python scripts/backup_sqlite.py --source database/innova.db --keep 10
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "database" / "innova.db"
DEFAULT_BACKUP_DIR = ROOT / "backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_sql_dump(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["sqlite3", str(source), ".dump"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            destination.write_text(result.stdout, encoding="utf-8")
            return
    except (FileNotFoundError, OSError):
        pass

    with destination.open("w", encoding="utf-8") as handle:
        conn = sqlite3.connect(source)
        for line in conn.iterdump():
            handle.write(f"{line}\n")
        conn.close()


def prune_old_backups(backup_dir: Path, keep: int) -> None:
    backups = sorted(
        backup_dir.glob("innova_*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink(missing_ok=True)
        old.with_suffix(".db.sha256").unlink(missing_ok=True)
        sql_old = old.with_suffix(".sql")
        sql_old.unlink(missing_ok=True)


def run_backup(
    source: Path,
    backup_dir: Path,
    keep: int = 10,
    export_sql: bool = True,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"No se encontró la base SQLite: {source}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_db = backup_dir / f"innova_{timestamp}.db"
    checksum_file = backup_dir / f"innova_{timestamp}.db.sha256"

    shutil.copy2(source, backup_db)
    checksum = sha256_file(backup_db)
    checksum_file.write_text(f"{checksum}  {backup_db.name}\n", encoding="utf-8")

    sql_path = None
    if export_sql:
        sql_path = backup_dir / f"innova_{timestamp}.sql"
        export_sql_dump(source, sql_path)

    prune_old_backups(backup_dir, keep)

    return {
        "source": str(source),
        "backup_db": str(backup_db),
        "checksum_sha256": checksum,
        "checksum_file": str(checksum_file),
        "sql_dump": str(sql_path) if sql_path else None,
        "size_bytes": backup_db.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup SQLite del ERP")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument("--keep", type=int, default=10, help="Backups .db a conservar")
    parser.add_argument("--no-sql-dump", action="store_true")
    args = parser.parse_args()

    try:
        result = run_backup(
            source=Path(args.source),
            backup_dir=Path(args.backup_dir),
            keep=args.keep,
            export_sql=not args.no_sql_dump,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Backup completado")
    print(f"  Archivo:   {result['backup_db']}")
    print(f"  SHA256:    {result['checksum_sha256']}")
    print(f"  Tamaño:    {result['size_bytes']:,} bytes")
    if result["sql_dump"]:
        print(f"  SQL dump:  {result['sql_dump']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
