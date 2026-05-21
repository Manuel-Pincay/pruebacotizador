from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models import client
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

@router.get(
    "/{client_id}/edit",
    response_class=HTMLResponse
)
async def edit_client_page(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    client = db.query(
        Client
    ).filter(
        Client.id == client_id
    ).first()

    if not client:

        return RedirectResponse(
            url="/clients",
            status_code=302
        )

    return templates.TemplateResponse(
        request=request,
        name="client_edit.html",
        context={
            "client": client
        }
    )

@router.post("/{client_id}/edit")
async def update_client(

    client_id: int,

    name: str = Form(...),

    phone: str = Form(""),

    email: str = Form(""),

    address: str = Form(""),

    ruc_ci: str = Form(""),
    company: str = Form(""),

    client_type: str = Form("particular"),

    observations: str = Form(""),

    db: Session = Depends(get_db)

):

    try:

        client = db.query(
            Client
        ).filter(
            Client.id == client_id
        ).first()

        if not client:

            return RedirectResponse(
                url="/clients",
                status_code=302
            )

        client.name = name
        client.phone = phone
        client.email = email
        client.address = address
        client.ruc_ci = ruc_ci
        client.company = company
        client.client_type = client_type
        client.observations = observations

        db.commit()

        return RedirectResponse(
            url="/clients",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        return HTMLResponse(
            content=f"""
            <h1>
                Error actualizando cliente
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )
    
@router.get("/{client_id}/delete")
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db)
):

    try:

        client = db.query(
            Client
        ).filter(
            Client.id == client_id
        ).first()

        if client:

            db.delete(client)

            db.commit()

        return RedirectResponse(
            url="/clients",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        return HTMLResponse(
            content=f"""
            <h1>
                No se puede eliminar cliente
            </h1>

            <p>
                Probablemente tiene cotizaciones asociadas
            </p>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
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