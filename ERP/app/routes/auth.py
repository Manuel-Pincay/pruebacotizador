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
        name="login.html",
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
            name="login.html",
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
            name="login.html",
            context={
                "error": "Contraseña incorrecta",
                "company_name": company_name
            }
        )

    response = RedirectResponse(
        url="/",
        status_code=302
    )

    response.set_cookie(
    key="user",
    value=user.username,
    httponly=True,
    samesite="Lax"
)

    return response

@router.get("/logout")
async def logout():

    response = RedirectResponse(
        url="/login",
        status_code=302
    )

    response.delete_cookie(
        key="user"
    )

    return response