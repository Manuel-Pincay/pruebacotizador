from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from datetime import date, datetime, time
from collections import defaultdict

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.shipment import Shipment

router = APIRouter(
    prefix="/production",
    tags=["production"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


# =========================================
# LISTADO PRODUCCIÓN
# =========================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def production_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "produccion"]
    )

    if isinstance(user, RedirectResponse):
        return user

    orders = db.query(
    ProductionOrder
    ).order_by(
        ProductionOrder.delivery_date.asc()
    ).all()

    active_orders_count = db.query(ProductionOrder).filter(
        ProductionOrder.status != "entregado"
    ).count()

    urgent_orders_count = db.query(ProductionOrder).filter(
        ProductionOrder.priority == "alta"
    ).count()

    overdue_orders_count = db.query(ProductionOrder).filter(
        ProductionOrder.delivery_date != None,
        ProductionOrder.delivery_date < datetime.utcnow(),
        ProductionOrder.status != "entregado"
    ).count()

    return templates.TemplateResponse(
        request=request,
        name="production.html",
        context={
            "orders": orders,
            "active_orders_count": active_orders_count,
            "urgent_orders_count": urgent_orders_count,
            "overdue_orders_count": overdue_orders_count,
            "user": user,
        }
    )


# =========================================
# KANBAN
# =========================================
@router.get(
    "/kanban",
    response_class=HTMLResponse
)
async def production_kanban(
    request: Request,
    db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "produccion"])

    if isinstance(user, RedirectResponse):
        return user

    pending = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "pendiente"
    ).all()

    designing = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "diseño"
    ).all()

    producing = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "produccion"
    ).all()

    packed = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "empacado"
    ).all()

    shipped = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "enviado"
    ).all()

    delivered = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "entregado"
    ).all()

    today_start = datetime.combine(date.today(), time.min)

    pending_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "pendiente",
        ProductionOrder.created_at >= today_start
    ).count()

    designing_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "diseño",
        ProductionOrder.created_at >= today_start
    ).count()

    producing_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "produccion",
        ProductionOrder.created_at >= today_start
    ).count()

    packed_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "empacado",
        ProductionOrder.created_at >= today_start
    ).count()

    shipped_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "enviado",
        ProductionOrder.created_at >= today_start
    ).count()

    delivered_today = db.query(ProductionOrder).filter(
        ProductionOrder.status == "entregado",
        ProductionOrder.created_at >= today_start
    ).count()

    active_orders_count = (
        len(pending) + len(designing) + len(producing) + len(packed) + len(shipped)
    )

    urgent_orders_count = db.query(ProductionOrder).filter(
        ProductionOrder.priority == "alta"
    ).count()

    overdue_orders_count = db.query(ProductionOrder).filter(
        ProductionOrder.delivery_date != None,
        ProductionOrder.delivery_date < datetime.utcnow(),
        ProductionOrder.status != "entregado"
    ).count()

    return templates.TemplateResponse(
        request=request,
        name="production_kanban.html",
        context={
            "pending": pending,
            "designing": designing,
            "producing": producing,
            "packed": packed,
            "shipped": shipped,
            "delivered": delivered,
            "active_orders_count": active_orders_count,
            "urgent_orders_count": urgent_orders_count,
            "overdue_orders_count": overdue_orders_count,
            "pending_today": pending_today,
            "designing_today": designing_today,
            "producing_today": producing_today,
            "packed_today": packed_today,
            "shipped_today": shipped_today,
            "delivered_today": delivered_today,
            "today": date.today(),
            "user": user,
        }
    )

# =========================================
# CALENDARIO PRODUCCIÓN
# =========================================

