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
from app.auth.auth_handler import role_required

from app.models.client import Client
from app.models.quotation import Quotation
from app.models.production_order import ProductionOrder 

router = APIRouter(prefix="/clients", tags=["clients"])

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config


@router.get("/", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).all()

    return templates.TemplateResponse(
        request=request, name="clients.html", context={"clients": clients, "user": user}
    )


from fastapi.responses import JSONResponse

@router.get("/api/list")
async def clients_api(
    request: Request,
    q: str = "",
    client_type: str = "",
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    query = db.query(Client)

    if q:

        query = query.filter(
            Client.name.ilike(f"%{q}%")
        )

    if client_type:

        query = query.filter(
            Client.client_type == client_type
        )

    clients = query.order_by(
        Client.name.asc()
    ).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "company": c.company,
            "client_type": c.client_type
        }
        for c in clients
    ]

@router.get("/new", response_class=HTMLResponse)
async def new_client_page(request: Request):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request=request,
        name="client_new.html",
        context={"user": user},
    )


@router.get("/{client_id}/edit", response_class=HTMLResponse)
async def edit_client_page(
    client_id: int, request: Request, db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:

        return RedirectResponse(url="/clients", status_code=302)
    # ==========================
    # ESTADISTICAS
    # ==========================

    quotations = (
        db.query(Quotation)
        .filter(
            Quotation.client_id == client.id
        )
        .all()
    )

    quotations_count = len(quotations)

    total_sales = sum(
        q.total or 0
        for q in quotations
    )

    last_quote_date = "-"

    if quotations:

        last_quote = max(
            quotations,
            key=lambda q: q.created_at
        )

        last_quote_date = last_quote.created_at.strftime(
            "%d/%m/%Y"
        )

    # ==========================
    # TEMPLATE
    # ==========================

    return templates.TemplateResponse(
        request=request,
        name="client_edit.html",
        context={
            "client": client,
            "quotations_count": quotations_count,
            "total_sales": total_sales,
            "last_quote_date": last_quote_date,
            "user": user,
        }
    )


@router.get("/{client_id}/history")
async def client_history(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    client = (
        db.query(Client)
        .filter(Client.id == client_id)
        .first()
    )

    if not client:

        return RedirectResponse(
            "/clients",
            status_code=302
        )

    quotations = (
        db.query(Quotation)
        .filter(
            Quotation.client_id == client_id
        )
        .order_by(
            Quotation.created_at.desc()
        )
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="clients/client_history.html",
        context={
            "client": client,
            "quotations": quotations,
            "user": user,
        }
    )

@router.post("/{client_id}/edit")
async def update_client(
    client_id: int,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    ruc_ci: str = Form(""),
    company: str = Form(""),
    client_type: str = Form("Minorista"),
    observations: str = Form(""),
    db: Session = Depends(get_db),
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    try:

        client = db.query(Client).filter(Client.id == client_id).first()

        if not client:

            return RedirectResponse(url="/clients", status_code=302)
        # VALIDAR CÉDULA/RUC DUPLICADO

        existing_client = (
            db.query(Client)
            .filter(Client.ruc_ci == ruc_ci, Client.id != client_id)
            .first()
        )

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
                status_code=400,
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

        return RedirectResponse(url="/clients", status_code=302)

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
            status_code=500,
        )


@router.get("/{client_id}/delete")
async def delete_client(client_id: int, request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    try:

        client = db.query(Client).filter(Client.id == client_id).first()

        if client:

            db.delete(client)

            db.commit()

        return RedirectResponse(url="/clients", status_code=302)

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
            status_code=500,
        )


@router.post("/new")
async def create_client(
    request: Request,
    name: str = Form(...),
    company: str = Form(""),
    ruc_ci: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    client_type: str = Form(...),
    observations: str = Form(""),
    db: Session = Depends(get_db),
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    # =====================================
    # VALIDATE EXISTING CLIENT
    # =====================================

    existing_client = db.query(Client).filter(Client.ruc_ci == ruc_ci).first()
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
            status_code=400,
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
        observations=observations,
    )

    db.add(client)

    db.commit()

    try:
        log_activity(db, "Cliente creado", client.name or "Cliente sin nombre")
    except Exception:
        pass

    return RedirectResponse(url="/clients", status_code=302)

## clientes busqueda
@router.get("/search")
async def search_clients(request: Request, q: str = "", db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).filter(Client.name.ilike(f"%{q}%")).limit(10).all()

    return [
        {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "ruc_ci": client.ruc_ci,
            "email": client.email,
            "address": client.address,
        }
        for client in clients
    ]


@router.get("/catalog/modal")
async def client_catalog_modal(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).order_by(Client.name.asc()).limit(20).all()

    return templates.TemplateResponse(
        request=request,
        name="partials/client_catalog_table.html",
        context={"clients": clients},
    )
