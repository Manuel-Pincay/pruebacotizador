from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime, timedelta
from sqlalchemy import func
from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.production_order import ProductionOrder
from app.models.company_config import CompanyConfig
from app.models.activity_log import ActivityLog
from app.services.fabrication_condensed_service import build_fabricator_dashboard
from app.services.production_helpers import (
    prepare_production_module,
    production_orders_base_query,
    build_dashboard_production_summary,
)

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config

DASHBOARD_ACTIVITY_LIMIT = 5
VENTAS_RECENT_QUOTATIONS_LIMIT = 10


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas", "produccion"])

    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)

    # defaults / fallbacks
    total_clients = 0
    total_products = 0
    total_quotations = 0
    production_pending = 0
    recent_quotations = []
    recent_products = []
    recent_production_items = []
    production_summary = {
        "active_count": 0,
        "overdue": 0,
        "due_today": 0,
        "due_this_week": 0,
        "urgent": 0,
        "recent_items": [],
        "table_items": [],
    }
    recent_activity = []
    company_name = "SISTEMA ERP"
    quotation_status_summary = []
    today = date.today()

    try:
        total_clients = db.query(Client).count()
    except Exception as e:
        print("DASHBOARD ERROR total_clients:", str(e))
        total_clients = 0

    try:
        total_products = db.query(Product).count()
    except Exception as e:
        print("DASHBOARD ERROR total_products:", str(e))
        total_products = 0

    try:
        total_quotations = db.query(Quotation).count()
    except Exception as e:
        print("DASHBOARD ERROR total_quotations:", str(e))
        total_quotations = 0

    try:
        production_pending = (
            production_orders_base_query(db)
            .filter(
                ProductionOrder.status.in_(
                    ["pendiente", "diseno", "diseño", "produccion", "envio", "enviado"]
                )
            )
            .count()
        )
    except Exception as e:
        print("DASHBOARD ERROR production_pending:", str(e))
        production_pending = 0

    try:
        recent_quotations = (
            db.query(Quotation)
            .options(joinedload(Quotation.client))
            .order_by(Quotation.id.desc())
            .limit(5)
            .all()
        )
    except Exception as e:
        print("DASHBOARD ERROR recent_quotations:", str(e))
        recent_quotations = []

    try:
        recent_products = db.query(Product).order_by(Product.id.desc()).limit(5).all()
    except Exception as e:
        print("DASHBOARD ERROR recent_products:", str(e))
        recent_products = []

    try:
        production_summary = build_dashboard_production_summary(db)
        recent_production_items = production_summary["recent_items"]
    except Exception as e:
        print("DASHBOARD ERROR production_summary:", str(e))
        production_summary = {
            "active_count": 0,
            "overdue": 0,
            "due_today": 0,
            "due_this_week": 0,
            "urgent": 0,
            "recent_items": [],
            "table_items": [],
        }
        recent_production_items = []

    try:
        status_rows = (
            db.query(Quotation.status, func.count(Quotation.id))
            .group_by(Quotation.status)
            .all()
        )
        quotation_status_summary = [
            {"status": (status or "—"), "count": count}
            for status, count in status_rows
            if count
        ]
        quotation_status_summary.sort(key=lambda row: row["count"], reverse=True)
    except Exception as e:
        print("DASHBOARD ERROR quotation_status_summary:", str(e))
        quotation_status_summary = []

    try:
        config = db.query(CompanyConfig).first()
        company_name = config.company_name if config else "SISTEMA ERP"
    except Exception as e:
        print("DASHBOARD ERROR config:", str(e))
        company_name = "SISTEMA ERP"

    try:
        recent_activity = db.query(
            ActivityLog
        ).order_by(
            ActivityLog.id.desc()
        ).limit(DASHBOARD_ACTIVITY_LIMIT).all()
    except Exception as e:
        print("DASHBOARD ERROR recent_activity:", str(e))
        recent_activity = []

    role = (user.role or "").lower()
    fab_dash = None

    if role == "ventas":
        try:
            recent_quotations = (
                db.query(Quotation)
                .options(joinedload(Quotation.client))
                .order_by(Quotation.id.desc())
                .limit(VENTAS_RECENT_QUOTATIONS_LIMIT)
                .all()
            )
        except Exception as e:
            print("DASHBOARD ERROR recent_quotations ventas:", str(e))
            recent_quotations = []

        approved_quotations = db.query(Quotation).filter(Quotation.status == "aprobada").count()
        pending_quotations = db.query(Quotation).filter(Quotation.status == "pendiente").count()

        dashboard_cards = [
            {"title": "Clientes", "value": total_clients, "icon": "👥", "color": "purple"},
            {"title": "Cotizaciones", "value": total_quotations, "icon": "📄", "color": "green"},
            {"title": "Pendientes", "value": pending_quotations, "icon": "⏳", "color": "yellow"},
            {"title": "Aprobadas", "value": approved_quotations, "icon": "✅", "color": "teal"},
        ]

        quick_actions = [
            {"title": "Nuevo Cliente", "url": "/clients/new", "icon": "👤"},
            {"title": "Nueva Cotización", "url": "/quotations/new", "icon": "📄"},
            {"title": "Seguimiento", "url": "/quotations/tracking", "icon": "📈"},
            {"title": "Clientes", "url": "/clients", "icon": "👥"},
        ]
    elif role == "produccion":
        fab_dash = build_fabricator_dashboard(db, user)

        dashboard_cards = [
            {"title": "Pendientes", "value": fab_dash["pending_count"], "icon": "⏳", "color": "orange"},
            {"title": "Ya realizadas", "value": fab_dash["done_count"], "icon": "✅", "color": "green"},
        ]

        quick_actions = [
            {"title": "Condensado Fabricación", "url": "/production/fabrication-condensed", "icon": "🖨️"},
            {"title": "Kanban", "url": "/production/kanban", "icon": "📋"},
        ]
    else:
        dashboard_cards = [
            {"title": "Clientes", "value": total_clients, "icon": "👥", "color": "purple"},
            {"title": "Productos", "value": total_products, "icon": "📦", "color": "blue"},
            {
                "title": "Cotizaciones",
                "value": total_quotations,
                "icon": "📄",
                "color": "green",
            },
            {
                "title": "Producción",
                "value": production_pending,
                "icon": "🏭",
                "color": "red",
            },
        ]

        quick_actions = [
            {"title": "Nuevo Cliente", "url": "/clients/new", "icon": "👤"},
            {"title": "Nuevo Producto", "url": "/products/new", "icon": "📦"},
            {"title": "Nueva Cotización", "url": "/quotations/new", "icon": "📄"},
            {"title": "Kanban", "url": "/production/kanban", "icon": "📋"},
            {"title": "Calendario", "url": "/production/calendar", "icon": "📅"},
            {"title": "Producción", "url": "/production/", "icon": "🏭"},
        ]
    # CHART LAST 30 DAYS

    chart_labels = []
    chart_values = []

    if role not in ("produccion", "ventas", "admin"):
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            total = db.query(
                Quotation
            ).filter(
                func.date(
                    Quotation.created_at
                ) == day
            ).count()

            chart_labels.append(
                day.strftime("%d/%m")
            )

            chart_values.append(total)

    chart_total = sum(chart_values)

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "total_clients": total_clients,
            "total_products": total_products,
            "total_quotations": total_quotations,
            "production_pending": production_pending,
            "recent_quotations": recent_quotations,
            "company_name": company_name,
            "dashboard_cards": dashboard_cards,
            "quick_actions": quick_actions,
            "user": user,
            "role": role,
            "recent_products": recent_products,
            "recent_production_items": recent_production_items,
            "production_summary": production_summary,
            "recent_activity": recent_activity,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "chart_total": chart_total,
            "quotation_status_summary": quotation_status_summary,
            "today": today,
            "fab_dash": fab_dash,
        },
    )
