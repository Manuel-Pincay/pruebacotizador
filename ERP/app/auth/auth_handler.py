from fastapi import Request

from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import SessionLocal

from app.models.user import User

from app.auth.permissions import role_required as permissions_role_required


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

role_required = permissions_role_required