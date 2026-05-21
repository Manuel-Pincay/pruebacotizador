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

from app.auth.security import verify_password

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/login",
    response_class=HTMLResponse
)
async def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
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

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Usuario incorrecto"
            }
        )

    valid = verify_password(
        password,
        user.password
    )

    if not valid:

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Contraseña incorrecta"
            }
        )

    response = RedirectResponse(
        url="/",
        status_code=302
    )

    response.set_cookie(
        key="user",
        value=user.username
    )

    return response