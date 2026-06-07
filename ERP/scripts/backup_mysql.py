#!/usr/bin/env python3
"""
Respaldo MySQL/MariaDB del ERP (producción o desarrollo).

Uso:
  python scripts/backup_mysql.py
  python scripts/backup_mysql.py --output backups/manual.sql
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BACKUP_DIR = ROOT / "backups"


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_database_url(url: str) -> dict:
    parsed = urlparse(url.replace("+pymysql", "", 1))
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": (parsed.path or "/").lstrip("/").split("?")[0],
    }


def find_mysqldump() -> str | None:
    found = shutil.which("mysqldump")
    if found:
        return found

    tools_dir = ROOT / "tools" / "mariadb"
    if tools_dir.exists():
        candidates = list(tools_dir.glob("mariadb-*/bin/mysqldump.exe"))
        if candidates:
            return str(candidates[0])

    return None


def run_backup(output_path: Path) -> None:
    from app.config.settings import settings

    cfg = parse_database_url(settings.database_url)
    mysqldump = find_mysqldump()

    if not mysqldump:
        raise RuntimeError(
            "mysqldump no encontrado. Instale MySQL client o use MariaDB portable."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        mysqldump,
        f"-h{cfg['host']}",
        f"-P{cfg['port']}",
        f"-u{cfg['user']}",
        f"-p{cfg['password']}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--set-gtid-purged=OFF",
        cfg["database"],
    ]

    log(f"Generando backup: {output_path}")
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        subprocess.run(cmd, stdout=handle, check=True, stderr=subprocess.PIPE)

    size_kb = output_path.stat().st_size // 1024
    log(f"Backup listo ({size_kb} KB): {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup MySQL ERP")
    parser.add_argument(
        "--output",
        help="Ruta del archivo .sql (default: backups/erp_YYYYMMDD_HHMMSS.sql)",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(args.output) if args.output else BACKUP_DIR / f"erp_{timestamp}.sql"

    try:
        run_backup(output)
        return 0
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        log(f"ERROR mysqldump: {err or exc}")
        return 1
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
