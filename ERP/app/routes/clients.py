from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi.responses import JSONResponse

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.utils.activity import log_activity

from app.models import client
from app.models.client import Client

router = APIRouter(
    prefix="/clients",
    tags=["clients"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


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
    client_type: str = Form("Minorista"),
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
        # VALIDAR CÉDULA/RUC DUPLICADO

        existing_client = db.query(
            Client
        ).filter(
            Client.ruc_ci == ruc_ci,
            Client.id != client_id
        ).first()

        if existing_client:

            return HTMLResponse(
                content=f"""
                <script>

                    alert(
                        "Ya existe otro cliente con la cédula/RUC: {ruc_ci}"
                    )

                    window.history.back()

                </script>
                """,
                status_code=400
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

    # =====================================
    # VALIDATE EXISTING CLIENT
    # =====================================

    existing_client = db.query(
        Client
    ).filter(
        Client.ruc_ci == ruc_ci
    ).first()
    if existing_client:

        return HTMLResponse(
        content=f"""
        <script>

            alert(
                "Ya existe un cliente con la cédula/RUC: {ruc_ci}"
            )

            window.location.href = "/clients/new"

        </script>
        """,
        status_code=400
    )
    # =====================================
    # CREATE CLIENT
    # =====================================

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

    try:
        log_activity(
            db,
            "Cliente creado",
            client.name or "Cliente sin nombre"
        )
    except Exception:
        pass

    return RedirectResponse(
        url="/clients",
        status_code=302
    )
@router.get("/search")
async def search_clients(
    q: str = "",
    db: Session = Depends(get_db)
):

    clients = db.query(
        Client
    ).filter(
        Client.name.ilike(f"%{q}%")
    ).limit(10).all()

    return [

        {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "ruc_ci": client.ruc_ci
        }

        for client in clients
    ]

## clientes busqueda 
@router.get("/search")
async def search_clients(
    q: str = "",
    db: Session = Depends(get_db)
):

    clients = (
        db.query(Client)
        .filter(
            Client.name.ilike(f"%{q}%")
        )
        .limit(10)
        .all()
    )

    return [
        {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "email": client.email,
            "address": client.address
        }
        for client in clients
    ]
@router.get("/catalog/modal")
async def client_catalog_modal(
    request: Request,
    db: Session = Depends(get_db)
):

    clients = (
        db.query(Client)
        .order_by(Client.name.asc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/client_catalog_table.html",
        context={
            "clients": clients
        }
    )