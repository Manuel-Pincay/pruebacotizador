import json
import re
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.auth.security import verify_admin_password
from app.database import get_db
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.product import Product
from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.quotation_payment import QuotationPayment
from app.models.shipment import Shipment
from app.models.quotation_design import QuotationDesign
from app.models.production_tracking import ProductionTracking
from app.models.design_observation import DesignObservation
from app.models.design_tracking import DesignTracking
from app.models.production_order_history import ProductionOrderHistory
from app.services.logo_types import (
    LOGO_TYPE_SIN,
    normalize_logo_type,
    register_logo_template_globals,
    resolve_item_logo_type,
)
from app.services.production_helpers import ensure_production_order, cancel_stale_pending_quotations
from app.services.product_service import (
    create_custom_product_from_quotation,
    resolve_custom_product_id,
    sync_product_image,
)
from app.services.quotation_service import compute_item_total, recalculate_quotation
from app.services.quotation_design_service import (
    MAX_QUOTATION_DESIGNS,
    DesignLimitError,
    add_design_image,
    delete_design_image,
    get_design_urls,
    sync_legacy_design_file,
)
from app.utils.activity import log_activity
from app.utils.context import get_global_config
from app.utils.pdf import generate_quotation_pdf
from app.utils.status_helpers import COMPLETED_STATUSES, expand_status_filter
from app.config.settings import settings
from app.utils.pagination import build_page_url, paginate_query
from app.utils.image_storage import (
    UploadValidationError,
    delete_payment_receipt,
    delete_design_file,
    delete_product_files,
    design_image_url,
    read_upload_bytes,
    save_product_image,
    validate_upload_filename,
    payment_receipt_url,
    is_payment_receipt_pdf,
    is_payment_receipt_image,
    product_image_url,
)

router = APIRouter(prefix="/quotations", tags=["quotations"])

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["build_page_url"] = build_page_url
templates.env.globals["design_image_url"] = design_image_url
templates.env.globals["payment_receipt_url"] = payment_receipt_url
templates.env.globals["is_payment_receipt_pdf"] = is_payment_receipt_pdf
templates.env.globals["is_payment_receipt_image"] = is_payment_receipt_image
templates.env.globals["product_image_url"] = product_image_url
register_logo_template_globals(templates.env)

QUOTATION_ROLES = ["admin", "ventas"]


def _purge_quotation(db: Session, quotation: Quotation) -> None:
    """Elimina registros ligados y archivos antes de borrar la cotización."""
    design_filenames: set[str] = set()

    payments = (
        db.query(QuotationPayment)
        .filter(QuotationPayment.quotation_id == quotation.id)
        .all()
    )
    for payment in payments:
        delete_payment_receipt(payment.transfer_receipt)
    db.query(QuotationPayment).filter(
        QuotationPayment.quotation_id == quotation.id
    ).delete(synchronize_session=False)

    designs = (
        db.query(QuotationDesign)
        .filter(QuotationDesign.quotation_id == quotation.id)
        .all()
    )
    for design in designs:
        if design.filename:
            design_filenames.add(design.filename)
            delete_design_file(design.filename)
    db.query(QuotationDesign).filter(
        QuotationDesign.quotation_id == quotation.id
    ).delete(synchronize_session=False)

    if quotation.design_file and quotation.design_file not in design_filenames:
        delete_design_file(quotation.design_file)

    items = (
        db.query(QuotationItem)
        .filter(QuotationItem.quotation_id == quotation.id)
        .all()
    )
    item_ids = [item.id for item in items]

    production_orders = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.quotation_id == quotation.id)
        .all()
    )
    for order in production_orders:
        design_name = (order.design_file_name or "").strip()
        if design_name and design_name not in design_filenames:
            delete_design_file(design_name)

    for item in items:
        image_name = (item.product_image or "").strip()
        if not image_name:
            continue
        used_by_product = (
            db.query(Product.id)
            .filter(Product.image == image_name)
            .first()
        )
        if used_by_product:
            continue
        used_by_other_item = (
            db.query(QuotationItem.id)
            .filter(
                QuotationItem.product_image == image_name,
                QuotationItem.quotation_id != quotation.id,
            )
            .first()
        )
        if used_by_other_item:
            continue
        delete_product_files(image_name)

    if item_ids:
        tracking_ids = [
            row[0]
            for row in db.query(DesignTracking.id)
            .filter(DesignTracking.quotation_item_id.in_(item_ids))
            .all()
        ]
        if tracking_ids:
            db.query(DesignObservation).filter(
                DesignObservation.design_tracking_id.in_(tracking_ids)
            ).delete(synchronize_session=False)
        db.query(DesignTracking).filter(
            DesignTracking.quotation_item_id.in_(item_ids)
        ).delete(synchronize_session=False)
        db.query(ProductionTracking).filter(
            ProductionTracking.quotation_item_id.in_(item_ids)
        ).delete(synchronize_session=False)

    db.query(ProductionTracking).filter(
        ProductionTracking.quotation_id == quotation.id
    ).delete(synchronize_session=False)
    db.query(Shipment).filter(
        Shipment.quotation_id == quotation.id
    ).delete(synchronize_session=False)

    order_ids = [order.id for order in production_orders]
    if order_ids:
        db.query(ProductionOrderHistory).filter(
            ProductionOrderHistory.production_order_id.in_(order_ids)
        ).delete(synchronize_session=False)
    db.query(ProductionOrder).filter(
        ProductionOrder.quotation_id == quotation.id
    ).delete(synchronize_session=False)

    db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation.id).delete(
        synchronize_session=False
    )
    db.delete(quotation)


