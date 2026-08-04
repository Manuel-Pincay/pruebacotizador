from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


def notify_user(
    db: Session,
    user_id: int,
    title: str,
    message: str = "",
    link: str | None = None,
) -> None:
    try:
        db.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                link=link,
                is_read=False,
            )
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def notify_roles(
    db: Session,
    roles: list[str],
    title: str,
    message: str = "",
    link: str | None = None,
    exclude_user_id: int | None = None,
) -> None:
    """Notifica a todos los usuarios activos con los roles indicados."""
    try:
        q = db.query(User).filter(User.role.in_(roles))
        if hasattr(User, "active"):
            q = q.filter(User.active.is_(True))
        users = q.all()
        for u in users:
            if exclude_user_id and u.id == exclude_user_id:
                continue
            db.add(
                Notification(
                    user_id=u.id,
                    title=title,
                    message=message,
                    link=link,
                    is_read=False,
                )
            )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def unread_count(db: Session, user_id: int) -> int:
    try:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
            .count()
        )
    except Exception:
        return 0
