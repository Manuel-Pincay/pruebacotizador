from fastapi import Request

from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import SessionLocal

from app.models.user import User


# =========================================
# LOGIN REQUIRED
# =========================================

def login_required(request: Request):

    username = request.cookies.get("user")

    if not username:

        return RedirectResponse(
            url="/login",
            status_code=302
        )

    db: Session = SessionLocal()

    user = db.query(User).filter(
        User.username == username
    ).first()

    db.close()

    if not user:

        return RedirectResponse(
            url="/login",
            status_code=302
        )

    return user


# =========================================
# ROLE REQUIRED
# =========================================

def role_required(
    request: Request,
    allowed_roles: list
):

    user = login_required(request)

    if isinstance(user, RedirectResponse):
        return user

    if user.role not in allowed_roles:

        return RedirectResponse(
            url="/",
            status_code=302
        )

    return user