def _normalize_product_id(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _item_image_from_form(request: Request, index: int) -> str | None:
    form = await request.form()
    upload = form.get(f"item_image_{index}")
    if not upload or not getattr(upload, "filename", None):
        return None
    try:
        validate_upload_filename(upload.filename)
        data = await read_upload_bytes(upload, 5 * 1024 * 1024)
        return save_product_image(data)
    except UploadValidationError:
        return None


def _add_items_to_quotation(
    db: Session,
    quotation: Quotation,
    items_data: list,
    item_images: dict[int, str | None],
) -> None:
    for idx, item in enumerate(items_data):
        image_name = item_images.get(idx)
        if not image_name:
            existing = (item.get("existing_image") or "").strip()
            if existing:
                image_name = existing
        product_id = resolve_custom_product_id(
            db,
            item_data=item,
            image=image_name,
        )
        if product_id is None:
            product_id = _normalize_product_id(item.get("product_id"))

        if image_name and product_id:
            sync_product_image(db, product_id, image_name)

        resolved_logo = normalize_logo_type(item.get("logo_type") or item.get("logo"))
        item_discount = float(item.get("item_discount") or item.get("discount") or 0)
        quantity = item.get("quantity", 1)
        unit_price = item.get("price", 0)
        line_total = item.get("total")
        if line_total is None:
            line_total = compute_item_total(quantity, unit_price, item_discount)
        db.add(
            QuotationItem(
                quotation_id=quotation.id,
                product_id=product_id,
                quantity=quantity,
                detail=item.get("detail", ""),
                measure=item.get("measure", ""),
                theme=item.get("theme", ""),
                color=item.get("color", ""),
                logo=resolved_logo != LOGO_TYPE_SIN,
                logo_type=resolved_logo,
                item_discount=item_discount,
                unit_price=unit_price,
                total=line_total,
                product_image=image_name,
            )
        )


def _require_quotation_access(request: Request):
    user = role_required(request, QUOTATION_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


def _quotation_counts(db: Session) -> dict:
    return {
        "total_quotations": db.query(Quotation).count(),
        "pending_quotations": db.query(Quotation).filter(Quotation.status == "pendiente").count(),
        "approved_quotations": db.query(Quotation).filter(Quotation.status == "aprobada").count(),
        "production_quotations": db.query(Quotation).filter(Quotation.status == "produccion").count(),
        "sent_quotations": db.query(Quotation).filter(
            Quotation.status.in_(["enviada", "enviado"])
        ).count(),
        "delivered_quotations": db.query(Quotation).filter(
            Quotation.status.in_(["entregada", "entregado"])
        ).count(),
        "cancelled_quotations": db.query(Quotation).filter(Quotation.status == "cancelada").count(),
    }


@router.get("/new", response_class=HTMLResponse)
async def new_quotation(request: Request, db: Session = Depends(get_db)):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).all()
    products = db.query(Product).all()
    config = db.query(CompanyConfig).first()

    return templates.TemplateResponse(
        request=request,
        name="quotations/new.html",
        context={"clients": clients, "products": products, "config": config, "user": user},
    )


@router.get("/", response_class=HTMLResponse)
async def quotations_page(
    request: Request,
    search: str = "",
    client_id: Optional[str] = None,
    status: str = "",
    delivery: str = "",
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    error: str = "",
    deleted: int = 0,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    cancel_stale_pending_quotations(db)

    query = db.query(Quotation).options(
        joinedload(Quotation.client),
        joinedload(Quotation.payments),
    )

    if search:
        query = query.join(Client).filter(Client.name.ilike(f"%{search}%"))

    if client_id and client_id.strip():
        query = query.filter(Quotation.client_id == int(client_id))

    if status:
        query = query.filter(Quotation.status.in_(expand_status_filter(status)))

    if delivery == "entregada":
        query = query.filter(Quotation.status.in_(expand_status_filter("entregada,entregado")))
    elif delivery == "no_entregada":
        query = query.filter(
            ~Quotation.status.in_(expand_status_filter("entregada,entregado")),
            Quotation.status != "cancelada",
        )

    if start_date:
        query = query.filter(Quotation.created_at >= start_date)

    if end_date:
        query = query.filter(Quotation.created_at <= end_date)

    query = query.order_by(Quotation.created_at.desc(), Quotation.id.desc())
    pagination = paginate_query(query, page, settings.per_page)
    clients = db.query(Client).order_by(Client.name).all()
    counts = _quotation_counts(db)

    filter_params = {
        "search": search,
        "client_id": client_id or "",
        "status": status,
        "delivery": delivery,
        "start_date": start_date,
        "end_date": end_date,
    }

    return templates.TemplateResponse(
        request=request,
        name="quotations/list.html",
        context={
            "quotations": pagination["items"],
            "clients": clients,
            "search": search,
            "client_id": client_id,
            "status": status,
            "delivery": delivery,
            "start_date": start_date,
            "end_date": end_date,
            "error": error,
            "deleted": deleted,
            "user": user,
            "page": pagination["page"],
            "pages": pagination["pages"],
            "filtered_total": pagination["total"],
            "filter_params": filter_params,
            **counts,
        },
    )


@router.get("/completed", response_class=HTMLResponse)
async def completed_quotations_page(request: Request, db: Session = Depends(get_db)):
    return await quotations_page(
        request=request,
        search="",
        client_id=None,
        status=",".join(COMPLETED_STATUSES),
        start_date="",
        end_date="",
        db=db,
    )


@router.get("/tracking", response_class=HTMLResponse)
async def sales_tracking_page(request: Request, db: Session = Depends(get_db)):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    cancel_stale_pending_quotations(db)

    pipeline = [
        {"key": "pendiente", "label": "Pendientes", "count": db.query(Quotation).filter(Quotation.status == "pendiente").count()},
        {"key": "aprobada", "label": "Aprobadas", "count": db.query(Quotation).filter(Quotation.status == "aprobada").count()},
        {"key": "produccion", "label": "En producción", "count": db.query(Quotation).filter(Quotation.status == "produccion").count()},
        {"key": "enviada,enviado", "label": "Enviadas", "count": db.query(Quotation).filter(Quotation.status.in_(["enviada", "enviado"])).count()},
        {"key": "entregada,entregado", "label": "Entregadas", "count": db.query(Quotation).filter(Quotation.status.in_(["entregada", "entregado"])).count()},
        {"key": "cancelada", "label": "Canceladas", "count": db.query(Quotation).filter(Quotation.status == "cancelada").count()},
    ]

    active_quotations = (
        db.query(Quotation)
        .options(joinedload(Quotation.client))
        .filter(~Quotation.status.in_(["cancelada", "entregada", "entregado"]))
        .order_by(Quotation.created_at.desc(), Quotation.id.desc())
        .limit(50)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="quotations/tracking.html",
        context={
            "pipeline": pipeline,
            "active_quotations": active_quotations,
            "user": user,
        },
    )


@router.get("/catalog")
async def product_catalog(
    request: Request,
    q: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    per_page = 10
    query = db.query(Product)

    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    total = query.count()
    products = query.offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        request=request,
        name="partials/products/catalog_table.html",
        context={"products": products, "page": page, "total": total},
    )


@router.post("/create")
async def create_quotation(
    request: Request,
    client_id: int = Form(...),
    subtotal: float = Form(...),
    discount: float = Form(...),
    delivery_date: str = Form(None),
    iva: float = Form(...),
    total: float = Form(...),
    shipping_cost: float = Form(0),
    items: str = Form(...),
    design_file: UploadFile = File(None),
    design_files: Annotated[list[UploadFile], File()] = [],
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return JSONResponse(
                status_code=400,
                content={"message": "El cliente seleccionado no existe."},
            )

        items_data = json.loads(items)
        if not items_data:
            return JSONResponse(
                status_code=400,
                content={"message": "Agrega al menos un producto a la cotización."},
            )

        parsed_delivery_date = None
        if delivery_date:
            parsed_delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()

        filename = None
        uploads: list[UploadFile] = []
        if design_file and design_file.filename:
            uploads.append(design_file)
        for upload in design_files:
            if upload.filename:
                uploads.append(upload)
        uploads = uploads[:MAX_QUOTATION_DESIGNS]

        quotation = Quotation(
            client_id=client_id,
            subtotal=subtotal,
            discount=discount,
            delivery_date=parsed_delivery_date,
            iva=iva,
            total=total,
            shipping_cost=shipping_cost or 0,
            design_file=None,
            status="pendiente",
        )

        db.add(quotation)
        db.flush()

        for upload in uploads:
            try:
                validate_upload_filename(upload.filename)
                data = await read_upload_bytes(upload, 10 * 1024 * 1024)
                design = add_design_image(db, quotation, data)
                if not filename:
                    filename = design.filename
            except (UploadValidationError, DesignLimitError) as exc:
                db.rollback()
                return JSONResponse(
                    status_code=400,
                    content={"message": str(exc)},
                )

        if filename:
            quotation.design_file = filename

        item_images: dict[int, str | None] = {}
        for idx in range(len(items_data)):
            item_images[idx] = await _item_image_from_form(request, idx)

        _add_items_to_quotation(db, quotation, items_data, item_images)

        db.commit()

        try:
            log_activity(db, "Cotización creada", f"Cotización #{quotation.id}")
        except Exception:
            pass

        return RedirectResponse(url=f"/quotations/{quotation.id}", status_code=302)

    except json.JSONDecodeError:
        db.rollback()
        return JSONResponse(
            status_code=400,
            content={"message": "Los productos de la cotización no son válidos. Recarga la página e intenta de nuevo."},
        )
    except ValueError as e:
        db.rollback()
        if "does not match format" in str(e):
            message = "Fecha de entrega inválida."
        else:
            message = str(e)
        return JSONResponse(status_code=400, content={"message": message})
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "message": "No se pudo guardar la cotización. Revisa los datos e intenta de nuevo.",
                "detail": str(e),
            },
        )


@router.get("/quotation-items/{item_id}/edit", response_class=HTMLResponse)
async def edit_quotation_item(
    item_id: int, request: Request, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        return RedirectResponse("/quotations", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="partials/quotations/item_modal.html",
        context={"item": item},
    )


@router.post("/quotation-items/{item_id}/edit")
async def update_item(
    request: Request,
    item_id: int,
    quantity: int = Form(...),
    unit_price: float = Form(...),
    theme: str = Form(""),
    measure: str = Form(""),
    color: str = Form(""),
    logo_type: str = Form("sin_logo"),
    item_discount: float = Form(0),
    product_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        return RedirectResponse("/quotations", status_code=302)

    if quantity < 1:
        return RedirectResponse(url=f"/quotations/{item.quotation_id}", status_code=302)

    resolved_logo = normalize_logo_type(logo_type)
    item.item_discount = max(0.0, min(float(item_discount or 0), 100.0))
    item.quantity = quantity
    item.unit_price = unit_price
    item.total = compute_item_total(quantity, unit_price, item.item_discount)
    item.theme = theme
    item.measure = measure
    item.color = color
    item.logo_type = resolved_logo
    item.logo = resolved_logo != LOGO_TYPE_SIN

    if product_image and product_image.filename:
        try:
            validate_upload_filename(product_image.filename)
            data = await read_upload_bytes(product_image, 5 * 1024 * 1024)
            image_name = save_product_image(data)
            item.product_image = image_name
            sync_product_image(db, item.product_id, image_name)
        except UploadValidationError:
            pass

    db.commit()
    recalculate_quotation(item.quotation, db)
    return RedirectResponse(url=f"/quotations/{item.quotation_id}", status_code=302)


@router.get("/quotation-items/{item_id}/delete")
async def delete_item(
    request: Request, item_id: int, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        return RedirectResponse("/quotations", status_code=302)

    quotation = item.quotation
    db.delete(item)
    db.commit()
    recalculate_quotation(quotation, db)
    return RedirectResponse(f"/quotations/{quotation.id}", status_code=302)


@router.get("/quotation-items/{item_id}/modal", response_class=HTMLResponse)
async def quotation_item_modal(
    item_id: int, request: Request, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        return HTMLResponse("Item no encontrado", status_code=404)

    return templates.TemplateResponse(
        request=request, name="partials/quotations/item_modal.html", context={"item": item}
    )


@router.post("/quotation-items/{item_id}/update-quantity")
async def update_quantity(
    request: Request,
    item_id: int,
    quantity: int = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        return {"success": False}

    if quantity < 1:
        return {"success": False}

    item.quantity = quantity
    item.total = compute_item_total(
        item.quantity,
        item.unit_price,
        getattr(item, "item_discount", 0),
    )
    db.commit()
    recalculate_quotation(item.quotation, db)
    return {"success": True}


@router.get("/{quotation_id}", response_class=HTMLResponse)
async def quotation_detail(
    quotation_id: int, request: Request, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.items).joinedload(QuotationItem.product),
            joinedload(Quotation.payments),
            joinedload(Quotation.designs),
        )
        .filter(Quotation.id == quotation_id)
        .first()
    )

    if quotation:
        sync_legacy_design_file(db, quotation)
        db.commit()
        db.refresh(quotation)

    if quotation and quotation.payments:
        quotation.payments.sort(
            key=lambda payment: payment.payment_date or datetime.min,
            reverse=True,
        )

    return templates.TemplateResponse(
        request=request,
        name="quotations/detail.html",
        context={
            "quotation": quotation,
            "user": user,
            "design_urls": get_design_urls(quotation) if quotation else [],
            "max_designs": MAX_QUOTATION_DESIGNS,
            "designs_count": len(quotation.designs) if quotation else 0,
        },
    )


@router.get("/{quotation_id}/approve")
async def approve_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "pendiente":
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.status = "aprobada"
    ensure_production_order(db, quotation)
    db.commit()

    try:
        log_activity(db, "Cotización aprobada", f"Cotización #{quotation.id}")
    except Exception:
        pass

    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)


@router.get("/{quotation_id}/cancel")
async def cancel_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "pendiente":
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.status = "cancelada"
    db.query(ProductionOrder).filter(
        ProductionOrder.quotation_id == quotation.id
    ).delete(synchronize_session=False)
    db.commit()
    return RedirectResponse(url="/quotations", status_code=302)


@router.get("/{quotation_id}/delete")
async def delete_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    _purge_quotation(db, quotation)
    db.commit()
    return RedirectResponse(url="/quotations", status_code=302)


@router.post("/{quotation_id}/delete")
async def delete_quotation_with_password(
    request: Request,
    quotation_id: int,
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    if not verify_admin_password(admin_password):
        return RedirectResponse(
            url="/quotations/?error=clave_admin_incorrecta",
            status_code=302,
        )

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    _purge_quotation(db, quotation)
    db.commit()
    return RedirectResponse(url="/quotations/?deleted=1", status_code=302)


@router.get("/{quotation_id}/reactivate")
async def reactivate_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "cancelada":
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.status = "pendiente"
    db.query(ProductionOrder).filter(
        ProductionOrder.quotation_id == quotation.id
    ).delete(synchronize_session=False)
    db.commit()
    return RedirectResponse(url="/quotations", status_code=302)


@router.get("/{quotation_id}/edit", response_class=HTMLResponse)
async def edit_quotation_page(
    quotation_id: int, request: Request, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "pendiente":
        return RedirectResponse(url="/quotations", status_code=302)

    clients = db.query(Client).all()
    products = db.query(Product).all()
    config = db.query(CompanyConfig).first()
    items = db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation.id).all()

    items_json = []
    for item in items:
        is_custom = bool(item.product and item.product.custom)
        thumb = None
        if item.product_image:
            thumb = product_image_url(item.product_image, thumb=True)
        elif item.product and item.product.image:
            thumb = product_image_url(item.product.image, thumb=True)
        items_json.append(
            {
                "type": "custom" if is_custom else "inventory",
                "product_id": item.product_id,
                "quantity": item.quantity,
                "detail": item.detail,
                "measure": item.measure or "",
                "theme": item.theme or "",
                "color": item.color or "",
                "logo_type": resolve_item_logo_type(item),
                "item_discount": float(getattr(item, "item_discount", 0) or 0),
                "price": item.unit_price,
                "total": item.total,
                "existing_image": item.product_image or "",
                "existing_image_url": thumb or "",
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="quotations/new.html",
        context={
            "clients": clients,
            "products": products,
            "config": config,
            "quotation": quotation,
            "items_json": json.dumps(items_json),
            "edit_mode": True,
            "user": user,
        },
    )


@router.post("/{quotation_id}/edit")
async def update_quotation(
    request: Request,
    quotation_id: int,
    client_id: int = Form(...),
    subtotal: float = Form(...),
    discount: float = Form(...),
    iva: float = Form(...),
    total: float = Form(...),
    shipping_cost: float = Form(0),
    items: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "pendiente":
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.client_id = client_id
    quotation.subtotal = subtotal
    quotation.discount = discount
    quotation.iva = iva
    quotation.total = total
    quotation.shipping_cost = shipping_cost or 0

    db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation.id).delete()
    items_data = json.loads(items)

    item_images: dict[int, str | None] = {}
    for idx in range(len(items_data)):
        item_images[idx] = await _item_image_from_form(request, idx)

    _add_items_to_quotation(db, quotation, items_data, item_images)

    db.commit()
    return RedirectResponse(url=f"/quotations/{quotation.id}", status_code=302)


@router.post("/{quotation_id}/shipping-cost")
async def update_shipping_cost(
    request: Request,
    quotation_id: int,
    shipping_cost: float = Form(0),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.shipping_cost = shipping_cost or 0
    recalculate_quotation(quotation, db)
    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)


@router.get("/{quotation_id}/production")
async def production_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations/", status_code=302)

    order = ensure_production_order(db, quotation)
    db.commit()

    if order:
        from app.services.production_order_service import normalize_status

        stage = normalize_status(order.status)
        if stage in {"pendiente", "diseno"}:
            return RedirectResponse(url=f"/production/{order.id}", status_code=302)

    return RedirectResponse(url="/production/", status_code=302)


@router.get("/{quotation_id}/shipping")
async def shipping_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "despacho", "transporte", "ventas", "disenador"])
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quotation.status != "produccion":
        return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)

    quotation.status = "enviado"
    db.commit()
    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)


@router.get("/{quotation_id}/delivered")
async def delivered_quotation(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "despacho", "transporte", "ventas", "disenador"])
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    quotation.status = "entregado"
    db.commit()
    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)