@router.get(
    "/calendar",
    response_class=HTMLResponse
)
async def production_calendar(
    request: Request,
    db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "produccion"])

    if isinstance(user, RedirectResponse):
        return user

    # Query params: view=upcoming|completed|all, status filter, start_date, end_date
    view: str = request.query_params.get("view", "upcoming")
    status: str = request.query_params.get("status", "")
    start_date: str = request.query_params.get("start_date", "")
    end_date: str = request.query_params.get("end_date", "")

    query = db.query(Quotation).filter(Quotation.delivery_date != None)

    # Exclude canceled quotations by default
    query = query.filter(~Quotation.status.in_(
        ["cancelada", "cancelado"]
    ))

    today_date = date.today()

    if view == "upcoming":
        query = query.filter(Quotation.delivery_date >= today_date)
        # For upcoming view, exclude already sent or delivered orders
        query = query.filter(~Quotation.status.in_(["enviada", "enviado", "entregada", "entregado"]))
    elif view == "completed":
        query = query.filter(Quotation.status.in_(["enviada", "enviado", "entregada", "entregado"]))
    # else 'all' -> no extra filter

    # status filter can accept comma separated values
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        expanded = set()
        for s in statuses:
            if s in ("enviada", "enviado"):
                expanded.update(["enviada", "enviado"])
            elif s in ("entregada", "entregado"):
                expanded.update(["entregada", "entregado"])
            else:
                expanded.add(s)
        query = query.filter(Quotation.status.in_(list(expanded)))

    # date range filters
    try:
        if start_date:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Quotation.delivery_date >= sd)
        if end_date:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Quotation.delivery_date <= ed)
    except Exception:
        pass

    quotations = query.order_by(Quotation.delivery_date.asc()).all()

    grouped_orders = defaultdict(list)
    for quotation in quotations:
        grouped_orders[quotation.delivery_date].append(quotation)

    # counts
    upcoming_count = db.query(Quotation).filter(
        Quotation.delivery_date >= today_date,
        ~Quotation.status.in_(["enviada", "enviado", "entregada", "entregado", "cancelada", "cancelado"])
    ).count()
    completed_count = db.query(Quotation).filter(Quotation.status.in_(
        ["enviada", "enviado", "entregada", "entregado"]
    )).count()

    return templates.TemplateResponse(
        request=request,
        name="production_calendar.html",
        context={
            "grouped_orders": dict(grouped_orders),
            "today": today_date,
            "view": view,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "upcoming_count": upcoming_count,
            "completed_count": completed_count,
            "user": user,
        }
    )

# =========================================
# CAMBIO DE ESTADO
# =========================================

@router.get("/move/{order_id}/{status}")
async def move_order(
    order_id: int,
    status: str,
    db: Session = Depends(get_db)
):

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    if not order:
        return RedirectResponse(url="/production/kanban", status_code=302)

    if status == "diseño" and not order.designer:
        return HTMLResponse(
            content="<script>alert('Asigna un diseñador antes de pasar a Diseño.'); window.history.back();</script>",
            status_code=400
        )

    if status == "produccion" and not order.designer:
        return HTMLResponse(
            content="<script>alert('La orden debe tener un diseñador asignado antes de pasar a Producción.'); window.history.back();</script>",
            status_code=400
        )

    if status == "empacado" and not order.fabricator:
        return HTMLResponse(
            content="<script>alert('Asigna un fabricador antes de pasar a Empacado.'); window.history.back();</script>",
            status_code=400
        )

    if status == "enviado":
        shipment = db.query(Shipment).filter(Shipment.quotation_id == order.quotation_id).first()
        if not shipment:
            return HTMLResponse(
                content=f"<script>alert('Crea la guía de envío antes de marcar como Enviado.'); window.location.href = '/shipments/new/{order.quotation_id}';</script>",
                status_code=400
            )

    order.status = status

    db.commit()

    return RedirectResponse(
        url="/production/kanban",
        status_code=302
    )
# =========================================
# ACTUALIZAR ORDEN
# =========================================

@router.post(
    "/{order_id}/update/"
)
async def update_production(
    order_id: int,
    designer: str = Form(""),
    fabricator: str = Form(""),
    priority: str = Form("media"),
    observations: str = Form(""),
    status: str = Form("pendiente"),
    db: Session = Depends(get_db)
):

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    if not order:
        return RedirectResponse(url="/production/kanban", status_code=302)

    if status == "diseño" and not designer:
        return HTMLResponse(
            content="<script>alert('Asigna un diseñador antes de mover la orden a Diseño.'); window.history.back();</script>",
            status_code=400
        )

    if status == "produccion" and not designer:
        return HTMLResponse(
            content="<script>alert('La orden debe tener un diseñador asignado antes de pasar a Producción.'); window.history.back();</script>",
            status_code=400
        )

    if status == "empacado" and not fabricator:
        return HTMLResponse(
            content="<script>alert('Asigna un fabricador antes de pasar a Empacado.'); window.history.back();</script>",
            status_code=400
        )

    if status == "enviado":
        shipment = db.query(Shipment).filter(Shipment.quotation_id == order.quotation_id).first()
        if not shipment:
            return HTMLResponse(
                content=f"<script>alert('Crea la guía de envío antes de marcar como Enviado.'); window.location.href = '/shipments/new/{order.quotation_id}';</script>",
                status_code=400
            )

    order.designer = designer
    order.fabricator = fabricator
    order.priority = priority
    order.observations = observations
    order.status = status

    db.commit()

    return RedirectResponse(
        url=f"/production/{order_id}",
        status_code=302
    )


# =========================================
# DETALLE ORDEN
# =========================================

@router.get(
    "/{order_id}",
    response_class=HTMLResponse
)
async def production_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "produccion"]
    )

    if isinstance(user, RedirectResponse):
        return user

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    shipment = None
    if order:
        shipment = db.query(Shipment).filter(Shipment.quotation_id == order.quotation_id).order_by(Shipment.id.desc()).first()

    return templates.TemplateResponse(
        request=request,
        name="production_detail.html",
        context={
            "order": order,
            "shipment": shipment
        }
    )
