from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.client import Client

router = APIRouter(
    prefix="/clients",
    tags=["clients"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/",
    response_class=HTMLResponse
)
async def clients_page(
    request: Request,
    db: Session = Depends(get_db)
):

    clients = db.query(Client).all()

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients
        }
    )


@router.get(
    "/new",
    response_class=HTMLResponse
)
async def new_client_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="client_new.html",
        context={}
    )


@router.post("/new")
async def create_client(
    name: str = Form(...),
    company: str = Form(""),
    ruc_ci: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    client_type: str = Form(...),
    observations: str = Form(""),
    db: Session = Depends(get_db)
):

    client = Client(
        name=name,
        company=company,
        ruc_ci=ruc_ci,
        phone=phone,
        email=email,
        address=address,
        client_type=client_type,
        observations=observations
    )

    db.add(client)
    db.commit()

    return RedirectResponse(
        url="/clients",
        status_code=302
    )