@router.get("/{quotation_id}/pdf")
async def quotation_pdf(
    request: Request, quotation_id: int, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        quotation = (
            db.query(Quotation)
            .options(
                joinedload(Quotation.payments),
                joinedload(Quotation.designs),
            )
            .filter(Quotation.id == quotation_id)
            .first()
        )
        if not quotation:
            return HTMLResponse(content="<h1>Cotización no encontrada</h1>", status_code=404)

        items = (
            db.query(QuotationItem)
            .options(joinedload(QuotationItem.product))
            .filter(QuotationItem.quotation_id == quotation_id)
            .all()
        )
        client = db.query(Client).filter(Client.id == quotation.client_id).first()

        if not client:
            return HTMLResponse(content="<h1>Cliente no encontrado</h1>", status_code=404)

        pdf_buffer = generate_quotation_pdf(quotation, items, client, db)
        client_name = re.sub(r'[<>:"/\\|?*]', "", client.name or "Cliente")
        pdf_name = f"Cotizacion {quotation.id} - {client_name}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf_name}"'},
        )

    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Error generando PDF</h1><p>{str(e)}</p>",
            status_code=500,
        )


@router.get("/{quotation_id}/add-product-modal", response_class=HTMLResponse)
async def add_product_modal(
    quotation_id: int, request: Request, db: Session = Depends(get_db)
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    products = db.query(Product).order_by(Product.name).all()
    return templates.TemplateResponse(
        request=request,
        name="partials/quotations/add_product_modal.html",
        context={"quotation_id": quotation_id, "products": products},
    )


@router.post("/{quotation_id}/add-product")
async def add_product_to_quotation(
    request: Request,
    quotation_id: int,
    product_type: str = Form(...),
    product_id: int | None = Form(None),
    detail: str = Form(""),
    custom_price: float = Form(0),
    quantity: int = Form(...),
    theme: str = Form(""),
    measure: str = Form(""),
    color: str = Form(""),
    logo_type: str = Form("sin_logo"),
    item_discount: float = Form(0),
    product_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    if quantity < 1:
        return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)

    resolved_logo = normalize_logo_type(logo_type)
    line_discount = max(0.0, min(float(item_discount or 0), 100.0))

    image_name = None
    if product_image and product_image.filename:
        try:
            validate_upload_filename(product_image.filename)
            data = await read_upload_bytes(product_image, 5 * 1024 * 1024)
            image_name = save_product_image(data)
        except UploadValidationError:
            image_name = None

    if product_type == "catalogo":
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)

        item = QuotationItem(
            quotation_id=quotation.id,
            product_id=product.id,
            detail=product.name,
            quantity=quantity,
            theme=theme,
            measure=measure,
            color=color,
            logo=resolved_logo != LOGO_TYPE_SIN,
            logo_type=resolved_logo,
            item_discount=line_discount,
            unit_price=product.price,
            total=compute_item_total(quantity, product.price, line_discount),
        )
    else:
        custom_product = create_custom_product_from_quotation(
            db,
            name=detail,
            description=detail,
            color=color,
            size=measure,
            theme=theme,
            price=custom_price,
            image=image_name,
        )

        item = QuotationItem(
            quotation_id=quotation.id,
            product_id=custom_product.id if custom_product else None,
            detail=detail.strip(),
            quantity=quantity,
            theme=theme,
            measure=measure,
            color=color,
            logo=resolved_logo != LOGO_TYPE_SIN,
            logo_type=resolved_logo,
            item_discount=line_discount,
            unit_price=custom_price,
            total=compute_item_total(quantity, custom_price, line_discount),
            product_image=image_name,
        )

    db.add(item)
    db.commit()
    recalculate_quotation(quotation, db)
    return RedirectResponse(url=f"/quotations/{quotation.id}", status_code=302)


@router.post("/{quotation_id}/designs")
async def upload_quotation_design(
    quotation_id: int,
    request: Request,
    design_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return JSONResponse(status_code=404, content={"message": "Cotización no encontrada."})

    try:
        sync_legacy_design_file(db, quotation)
        validate_upload_filename(design_file.filename)
        data = await read_upload_bytes(design_file, 10 * 1024 * 1024)
        add_design_image(db, quotation, data)
        db.commit()
        return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)
    except (UploadValidationError, DesignLimitError, ValueError) as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.post("/{quotation_id}/designs/{design_id}/delete")
async def remove_quotation_design(
    quotation_id: int,
    design_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/quotations", status_code=302)

    try:
        delete_design_image(db, quotation, design_id)
        db.commit()
    except ValueError:
        db.rollback()

    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=302)
