#!/usr/bin/env python3
"""
Comprueba o restablece el usuario administrador.

Uso:
  python scripts/check_admin.py
  python scripts/reset_admin_password.py
  python scripts/reset_admin_password.py --password MiNuevaClave
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restablecer contraseña admin ERP")
    parser.add_argument("--username", default="admin")
    parser.add_argument(
        "--password",
        help="Nueva contraseña (default: 123456 o ERP_ADMIN_PASSWORD del .env)",
    )
    args = parser.parse_args()

    from app.auth.security import verify_password
    from app.database import SessionLocal
    from app.models.user import User
    from app.services.user_bootstrap import ensure_admin_user

    db = SessionLocal()
    try:
        before = db.query(User).filter(User.username == args.username).first()
        user, created = ensure_admin_user(
            db,
            username=args.username,
            password=args.password,
        )

        password = args.password or __import__("os").getenv("ERP_ADMIN_PASSWORD", "123456")
        ok = verify_password(password, user.password)

        if created:
            log(f"Usuario '{user.username}' creado.")
        else:
            log(f"Usuario '{user.username}' actualizado (contraseña restablecida).")

        log(f"Contraseña verificada: {'OK' if ok else 'ERROR'}")
        log(f"Ingresa con: {user.username} / {password}")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
