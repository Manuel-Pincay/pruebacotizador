from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User

from app.auth.security import hash_password

from app.auth.auth_handler import role_required


router = APIRouter(
    prefix="/users",
    tags=["users"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


# =========================================
# USERS LIST
# =========================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def users_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    users = db.query(
        User
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users
        }
    )


# =========================================
# NEW USER PAGE
# =========================================

@router.get(
    "/new",
    response_class=HTMLResponse
)
async def new_user_page(
    request: Request
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request=request,
        name="user_new.html",
        context={}
    )


# =========================================
# CREATE USER
# =========================================

@router.post("/new")
async def create_user(

    request: Request,

    username: str = Form(...),

    full_name: str = Form(...),

    password: str = Form(...),

    role: str = Form(...),

    db: Session = Depends(get_db)

):

    try:

        user = role_required(
            request,
            ["admin"]
        )

        if isinstance(user, RedirectResponse):
            return user

        exists = db.query(User).filter(
            User.username == username
        ).first()

        if exists:

            return templates.TemplateResponse(
                request=request,
                name="user_new.html",
                context={
                    "error": "Usuario ya existe"
                }
            )

        new_user = User(

            username=username,

            full_name=full_name,

            password=hash_password(password),

            role=role

        )

        db.add(new_user)

        db.commit()

        return RedirectResponse(
            url="/users",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        return HTMLResponse(
            content=f"""
            <h1>
                Error creando usuario
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )