#!/usr/bin/env python3
"""Comprueba usuarios admin y prueba contraseña."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.auth.security import verify_password
from app.database import SessionLocal
from app.models.user import User


def main() -> int:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Total usuarios: {len(users)}")
        for user in users:
            ok = verify_password("123456", user.password or "")
            active = getattr(user, "active", True)
            print(
                f"  - {user.username} | rol={user.role} | activo={active} | "
                f"123456={'OK' if ok else 'NO'}"
            )

        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("\nNo existe usuario 'admin'.")
            return 1

        print("\nUsuario admin encontrado.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
