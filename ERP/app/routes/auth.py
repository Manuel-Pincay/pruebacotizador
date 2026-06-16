from fastapi import APIRouter
from fastapi import Request
from fastapi import Form
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.company_config import CompanyConfig

from app.auth.security import verify_password, hash_password, verify_admin_password
from app.auth.session import cookie_options, sign_user_session
from app.auth.permissions import get_login_redirect_url

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


@router.get(
    "/login",
    response_class=HTMLResponse
)
async def login_page(request: Request, db: Session = Depends(get_db)):

    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"company_name": company_name}
    )


def _login_context(db: Session, *, error: str = "", username: str = "") -> dict:
    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"
    return {
        "error": error,
        "username": username,
        "company_name": company_name,
    }


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db)
):
    username_clean = username.strip()
    password_clean = password.strip()

    if not username_clean or not password_clean:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=_login_context(
                db,
                error="Ingrese usuario y contraseña.",
                username=username_clean,
            ),
        )

    user = db.query(User).filter(
        User.username == username_clean
    ).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=_login_context(
                db,
                error="Usuario incorrecto",
                username=username_clean,
            ),
        )

    valid = verify_password(
        password_clean,
        user.password
    )

    if not valid:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=_login_context(
                db,
                error="Contraseña incorrecta",
                username=username_clean,
            ),
        )

    if not getattr(user, "active", True):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context=_login_context(
                db,
                error="Usuario inactivo. Contacte al administrador.",
                username=username_clean,
            ),
        )

    response = RedirectResponse(
        url=get_login_redirect_url(user.role),
        status_code=302
    )

    response.set_cookie(
        key="user",
        value=sign_user_session(user.username),
        **cookie_options(),
    )

    return response


@router.get("/login/recuperar-clave", response_class=HTMLResponse)
async def recover_password_page(request: Request, db: Session = Depends(get_db)):
    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"

    return templates.TemplateResponse(
        request=request,
        name="auth/recover_password.html",
        context={"company_name": company_name},
    )


@router.post("/login/recuperar-clave")
async def recover_password(
    request: Request,
    username: str = Form(...),
    admin_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"

    def _render(error: str):
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context={
                "error": error,
                "company_name": company_name,
                "username": username.strip(),
            },
        )

    username_clean = username.strip()
    if not username_clean:
        return _render("Indique el usuario.")

    if not verify_admin_password(admin_password):
        return _render("Clave de administrador incorrecta.")

    if len(new_password.strip()) < 4:
        return _render("La nueva contraseña debe tener al menos 4 caracteres.")

    if new_password.strip() != confirm_password.strip():
        return _render("Las contraseñas nuevas no coinciden.")

    user = db.query(User).filter(User.username == username_clean).first()
    if not user:
        return _render("Usuario no encontrado.")

    user.password = hash_password(new_password.strip())
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="auth/recover_password.html",
        context={
            "success": f"Contraseña actualizada para «{username_clean}». Ya puede iniciar sesión.",
            "company_name": company_name,
        },
    )


@router.get("/logout")
async def logout():

    response = RedirectResponse(
        url="/login",
        status_code=302
    )

    opts = cookie_options()
    response.delete_cookie(key="user", samesite=opts["samesite"])
    if opts.get("secure"):
        response.delete_cookie(key="user", secure=True, samesite=opts["samesite"])

    return response