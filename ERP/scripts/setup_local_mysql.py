#!/usr/bin/env python3
"""
MariaDB portable SOLO para desarrollo local (puerto 3307).
No usar en producción — ver docs/DATABASE.md

Uso: python scripts/setup_local_mysql.py
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools" / "mariadb"
DATA_DIR = TOOLS_DIR / "data"
ZIP_PATH = TOOLS_DIR / "mariadb.zip"

# MariaDB 10.11 LTS — compatible con MySQL 8 para este ERP
MARIADB_URL = (
    "https://archive.mariadb.org/mariadb-10.11.13/"
    "winx64-packages/mariadb-10.11.13-winx64.zip"
)

MYSQL_ROOT_PASSWORD = "erp_root_local"
MYSQL_USER = "erp_user"
MYSQL_PASSWORD = "erppassword"
MYSQL_DATABASE = "erp"
MYSQL_PORT = 3307


def log(msg: str) -> None:
    print(msg, flush=True)


def database_url() -> str:
    return (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@127.0.0.1:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )


def port_is_open(port: int = MYSQL_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def app_database_ready() -> bool:
    try:
        import pymysql

        conn = pymysql.connect(
            host="127.0.0.1",
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


def mysql_cli_ready(mariadb_root: Path, user: str, password: str = "") -> bool:
    mysql = mariadb_root / "bin" / "mysql.exe"
    auth = [f"-u{user}"]
    if password:
        auth.append(f"-p{password}")
    result = subprocess.run(
        [str(mysql), *auth, f"-P{MYSQL_PORT}", "-e", "SELECT 1"],
        capture_output=True,
    )
    return result.returncode == 0


def download_mariadb(force: bool = False) -> Path:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    extracted = list(TOOLS_DIR.glob("mariadb-*/bin/mysqld.exe"))
    if extracted and not force:
        return extracted[0].parent.parent

    if not ZIP_PATH.exists() or force:
        log(f"Descargando MariaDB (~80 MB)...")
        urlretrieve(MARIADB_URL, ZIP_PATH)

    log("Extrayendo MariaDB...")
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        archive.extractall(TOOLS_DIR)

    folders = list(TOOLS_DIR.glob("mariadb-*/bin/mysqld.exe"))
    if not folders:
        raise RuntimeError("No se encontró mysqld.exe tras extraer")
    return folders[0].parent.parent


def init_database(mariadb_root: Path) -> None:
    bin_dir = mariadb_root / "bin"
    mysqld = bin_dir / "mysqld.exe"
    mysql_install_db = bin_dir / "mysql_install_db.exe"
    my_ini = mariadb_root / "my.ini"

    if DATA_DIR.exists():
        return

    DATA_DIR.mkdir(parents=True)
    my_ini.write_text(
        f"""[mysqld]
port={MYSQL_PORT}
basedir={mariadb_root.as_posix()}
datadir={DATA_DIR.as_posix()}
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
skip-networking=0
bind-address=127.0.0.1

[client]
port={MYSQL_PORT}
default-character-set=utf8mb4
""",
        encoding="utf-8",
    )

    log("Inicializando datadir MariaDB...")
    install_db = mysql_install_db
    if not install_db.exists():
        install_db = bin_dir / "mariadb-install-db.exe"

    subprocess.run(
        [str(install_db), f"--datadir={DATA_DIR}"],
        check=True,
        cwd=str(bin_dir),
    )


def start_server(mariadb_root: Path) -> subprocess.Popen:
    bin_dir = mariadb_root / "bin"
    mysqld = bin_dir / "mysqld.exe"
    my_ini = mariadb_root / "my.ini"

    log(f"Iniciando MariaDB en puerto {MYSQL_PORT}...")
    process = subprocess.Popen(
        [str(mysqld), f"--defaults-file={my_ini}"],
        cwd=str(bin_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process


def wait_for_mysql(mariadb_root: Path, timeout: int = 30) -> None:
    for _ in range(timeout):
        if app_database_ready():
            return
        if mysql_cli_ready(mariadb_root, "root"):
            return
        if mysql_cli_ready(mariadb_root, "root", MYSQL_ROOT_PASSWORD):
            return
        time.sleep(1)
    raise TimeoutError("MariaDB no respondió a tiempo")


def setup_users(mariadb_root: Path) -> None:
    if app_database_ready():
        return

    mysql = mariadb_root / "bin" / "mysql.exe"
    sql = f"""
CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{MYSQL_USER}'@'localhost' IDENTIFIED BY '{MYSQL_PASSWORD}';
CREATE USER IF NOT EXISTS '{MYSQL_USER}'@'127.0.0.1' IDENTIFIED BY '{MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON {MYSQL_DATABASE}.* TO '{MYSQL_USER}'@'localhost';
GRANT ALL PRIVILEGES ON {MYSQL_DATABASE}.* TO '{MYSQL_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
"""
    for extra_auth in ([], [f"-p{MYSQL_ROOT_PASSWORD}"]):
        result = subprocess.run(
            [str(mysql), "-uroot", f"-P{MYSQL_PORT}", *extra_auth, "-e", sql],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            if not extra_auth:
                subprocess.run(
                    [
                        str(mysql),
                        "-uroot",
                        f"-P{MYSQL_PORT}",
                        "-e",
                        f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{MYSQL_ROOT_PASSWORD}';",
                    ],
                    check=True,
                )
            return
    raise RuntimeError(result.stderr or result.stdout)


def print_ready(process: subprocess.Popen | None = None) -> None:
    log("")
    log("MariaDB listo.")
    log(f"  Puerto:      {MYSQL_PORT}")
    log(f"  Base:        {MYSQL_DATABASE}")
    log(f"  Usuario:     {MYSQL_USER}")
    log(f"  Contraseña:  {MYSQL_PASSWORD}")
    log(f"  DATABASE_URL={database_url()}")
    if process:
        log(f"  PID:         {process.pid}")
        log("")
        log("Para detener: taskkill /PID <pid> /F")
    else:
        log("  (servidor ya estaba en ejecución)")


def ensure_running(force_download: bool = False) -> bool:
    """Inicia MariaDB portable si no responde. Devuelve True si la BD está lista."""
    try:
        if app_database_ready():
            return True

        mariadb_root = download_mariadb(force=force_download)
        init_database(mariadb_root)

        if not port_is_open():
            start_server(mariadb_root)
            wait_for_mysql(mariadb_root)
        else:
            log(f"Puerto {MYSQL_PORT} ocupado; esperando conexión...")
            wait_for_mysql(mariadb_root)

        setup_users(mariadb_root)
        return app_database_ready()
    except Exception as exc:
        log(f"ERROR: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    if app_database_ready():
        log("MariaDB ya responde en el puerto 3307.")
        print_ready()
        return 0

    if ensure_running(force_download=args.force_download):
        print_ready()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
