"""Backup de MySQL vía mysqldump (manual o programado)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config.settings import settings


def _parse_db_url(url: str) -> dict:
    # mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
    cleaned = url.replace("mysql+pymysql://", "mysql://", 1)
    parsed = urlparse(cleaned)
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 3306),
        "database": (parsed.path or "/").lstrip("/").split("?")[0],
    }


def backup_dir() -> Path:
    path = Path(os.getenv("ERP_BACKUP_DIR", "backups"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_mysql_backup() -> Path:
    """Genera un .sql.gz (o .sql) en backups/. Lanza RuntimeError si falla."""
    info = _parse_db_url(settings.database_url)
    if not info["database"]:
        raise RuntimeError("No se pudo determinar el nombre de la base de datos.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_sql = backup_dir() / f"erp_backup_{stamp}.sql"

    mysqldump = shutil.which("mysqldump")
    if not mysqldump:
        raise RuntimeError(
            "No se encontró mysqldump en el PATH. Instala MySQL client o agrega mysqldump al PATH."
        )

    cmd = [
        mysqldump,
        f"--host={info['host']}",
        f"--port={info['port']}",
        f"--user={info['user']}",
        "--single-transaction",
        "--routines",
        "--triggers",
        info["database"],
    ]
    env = os.environ.copy()
    if info["password"]:
        env["MYSQL_PWD"] = info["password"]

    with open(out_sql, "wb") as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        out_sql.unlink(missing_ok=True)
        err = (result.stderr or b"").decode("utf-8", errors="ignore")
        raise RuntimeError(f"mysqldump falló: {err.strip() or result.returncode}")

    # Comprimir si gzip está disponible
    gzip_bin = shutil.which("gzip")
    if gzip_bin:
        subprocess.run([gzip_bin, "-f", str(out_sql)], check=False)
        gz = Path(str(out_sql) + ".gz")
        if gz.exists():
            return gz

    return out_sql


def list_backups(limit: int = 20) -> list[Path]:
    files = sorted(
        list(backup_dir().glob("erp_backup_*.sql"))
        + list(backup_dir().glob("erp_backup_*.sql.gz")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit]
