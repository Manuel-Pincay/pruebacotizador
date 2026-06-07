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

from app.auth.security import verify_password
from app.auth.session import cookie_options, sign_user_session

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


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.username == username
    ).first()

    if not user:

        config = db.query(CompanyConfig).first()
        company_name = config.company_name if config else "SISTEMA ERP"

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Usuario incorrecto",
                "company_name": company_name
            }
        )

    valid = verify_password(
        password,
        user.password
    )

    if not valid:

        config = db.query(CompanyConfig).first()
        company_name = config.company_name if config else "SISTEMA ERP"

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Contraseña incorrecta",
                "company_name": company_name
            }
        )

    if not getattr(user, "active", True):

        config = db.query(CompanyConfig).first()
        company_name = config.company_name if config else "SISTEMA ERP"

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Usuario inactivo. Contacte al administrador.",
                "company_name": company_name
            }
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