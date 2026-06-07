import os

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models.user import User

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "123456"


def ensure_admin_user(
    db: Session,
    *,
    username: str = DEFAULT_ADMIN_USERNAME,
    password: str | None = None,
) -> tuple[User, bool]:
    """
    Crea o restablece el usuario administrador.
    Devuelve (usuario, fue_creado).
    """
    plain_password = password or os.getenv("ERP_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    hashed = hash_password(plain_password)

    user = db.query(User).filter(User.username == username).first()
    if user:
        user.password = hashed
        user.role = "admin"
        user.full_name = user.full_name or "Administrador"
        user.active = True
        db.commit()
        db.refresh(user)
        return user, False

    user = User(
        username=username,
        full_name="Administrador",
        password=hashed,
        role="admin",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True
