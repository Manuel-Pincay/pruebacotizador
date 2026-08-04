from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.database import get_db
from app.models.quotation import Quotation
from app.models.quotation_payment import QuotationPayment
from app.utils.context import get_global_config

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config


def _require_reports(request: Request):
    return role_required(request, ["admin", "ventas"])


@router.get("/receivables", response_class=HTMLResponse)
async def receivables_report(request: Request, db: Session = Depends(get_db)):
    user = _require_reports(request)
    if isinstance(user, RedirectResponse):
        return user

    quotations = (
        db.query(Quotation)
        .options(joinedload(Quotation.client), joinedload(Quotation.payments))
        .filter(~Quotation.status.in_(["cancelada", "vencida"]))
        .order_by(Quotation.created_at.desc())
        .all()
    )

    rows = []
    total_pending = 0.0
    by_client: dict[int, dict] = {}

    for q in quotations:
        pending = float(q.pending_balance or 0)
        if pending <= 0.01:
            continue
        total_pending += pending
        client = q.client
        client_id = q.client_id or 0
        if client_id not in by_client:
            by_client[client_id] = {
                "client": client,
                "pending": 0.0,
                "quotations": [],
            }
        by_client[client_id]["pending"] += pending
        by_client[client_id]["quotations"].append(q)
        rows.append(q)

    clients_summary = sorted(
        by_client.values(),
        key=lambda x: x["pending"],
        reverse=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="reports/receivables.html",
        context={
            "user": user,
            "rows": rows,
            "clients_summary": clients_summary,
            "total_pending": total_pending,
            "count": len(rows),
        },
    )


@router.get("/sales", response_class=HTMLResponse)
async def sales_report(
    request: Request,
    db: Session = Depends(get_db),
    start_date: str = "",
    end_date: str = "",
):
    user = _require_reports(request)
    if isinstance(user, RedirectResponse):
        return user

    today = datetime.utcnow().date()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today.replace(day=1)
    except ValueError:
        start = today.replace(day=1)
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    except ValueError:
        end = today

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    query = (
        db.query(Quotation)
        .options(joinedload(Quotation.client), joinedload(Quotation.payments))
        .filter(
            Quotation.created_at >= start_dt,
            Quotation.created_at <= end_dt,
            ~Quotation.status.in_(["cancelada", "vencida"]),
        )
    )
    quotations = query.order_by(Quotation.created_at.desc()).all()

    total_sales = sum(float(q.total or 0) for q in quotations)
    total_collected = sum(float(q.total_paid or 0) for q in quotations)
    by_status: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
    by_client: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
    by_month: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "total": 0.0, "collected": 0.0, "label": ""}
    )
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    for q in quotations:
        st = (q.status or "sin_estado").lower()
        by_status[st]["count"] += 1
        by_status[st]["total"] += float(q.total or 0)
        cname = q.client.name if q.client else "Sin cliente"
        by_client[cname]["count"] += 1
        by_client[cname]["total"] += float(q.total or 0)
        if q.created_at:
            month_key = q.created_at.strftime("%Y-%m")
            by_month[month_key]["count"] += 1
            by_month[month_key]["total"] += float(q.total or 0)
            by_month[month_key]["collected"] += float(q.total_paid or 0)
            by_month[month_key]["label"] = (
                f"{month_names.get(q.created_at.month, month_key)} {q.created_at.year}"
            )

    top_clients = sorted(by_client.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
    status_rows = sorted(by_status.items(), key=lambda x: x[1]["total"], reverse=True)
    month_rows = [
        {
            "key": key,
            "label": data["label"] or key,
            "count": data["count"],
            "total": data["total"],
            "collected": data["collected"],
        }
        for key, data in sorted(by_month.items())
    ]

    # Detalle agrupado por mes (más reciente primero)
    quotations_by_month: list[dict] = []
    grouped: dict[str, list] = defaultdict(list)
    for q in quotations:
        key = q.created_at.strftime("%Y-%m") if q.created_at else "sin-fecha"
        grouped[key].append(q)
    for key in sorted(grouped.keys(), reverse=True):
        label = next((m["label"] for m in month_rows if m["key"] == key), key)
        month_total = sum(float(q.total or 0) for q in grouped[key])
        quotations_by_month.append(
            {"key": key, "label": label, "total": month_total, "items": grouped[key]}
        )

    payments_in_range = (
        db.query(func.coalesce(func.sum(QuotationPayment.amount), 0))
        .filter(
            QuotationPayment.payment_date >= start_dt,
            QuotationPayment.payment_date <= end_dt,
        )
        .scalar()
    )

    return templates.TemplateResponse(
        request=request,
        name="reports/sales.html",
        context={
            "user": user,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "quotations": quotations,
            "quotations_by_month": quotations_by_month,
            "total_sales": total_sales,
            "total_collected": total_collected,
            "payments_in_range": float(payments_in_range or 0),
            "count": len(quotations),
            "top_clients": top_clients,
            "status_rows": status_rows,
            "month_rows": month_rows,
        },
    )
