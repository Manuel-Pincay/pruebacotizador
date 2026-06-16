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

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


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
        name="users/list.html",
        context={
            "users": users,
            "user": user,
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
        name="users/form.html",
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
                name="users/form.html",
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


# =========================================
# EDIT USER PAGE
# =========================================

@router.get(
    "/{user_id}/edit",
    response_class=HTMLResponse
)
async def edit_user_page(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):

    admin = role_required(request, ["admin"])

    if isinstance(admin, RedirectResponse):
        return admin

    edit_user = db.query(User).filter(User.id == user_id).first()

    if not edit_user:
        return RedirectResponse(url="/users", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="users/form.html",
        context={
            "edit_user": edit_user,
            "edit_mode": True,
            "user": admin,
        }
    )


# =========================================
# UPDATE USER
# =========================================

@router.post("/{user_id}/edit")
async def update_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(""),
    role: str = Form(...),
    active: str | None = Form(None),
    db: Session = Depends(get_db)
):

    admin = role_required(request, ["admin"])

    if isinstance(admin, RedirectResponse):
        return admin

    edit_user = db.query(User).filter(User.id == user_id).first()

    if not edit_user:
        return RedirectResponse(url="/users", status_code=302)

    duplicate = (
        db.query(User)
        .filter(User.username == username, User.id != user_id)
        .first()
    )

    if duplicate:
        return templates.TemplateResponse(
            request=request,
            name="users/form.html",
            context={
                "edit_user": edit_user,
                "edit_mode": True,
                "error": "Ya existe otro usuario con ese nombre",
                "user": admin,
            }
        )

    edit_user.username = username.strip()
    edit_user.full_name = full_name.strip()
    edit_user.role = role
    edit_user.active = active == "yes"

    if password.strip():
        edit_user.password = hash_password(password.strip())

    db.commit()

    return RedirectResponse(url="/users", status_code=302)


# =========================================
# DELETE USER
# =========================================

@router.get("/{user_id}/delete")
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):

    admin = role_required(request, ["admin"])

    if isinstance(admin, RedirectResponse):
        return admin

    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        return RedirectResponse(url="/users", status_code=302)

    if target.username == "admin":
        return RedirectResponse(url="/users", status_code=302)

    if target.id == admin.id:
        return RedirectResponse(url="/users", status_code=302)

    db.delete(target)
    db.commit()

    return RedirectResponse(url="/users", status_code=302)