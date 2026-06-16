from fastapi import Request

from fastapi.responses import RedirectResponse

from app.auth.session import resolve_user_session
from app.auth.permissions import role_required as permissions_role_required
from app.database import SessionLocal
from app.models.user import User


def login_required(request: Request):

    username = resolve_user_session(request.cookies.get("user"))

    if not username:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()

    user = db.query(User).filter(User.username == username).first()

    db.close()

    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if not getattr(user, "active", True):
        return RedirectResponse(url="/login", status_code=302)

    return user


role_required = permissions_role_required
