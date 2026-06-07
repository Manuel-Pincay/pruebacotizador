from fastapi import APIRouter
from fastapi import Request
from fastapi import Form
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database import get_db

from app.models.user import User
from app.models.company_config import CompanyConfig

from app.auth.security import hash_password, verify_password
from app.auth.session import cookie_options, sign_user_session

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


def _company_name(db: Session) -> str:
    config = db.query(CompanyConfig).first()
    return config.company_name if config else "SISTEMA ERP"


@router.get(
    "/login",
    response_class=HTMLResponse
)
async def login_page(
    request: Request,
    db: Session = Depends(get_db),
    ok: str | None = None,
):

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "company_name": _company_name(db),
            "success": "Contraseña actualizada. Ya puedes ingresar." if ok else None,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db)
):
    username = username.strip()
    company_name = _company_name(db)

    if not username:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Ingresa tu usuario",
                "company_name": company_name,
            },
        )

    if not password:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Ingresa tu contraseña",
                "username": username,
                "company_name": company_name,
            },
        )

    user = db.query(User).filter(
        User.username == username
    ).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Usuario incorrecto",
                "username": username,
                "company_name": company_name,
            },
        )

    valid = verify_password(
        password,
        user.password
    )

    if not valid:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Contraseña incorrecta",
                "username": username,
                "company_name": company_name,
            },
        )

    if not getattr(user, "active", True):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Usuario inactivo. Contacte al administrador.",
                "username": username,
                "company_name": company_name,
            },
        )

    response = RedirectResponse(
        url="/",
        status_code=302
    )

    response.set_cookie(
        key="user",
        value=sign_user_session(user.username),
        **cookie_options(),
    )

    return response


@router.get("/login/recuperar", response_class=HTMLResponse)
async def recover_password_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="auth/recover_password.html",
        context={"company_name": _company_name(db)},
    )


@router.post("/login/recuperar")
async def recover_password(
    request: Request,
    username: str = Form(""),
    recovery_code: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    username = username.strip()
    company_name = _company_name(db)
    context = {
        "company_name": company_name,
        "username": username,
    }

    if not username:
        context["error"] = "Ingresa tu usuario"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    if not recovery_code.strip():
        context["error"] = "Ingresa el código de recuperación"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    if not new_password:
        context["error"] = "Ingresa la nueva contraseña"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    if len(new_password) < 6:
        context["error"] = "La contraseña debe tener al menos 6 caracteres"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    if new_password != confirm_password:
        context["error"] = "Las contraseñas no coinciden"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        context["error"] = "Usuario no encontrado"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    if recovery_code.strip() != settings.secretadmin_password:
        context["error"] = "Código de recuperación incorrecto"
        return templates.TemplateResponse(
            request=request,
            name="auth/recover_password.html",
            context=context,
        )

    user.password = hash_password(new_password)
    db.commit()

    return RedirectResponse(url="/login?ok=1", status_code=302)


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
