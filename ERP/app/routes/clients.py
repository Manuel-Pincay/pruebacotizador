from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from datetime import datetime

from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.activity import log_activity
from app.auth.auth_handler import role_required
from app.utils.text_format import format_title_words
from app.utils.dialog_response import dialog_message_response

from app.models.client import Client
from app.models.quotation import Quotation
from app.models.production_order import ProductionOrder 

router = APIRouter(prefix="/clients", tags=["clients"])

templates = Jinja2Templates(directory="app/templates")

from app.config.settings import settings
from app.utils.pagination import build_page_url, paginate_query
from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["build_page_url"] = build_page_url


def _client_stats(db: Session) -> dict:
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "total": db.query(Client).count(),
        "mayoristas": db.query(Client).filter(Client.client_type == "mayorista").count(),
        "minoristas": db.query(Client).filter(Client.client_type == "minorista").count(),
        "new_this_month": db.query(Client).filter(Client.created_at >= month_start).count(),
    }


@router.get("/", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    stats = _client_stats(db)

    return templates.TemplateResponse(
        request=request,
        name="clients/list.html",
        context={
            **stats,
            "total_clients": stats["total"],
            "mayoristas_count": stats["mayoristas"],
            "minoristas_count": stats["minoristas"],
            "new_this_month": stats["new_this_month"],
            "user": user,
            "per_page": settings.per_page,
        },
    )


from fastapi.responses import JSONResponse


@router.get("/api/stats")
async def clients_stats_api(request: Request, db: Session = Depends(get_db)):
    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user
    return _client_stats(db)


@router.get("/api/list")
async def clients_api(
    request: Request,
    q: str = "",
    client_type: str = "",
    page: int = 1,
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    query = db.query(Client)

    if q:
        query = query.filter(Client.name.ilike(f"%{q}%"))

    if client_type:
        query = query.filter(Client.client_type == client_type)

    query = query.order_by(Client.name.asc())
    pagination = paginate_query(query, page, settings.per_page)

    return {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "company": c.company,
                "client_type": c.client_type,
            }
            for c in pagination["items"]
        ],
        "page": pagination["page"],
        "pages": pagination["pages"],
        "total": pagination["total"],
        "per_page": pagination["per_page"],
        "has_prev": pagination["has_prev"],
        "has_next": pagination["has_next"],
    }

@router.get("/new", response_class=HTMLResponse)
async def new_client_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user

    try:
        total_clients = db.query(Client).count()
    except Exception:
        total_clients = 0

    return templates.TemplateResponse(
        request=request,
        name="clients/new.html",
        context={
            "user": user,
            "total_clients": total_clients,
            "error": None,
            "form": {},
        },
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
        name="clients/edit.html",
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
        name="clients/history.html",
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

        ruc_ci = (ruc_ci or "").strip()

        # VALIDAR CÉDULA/RUC DUPLICADO

        existing_client = (
            db.query(Client)
            .filter(Client.ruc_ci == ruc_ci, Client.id != client_id)
            .first()
        )

        if existing_client:

            return dialog_message_response(
                f"Ya existe otro cliente con la cédula/RUC: {ruc_ci}",
                dialog_type="warning",
                title="Documento duplicado",
            )

        client.name = format_title_words(name)
        client.phone = (phone or "").strip()
        client.email = (email or "").strip().lower()
        client.address = format_title_words(address)
        client.ruc_ci = ruc_ci or None
        client.company = format_title_words(company) or None
        client.client_type = (client_type or "").strip()
        client.observations = (observations or "").strip()

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

    name = format_title_words(name)
    company = format_title_words(company)
    ruc_ci = (ruc_ci or "").strip()
    phone = (phone or "").strip()
    email = (email or "").strip().lower()
    address = format_title_words(address)
    client_type = (client_type or "minorista").strip()
    observations = (observations or "").strip()

    form_data = {
        "name": name,
        "company": company,
        "ruc_ci": ruc_ci,
        "phone": phone,
        "email": email,
        "address": address,
        "client_type": client_type,
        "observations": observations,
    }

    try:
        total_clients = db.query(Client).count()
    except Exception:
        total_clients = 0

    if ruc_ci:
        existing_client = db.query(Client).filter(Client.ruc_ci == ruc_ci).first()
        if existing_client:
            return templates.TemplateResponse(
                request=request,
                name="clients/new.html",
                context={
                    "user": user,
                    "total_clients": total_clients,
                    "error": f"Ya existe un cliente con la cédula/RUC: {ruc_ci}",
                    "form": form_data,
                },
                status_code=400,
            )

    client = Client(
        name=name,
        company=company or None,
        ruc_ci=ruc_ci or None,
        phone=phone or None,
        email=email or None,
        address=address or None,
        client_type=client_type,
        observations=observations or None,
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
        name="partials/clients/catalog_table.html",
        context={"clients": clients},
    )
