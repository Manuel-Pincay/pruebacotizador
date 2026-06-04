from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
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

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas", "produccion"])

    if isinstance(user, RedirectResponse):
        return user

    # defaults / fallbacks
    total_clients = 0
    total_products = 0
    total_quotations = 0
    production_pending = 0
    recent_quotations = []
    recent_products = []
    recent_production = []
    recent_activity = []
    company_name = "SISTEMA ERP"

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
            db.query(ProductionOrder)
            .filter(
                ProductionOrder.status.in_(
                    ["pendiente", "diseño", "produccion", "empacado"]
                )
            )
            .count()
        )
    except Exception as e:
        print("DASHBOARD ERROR production_pending:", str(e))
        production_pending = 0

    try:
        recent_quotations = db.query(Quotation).order_by(Quotation.id.desc()).limit(5).all()
    except Exception as e:
        print("DASHBOARD ERROR recent_quotations:", str(e))
        recent_quotations = []

    try:
        recent_products = db.query(Product).order_by(Product.id.desc()).limit(5).all()
    except Exception as e:
        print("DASHBOARD ERROR recent_products:", str(e))
        recent_products = []

    try:
        recent_production = (
            db.query(ProductionOrder).order_by(ProductionOrder.id.desc()).limit(5).all()
        )
    except Exception as e:
        print("DASHBOARD ERROR recent_production:", str(e))
        recent_production = []

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
        ).limit(10).all()
    except Exception as e:
        print("DASHBOARD ERROR recent_activity:", str(e))
        recent_activity = []

    role = (user.role or "").lower()

    if role == "ventas":
        approved_quotations = db.query(Quotation).filter(Quotation.status == "aprobada").count()
        estimated_sales = db.query(Quotation).filter(
            Quotation.status.in_(
                ["aprobada", "produccion", "enviada", "enviado", "entregada", "entregado"]
            )
        ).all()
        estimated_value = sum(q.total or 0 for q in estimated_sales)

        dashboard_cards = [
            {"title": "Clientes", "value": total_clients, "icon": "👥", "color": "purple"},
            {"title": "Cotizaciones", "value": total_quotations, "icon": "📄", "color": "green"},
            {"title": "Ventas estimadas", "value": estimated_value, "icon": "💰", "color": "blue"},
            {"title": "Cotizaciones aprobadas", "value": approved_quotations, "icon": "✅", "color": "teal"},
        ]

        quick_actions = [
            {"title": "Nuevo Cliente", "url": "/clients/new", "icon": "👤"},
            {"title": "Nueva Cotización", "url": "/quotations/new", "icon": "📄"},
            {"title": "Productos", "url": "/products", "icon": "📦"},
            {"title": "Cotizaciones", "url": "/quotations", "icon": "📑"},
        ]
    elif role == "produccion":
        pending_count = db.query(ProductionOrder).filter(ProductionOrder.status == "pendiente").count()
        in_production_count = db.query(ProductionOrder).filter(
            ProductionOrder.status.in_(["diseño", "produccion"])
        ).count()
        finished_count = db.query(ProductionOrder).filter(ProductionOrder.status == "empacado").count()
        delivered_count = db.query(ProductionOrder).filter(ProductionOrder.status == "entregado").count()

        dashboard_cards = [
            {"title": "Pendientes", "value": pending_count, "icon": "⏳", "color": "purple"},
            {"title": "En Producción", "value": in_production_count, "icon": "🏭", "color": "blue"},
            {"title": "Terminadas", "value": finished_count, "icon": "✅", "color": "green"},
            {"title": "Entregadas", "value": delivered_count, "icon": "🚚", "color": "red"},
        ]

        quick_actions = [
            {"title": "Órdenes de Producción", "url": "/production/", "icon": "🗂️"},
            {"title": "Kanban", "url": "/production/kanban", "icon": "📋"},
            {"title": "Calendario", "url": "/production/calendar", "icon": "🗓️"},
            {"title": "Últimos pedidos", "url": "/production/", "icon": "📦"},
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
            {"title": "Producción", "url": "/production/", "icon": "🏭"},
        ]
    # =====================================
# CHART LAST 30 DAYS
# =====================================

    last_30_days = []

    chart_labels = []

    chart_values = []

    for i in range(29, -1, -1):

        day = date.today() - timedelta(days=i)

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

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
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
            "recent_products": recent_products,
            "recent_production": recent_production,
            "recent_activity": recent_activity,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
        },
    )
