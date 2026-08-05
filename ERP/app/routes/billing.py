import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_

from app.auth.auth_handler import role_required
from app.auth.permissions import has_permission
from app.config.settings import settings
from app.database import get_db
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.product import Product
from app.models.client import Client
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.sri_certificate import SriCertificate
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.models.sri_sequence import SriSequence
from app.services.product_service import (
    create_billable_product,
    ensure_billing_line_product,
    product_to_billing_payload,
)
from app.services.billing_client_service import (
    consult_client_identificacion,
    consult_sri_identificacion,
    list_local_clients,
    upsert_client_from_adquirente,
)
from app.services.tax_service import default_tarifa_from_config, parse_tarifa_iva
from app.services.invoice_email_service import (
    get_default_body,
    get_default_subject,
    send_invoice_email,
)
from app.services.email_service import EmailDeliveryError, send_test_email
from app.services.smtp_config_service import (
    build_smtp_settings_from_form,
    save_smtp_password,
    smtp_configured,
    smtp_password_configured,
)
from app.services.sri_config_validator import format_validation_errors, validate_sri_config, validate_sri_form_input
from app.services.sri_emission_service import emit_invoice, sync_invoice_from_sri, validate_invoice_emission
from app.services.ride_pdf_service import generate_ride_pdf
from app.services.credit_note_service import (
    build_credit_note_preview,
    create_credit_note_from_invoice,
    get_authorized_credit_note,
    get_pending_credit_note,
)
from app.services.invoice_service import (
    anular_invoice,
    build_quotation_invoice_preview,
    create_invoice_from_quotation,
    create_manual_invoice,
    regenerar_clave_borrador,
    renumerar_borrador,
    validate_quotation_for_billing,
)
from app.services.sri_client_service import get_sri_url
from app.utils.clave_acceso import ambiente_desde_clave
from app.services.sri_sequence_service import (
    check_sequence_discrepancy,
    peek_next_secuencial,
    update_sequence_manual,
)
from app.utils.client_emails import additional_emails_display, collect_client_recipients, load_additional_emails
from app.utils.activity import log_activity
from app.utils.context import get_global_config, build_empresa_sri
from app.utils.encryption import encrypt_bytes, encrypt_text
from app.utils.pagination import build_page_url, paginate_query
from app.utils.sri_constants import CONSUMIDOR_FINAL, FORMAS_PAGO, MOTIVOS_NOTA_CREDITO, TIPOS_IDENTIFICACION, TARIFAS_IVA_PRODUCTO, codigo_iva_from_tarifa

router = APIRouter(prefix="/billing", tags=["billing"])
templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["build_page_url"] = build_page_url


def _billing_guard(request: Request, permission="billing_view"):
    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return user
    if not has_permission(user.role, permission):
        return RedirectResponse(url="/", status_code=302)
    return user


def _billing_api_guard(request: Request, permission="billing_view"):
    """Para endpoints JSON: no redirige al login, responde con error claro."""
    user = role_required(request, ["admin", "ventas"])
    if isinstance(user, RedirectResponse):
        return None, JSONResponse(
            status_code=401,
            content={"error": "Sesión expirada", "mensaje": "Vuelva a iniciar sesión e intente de nuevo."},
        )
    if not has_permission(user.role, permission):
        return None, JSONResponse(
            status_code=403,
            content={"error": "Sin permiso", "mensaje": "No tiene permiso para esta acción."},
        )
    return user, None


def _load_invoices_query(db: Session, estado=None, tipo=None, search=None, client_id=None, date_from=None, date_to=None):
    q = (
        db.query(ElectronicInvoice)
        .options(
            joinedload(ElectronicInvoice.client),
            joinedload(ElectronicInvoice.quotation),
            joinedload(ElectronicInvoice.documento_modificado),
        )
        .order_by(ElectronicInvoice.created_at.desc())
    )
    if tipo:
        q = q.filter(ElectronicInvoice.tipo_comprobante == tipo)
    elif estado in (None, "pending", "authorized", "rejected", "voided"):
        # Listas clásicas: solo facturas salvo comprobantes unificado
        if estado != "all_types":
            q = q.filter(ElectronicInvoice.tipo_comprobante == "FACTURA")
    if estado == "pending":
        q = q.filter(ElectronicInvoice.estado.in_(["BORRADOR", "PENDIENTE_ENVIO", "ENVIANDO", "RECIBIDA", "ERROR"]))
    elif estado == "authorized":
        q = q.filter(ElectronicInvoice.estado == "AUTORIZADA")
    elif estado == "rejected":
        q = q.filter(ElectronicInvoice.estado.in_(["RECHAZADA", "ERROR"]))
    elif estado == "voided":
        q = q.filter(ElectronicInvoice.estado == "ANULADA")
    elif estado == "credit_notes":
        q = q.filter(ElectronicInvoice.tipo_comprobante == "NOTA_CREDITO")
    elif estado in ("AUTORIZADA", "ANULADA", "BORRADOR", "RECHAZADA", "RECIBIDA", "ENVIANDO", "PENDIENTE_ENVIO"):
        q = q.filter(ElectronicInvoice.estado == estado)
    if client_id:
        q = q.filter(ElectronicInvoice.client_id == int(client_id))
    if date_from:
        q = q.filter(ElectronicInvoice.fecha_emision >= date_from)
    if date_to:
        q = q.filter(ElectronicInvoice.fecha_emision <= date_to)
    if search:
        term = f"%{search.strip()}%"
        q = q.outerjoin(Client).filter(
            or_(
                ElectronicInvoice.clave_acceso.ilike(term),
                ElectronicInvoice.secuencial.ilike(term),
                ElectronicInvoice.numero_autorizacion.ilike(term),
                ElectronicInvoice.motivo.ilike(term),
                Client.name.ilike(term),
                Client.company.ilike(term),
                Client.ruc_ci.ilike(term),
            )
        )
    return q


def _paginate(request: Request, query):
    page = max(1, int(request.query_params.get("page", 1) or 1))
    return paginate_query(query, page, settings.per_page)


@router.get("/", response_class=HTMLResponse)
async def billing_list(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Facturas", "filter": "all"},
    )


@router.get("/pending", response_class=HTMLResponse)
async def billing_pending(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db, "pending"))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Facturas pendientes", "filter": "pending"},
    )


@router.get("/authorized", response_class=HTMLResponse)
async def billing_authorized(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db, "authorized"))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Facturas autorizadas", "filter": "authorized"},
    )


@router.get("/rejected", response_class=HTMLResponse)
async def billing_rejected(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db, "rejected"))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Facturas rechazadas", "filter": "rejected"},
    )


@router.get("/voided", response_class=HTMLResponse)
async def billing_voided(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db, "voided"))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Facturas anuladas", "filter": "voided"},
    )


@router.get("/credit-notes", response_class=HTMLResponse)
async def billing_credit_notes(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    pagination = _paginate(request, _load_invoices_query(db, "credit_notes"))
    return templates.TemplateResponse(
        request=request,
        name="billing/list.html",
        context={"user": user, "pagination": pagination, "title": "Notas de crédito", "filter": "credit_notes"},
    )


@router.get("/comprobantes", response_class=HTMLResponse)
async def billing_comprobantes(
    request: Request,
    db: Session = Depends(get_db),
    search: str = "",
    tipo: str = "",
    estado: str = "",
    client_id: str = "",
    date_from: str = "",
    date_to: str = "",
):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    q = _load_invoices_query(
        db,
        estado=estado or "all_types",
        tipo=tipo or None,
        search=search or None,
        client_id=int(client_id) if client_id.strip().isdigit() else None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    pagination = _paginate(request, q)
    clients = db.query(Client).order_by(Client.name).all()
    return templates.TemplateResponse(
        request=request,
        name="billing/comprobantes.html",
        context={
            "user": user,
            "pagination": pagination,
            "clients": clients,
            "search": search,
            "tipo": tipo,
            "estado": estado,
            "client_id": client_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@router.get("/{invoice_id}/credit-note/preview", response_class=HTMLResponse)
async def billing_credit_note_preview(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    motivo: str = "ANULACIÓN DE FACTURA",
):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        preview = build_credit_note_preview(db, invoice_id, motivo)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="billing/credit_note_preview.html",
        context={
            "user": user,
            "invoice": preview["invoice"],
            "motivo": preview["motivo"],
            "validation": preview["validation"],
            "existing_nc": preview["existing_nc"],
            "motivos": MOTIVOS_NOTA_CREDITO,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/{invoice_id}/credit-note")
async def billing_credit_note_create(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    motivo: str = Form("ANULACIÓN DE FACTURA"),
    action: str = Form("create"),
):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        nc = create_credit_note_from_invoice(db, invoice_id, motivo, user_id=user.id)
        if action == "create_and_emit":
            emit_invoice(db, nc.id, user_id=user.id)
            return RedirectResponse(url=f"/billing/{nc.id}?success=nc_emitida", status_code=302)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/billing/{invoice_id}/credit-note/preview?motivo={quote(motivo)}&error={quote(str(exc))}",
            status_code=302,
        )
    return RedirectResponse(url=f"/billing/{nc.id}?success=nc_creada", status_code=302)


@router.get("/api/clientes")
async def billing_api_clientes(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
):
    """Catálogo local — pestaña «Mis clientes» (como GET /clientes en FactuSRI)."""
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err
    return JSONResponse(list_local_clients(db, search))


@router.get("/api/clientes/consultar-sri")
async def billing_api_consultar_sri(
    request: Request,
    identificacion: str = "",
):
    """Catastro en línea del SRI — pestaña «Consultar SRI» (sin buscar en catálogo local)."""
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err
    try:
        result = consult_sri_identificacion(identificacion)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "source": "manual",
                "error": str(exc),
                "mensaje": "No se pudo consultar el SRI en línea. Complete los datos manualmente.",
            },
        )


@router.get("/api/clientes/consultar")
async def billing_api_consultar_cliente(
    request: Request,
    identificacion: str = "",
    db: Session = Depends(get_db),
):
    """Local primero, luego SRI — mismo flujo que ClientesService.consultar en FactuSRI."""
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err
    try:
        result = consult_client_identificacion(db, identificacion)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "source": "manual",
                "error": str(exc),
                "mensaje": "No se pudo consultar. Complete los datos manualmente.",
            },
        )


@router.get("/api/preview-numero")
async def billing_preview_numero(
    request: Request,
    codigo_establecimiento: str = "001",
    codigo_punto_emision: str = "001",
    db: Session = Depends(get_db),
):
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err
    estab = str(codigo_establecimiento or "001").zfill(3)[-3:]
    pto = str(codigo_punto_emision or "001").zfill(3)[-3:]
    try:
        secuencial = peek_next_secuencial(db, estab, pto)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return JSONResponse(
        {
            "secuencial": secuencial,
            "numero_comprobante": f"{estab}-{pto}-{secuencial}",
        }
    )


@router.post("/api/products/quick-create")
async def billing_quick_create_product(request: Request, db: Session = Depends(get_db)):
    """Crea producto en catálogo con IVA SRI para usar en factura manual."""
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "JSON inválido"})

    name = (body.get("name") or body.get("descripcion") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "Ingrese la descripción del producto"})

    price = float(body.get("price") or body.get("precio_unitario") or 0)
    if price <= 0:
        return JSONResponse(status_code=400, content={"error": "Ingrese un precio válido"})

    config = db.query(CompanyConfig).first()
    default_tarifa = default_tarifa_from_config(config)
    tarifa_raw = body.get("tarifa_iva")
    if tarifa_raw is None or tarifa_raw == "":
        tarifa = default_tarifa
    else:
        tarifa = parse_tarifa_iva(tarifa_raw, default=default_tarifa)

    product = create_billable_product(
        db,
        name=name,
        description=name,
        price=price,
        tarifa_iva=tarifa,
        codigo_iva=body.get("codigo_iva"),
        custom=True,
        category="Facturación",
    )
    if not product:
        return JSONResponse(status_code=400, content={"error": "No se pudo crear el producto"})

    db.commit()
    db.refresh(product)
    return JSONResponse(product_to_billing_payload(product))


@router.get("/new", response_class=HTMLResponse)
async def billing_new(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    clients = (
        db.query(Client, func.count(ElectronicInvoice.id).label("uso_count"))
        .outerjoin(ElectronicInvoice, ElectronicInvoice.client_id == Client.id)
        .group_by(Client.id)
        .order_by(desc("uso_count"), Client.name.asc())
        .all()
    )
    products = db.query(Product).order_by(Product.name).limit(500).all()
    config = db.query(CompanyConfig).first()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    validation = validate_sri_config(db, config, cert) if config else None
    establishments = (
        db.query(SriEstablishment)
        .options(joinedload(SriEstablishment.emission_points))
        .order_by(SriEstablishment.codigo)
        .all()
    )
    products_payload = [
        {
            "id": p.id,
            "codigo_principal": (p.code or f"P{p.id}")[:50],
            "codigo_auxiliar": p.codigo_auxiliar,
            "descripcion": (p.description or p.name or "Producto")[:500],
            "precio_unitario": float(p.price or 0),
            "tarifa_iva": float(
                p.tarifa_iva if p.tarifa_iva is not None else default_tarifa_from_config(config)
            ),
            "codigo_iva": p.codigo_iva or codigo_iva_from_tarifa(
                p.tarifa_iva if p.tarifa_iva is not None else default_tarifa_from_config(config)
            ),
        }
        for p in products
    ]
    establishments_payload = [
        {
            "codigo": est.codigo,
            "nombre": est.nombre or f"Establecimiento {est.codigo}",
            "direccion": est.direccion or "",
            "points": [{"codigo": p.codigo} for p in est.emission_points],
        }
        for est in establishments
    ]
    clients_payload = [
        {
            "id": c.id,
            "identificacion": c.ruc_ci or "",
            "tipo_identificacion": c.tipo_identificacion or "CEDULA",
            "razon_social": c.company or c.name or "",
            "direccion": c.address or "",
            "telefono": c.phone or "",
            "email": c.email or "",
            "label": f"{c.ruc_ci or 'sin ID'} — {c.company or c.name}",
            "uso_count": int(uso_count or 0),
        }
        for c, uso_count in clients
    ]
    default_estab = (config.sri_default_establishment if config else None) or "001"
    default_pto = (config.sri_default_emission_point if config else None) or "001"
    preview_secuencial = "000000001"
    try:
        preview_secuencial = peek_next_secuencial(db, default_estab, default_pto)
    except ValueError:
        pass
    preview_numero = f"{default_estab}-{default_pto}-{preview_secuencial}"
    fecha_emision = datetime.now().strftime("%d-%m-%Y")
    empresa = build_empresa_sri(config)
    default_tarifa_iva = default_tarifa_from_config(config)
    default_codigo_iva = codigo_iva_from_tarifa(default_tarifa_iva)
    billing_tarifas_iva = [t for t in TARIFAS_IVA_PRODUCTO if t["tarifa"] in (0, 15)]
    return templates.TemplateResponse(
        request=request,
        name="billing/new.html",
        context={
            "user": user,
            "clients_json": json.dumps(clients_payload, ensure_ascii=False),
            "config": config,
            "empresa": empresa,
            "establishments": establishments,
            "products_json": json.dumps(products_payload, ensure_ascii=False),
            "establishments_json": json.dumps(establishments_payload, ensure_ascii=False),
            "formas_pago": FORMAS_PAGO,
            "tipos_identificacion": TIPOS_IDENTIFICACION,
            "consumidor_final": CONSUMIDOR_FINAL,
            "default_email": (config.sri_email_notificacion if config else "") or "",
            "default_estab": default_estab,
            "default_pto": default_pto,
            "preview_numero": preview_numero,
            "preview_secuencial": preview_secuencial,
            "fecha_emision": fecha_emision,
            "config_ready": validation.valido if validation else False,
            "config_errors": validation.errores if validation else [],
            "default_tarifa_iva": default_tarifa_iva,
            "default_codigo_iva": default_codigo_iva,
            "billing_tarifas_iva": billing_tarifas_iva,
        },
    )


@router.post("/create")
async def billing_create(request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()

    def _redirect_error(msg: str):
        return RedirectResponse(url=f"/billing/new?error={quote(msg)}", status_code=302)

    try:
        items = json.loads(form.get("items_json") or "[]")
        pagos = json.loads(form.get("pagos_json") or "[]")
        info_adicional = json.loads(form.get("info_adicional_json") or "[]")
    except json.JSONDecodeError:
        return _redirect_error("Datos del formulario inválidos. Recargue la página e intente de nuevo.")

    if not items:
        return _redirect_error("Agregue al menos un producto o línea a la factura.")

    try:
        client = upsert_client_from_adquirente(
            db,
            client_id=int(form.get("client_id") or 0) or None,
            tipo_identificacion=form.get("tipo_identificacion", ""),
            identificacion=form.get("identificacion", ""),
            razon_social=form.get("razon_social", ""),
            direccion=form.get("direccion", ""),
            telefono=form.get("telefono", ""),
            email=form.get("email", ""),
        )
    except ValueError as exc:
        return _redirect_error(str(exc))

    normalized_items = []
    config = db.query(CompanyConfig).first()
    default_tarifa = default_tarifa_from_config(config)
    for item in items:
        product_id = item.get("product_id")
        if product_id:
            try:
                product_id = int(product_id)
            except (TypeError, ValueError):
                product_id = None
        entry = {
            "product_id": product_id,
            "descripcion": item.get("descripcion", ""),
            "codigo_principal": item.get("codigo_principal") or item.get("codigo") or "MANUAL",
            "codigo_auxiliar": item.get("codigo_auxiliar"),
            "cantidad": float(item.get("cantidad", 1) or 1),
            "precio_unitario": float(item.get("precio_unitario", item.get("precio", 0)) or 0),
            "descuento": float(item.get("descuento", 0) or 0),
            "tarifa_iva": parse_tarifa_iva(item.get("tarifa_iva"), default=default_tarifa),
            "codigo_iva": item.get("codigo_iva"),
            "is_manual": bool(item.get("is_manual")),
        }
        entry = ensure_billing_line_product(db, entry, default_tarifa_iva=default_tarifa)
        normalized_items.append(
            {
                "product_id": entry.get("product_id"),
                "descripcion": entry.get("descripcion", ""),
                "codigo_principal": entry.get("codigo_principal") or "MANUAL",
                "codigo_auxiliar": entry.get("codigo_auxiliar"),
                "cantidad": entry.get("cantidad", 1),
                "precio_unitario": entry.get("precio_unitario", 0),
                "descuento": entry.get("descuento", 0),
                "tarifa_iva": parse_tarifa_iva(entry.get("tarifa_iva"), default=default_tarifa),
                "codigo_iva": entry.get("codigo_iva") or codigo_iva_from_tarifa(entry.get("tarifa_iva", default_tarifa)),
            }
        )

    normalized_pagos = []
    for pago in pagos:
        entry = {
            "forma_pago": str(pago.get("forma_pago") or pago.get("formaPago") or "01"),
            "total": round(float(pago.get("total") or 0), 2),
        }
        if pago.get("plazo") not in (None, ""):
            entry["plazo"] = int(pago["plazo"])
            entry["unidad_tiempo"] = pago.get("unidad_tiempo") or "dias"
        normalized_pagos.append(entry)

    info = [
        {"nombre": str(c.get("nombre", "")).strip(), "valor": str(c.get("valor", "")).strip()}
        for c in info_adicional
        if str(c.get("nombre", "")).strip() and str(c.get("valor", "")).strip()
    ]

    try:
        invoice = create_manual_invoice(
            db,
            client.id,
            normalized_items,
            user_id=user.id,
            codigo_establecimiento=form.get("codigo_establecimiento"),
            codigo_punto_emision=form.get("codigo_punto_emision"),
            pagos=normalized_pagos,
            info_adicional=info or None,
        )
    except ValueError as exc:
        return _redirect_error(str(exc))

    return RedirectResponse(url=f"/billing/{invoice.id}", status_code=302)


@router.get("/from-quotation/{quotation_id}/preview", response_class=HTMLResponse)
async def billing_from_quotation_preview(quotation_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        preview = build_quotation_invoice_preview(db, quotation_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/quotations/{quotation_id}?billing_error={quote(str(exc))}",
            status_code=302,
        )

    q = preview["quotation"]
    product_links = {}
    for item in q.items:
        if item.product_id:
            product_links[item.id] = item.product_id

    return templates.TemplateResponse(
        request=request,
        name="billing/from_quotation_preview.html",
        context={
            "user": user,
            "quotation": q,
            "lines": preview["lines"],
            "totals": preview["totals"],
            "validation": preview["validation"],
            "info_adicional": preview["info_adicional"],
            "formas_pago": FORMAS_PAGO,
            "product_links": product_links,
        },
    )


@router.get("/from-quotation/{quotation_id}/validar")
async def billing_from_quotation_validate(quotation_id: int, request: Request, db: Session = Depends(get_db)):
    _, err = _billing_api_guard(request, "billing_create")
    if err:
        return err
    quotation = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.items).joinedload(QuotationItem.product),
            joinedload(Quotation.payments),
            joinedload(Quotation.electronic_invoice),
        )
        .filter(Quotation.id == quotation_id)
        .first()
    )
    if not quotation:
        return JSONResponse(status_code=404, content={"valido": False, "errores": [{"mensaje": "Cotización no encontrada"}]})
    result = validate_quotation_for_billing(db, quotation)
    return JSONResponse(
        {
            "valido": result.valido,
            "errores": [{"campo": e.campo, "mensaje": e.mensaje} for e in result.errores],
            "advertencias": [{"campo": a.campo, "mensaje": a.mensaje} for a in result.advertencias],
        }
    )


@router.post("/from-quotation/{quotation_id}")
async def billing_from_quotation_create(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    forma_pago: str = Form("01"),
):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        preview = build_quotation_invoice_preview(db, quotation_id)
        total = preview["totals"]["importe_total"]
        pagos = [{"forma_pago": forma_pago, "total": total, "plazo": "0", "unidad_tiempo": "Dias"}]
        invoice = create_invoice_from_quotation(db, quotation_id, user_id=user.id, pagos=pagos)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/billing/from-quotation/{quotation_id}/preview?error={quote(str(exc))}",
            status_code=302,
        )
    try:
        from app.services.notification_service import NotificationService

        q = preview.get("quotation")
        client = getattr(q, "client", None) if q is not None else None
        client_name = getattr(client, "name", None) or "—"
        user_label = getattr(user, "full_name", None) or getattr(user, "username", None) or "—"
        invoice_ref = getattr(invoice, "numero_comprobante", None) or f"#{invoice.id}"
        NotificationService.notify_quote_sent_to_billing(
            client=client_name,
            quotation_id=quotation_id,
            total=total,
            invoice_ref=invoice_ref,
            user=user_label,
        )
    except Exception:
        pass
    return RedirectResponse(url=f"/billing/{invoice.id}", status_code=302)


@router.get("/from-quotation/{quotation_id}")
async def billing_from_quotation(quotation_id: int, request: Request, db: Session = Depends(get_db)):
    """Redirige al paso de revisión antes de crear la factura."""
    return RedirectResponse(url=f"/billing/from-quotation/{quotation_id}/preview", status_code=302)


@router.get("/{invoice_id}/validar")
async def billing_validate(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = _billing_api_guard(request, "billing_emit")
    if err:
        return err
    try:
        result = validate_invoice_emission(db, invoice_id)
        return JSONResponse(
            {
                "valido": result.valido,
                "errores": [{"campo": e.campo, "mensaje": e.mensaje} for e in result.errores],
                "advertencias": [{"campo": a.campo, "mensaje": a.mensaje} for a in result.advertencias],
            }
        )
    except ValueError as exc:
        return JSONResponse(status_code=404, content={"valido": False, "errores": [{"mensaje": str(exc)}]})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"valido": False, "errores": [{"mensaje": str(exc)}]},
        )


@router.get("/{invoice_id}", response_class=HTMLResponse)
async def billing_detail(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    invoice = (
        db.query(ElectronicInvoice)
        .options(
            joinedload(ElectronicInvoice.client),
            joinedload(ElectronicInvoice.lines),
            joinedload(ElectronicInvoice.notas_credito),
            joinedload(ElectronicInvoice.documento_modificado),
        )
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not invoice:
        return RedirectResponse(url="/billing/", status_code=302)

    config = db.query(CompanyConfig).first()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    validation = validate_sri_config(db, config, cert) if config else None
    seq_warning = check_sequence_discrepancy(
        db, invoice.codigo_establecimiento, invoice.codigo_punto_emision
    )

    error = request.query_params.get("error")
    success = request.query_params.get("success")
    pagos = json.loads(invoice.pagos_json) if invoice.pagos_json else []
    info_adicional = json.loads(invoice.info_adicional_json) if invoice.info_adicional_json else []
    sri_recepcion = None
    if invoice.mensajes_sri_json:
        try:
            sri_recepcion = json.loads(invoice.mensajes_sri_json)
        except json.JSONDecodeError:
            sri_recepcion = None

    return templates.TemplateResponse(
        request=request,
        name="billing/detail.html",
        context={
            "user": user,
            "invoice": invoice,
            "pagos": pagos,
            "info_adicional": info_adicional,
            "formas_pago": FORMAS_PAGO,
            "config_ready": validation.valido if validation else False,
            "config_errors": validation.errores if validation else [],
            "seq_warning": seq_warning,
            "error": error,
            "success": success,
            "sri_ambiente_config": (config.sri_ambiente if config else None) or "PRUEBAS",
            "sri_ambiente_clave": ambiente_desde_clave(invoice.clave_acceso),
            "sri_tipo_emision": (config.sri_tipo_emision if config else None) or "NORMAL",
            "sri_recepcion_url": get_sri_url(
                "recepcion",
                (config.sri_ambiente if config else None) or "PRUEBAS",
                (config.sri_tipo_emision if config else None) or "NORMAL",
            ),
            "sri_recepcion": sri_recepcion,
            "smtp_configured": smtp_configured(config),
            "smtp_password_set": smtp_password_configured(config),
            "smtp_source": "db" if (config and config.smtp_enabled and config.smtp_host) else ("env" if smtp_configured(None) else None),
            "email_recipients": collect_client_recipients(invoice.client) if invoice.client else [],
            "client_additional_emails": load_additional_emails(invoice.client) if invoice.client else [],
            "default_email_subject": get_default_subject(config),
            "default_email_body": get_default_body(config),
            "email_sent_to": json.loads(invoice.email_sent_to_json) if invoice.email_sent_to_json else [],
            "authorized_nc": get_authorized_credit_note(invoice) if invoice.is_factura else None,
            "pending_nc": get_pending_credit_note(invoice) if invoice.is_factura else None,
            "motivos_nc": MOTIVOS_NOTA_CREDITO,
        },
    )


@router.post("/{invoice_id}/send-email")
async def billing_send_email(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    custom_message: str = Form(""),
    extra_emails: str = Form(""),
    save_extra_emails: str = Form(""),
):
    user = _billing_guard(request, "billing_emit")
    if isinstance(user, RedirectResponse):
        return user
    try:
        extra = [e.strip() for e in extra_emails.replace("\n", ",").split(",") if e.strip()] if extra_emails else None
        save_extra = (
            [e.strip() for e in save_extra_emails.replace("\n", ",").split(",") if e.strip()]
            if save_extra_emails
            else None
        )
        result = send_invoice_email(
            db,
            invoice_id,
            custom_message=custom_message or None,
            extra_emails=extra,
            save_extra_to_client=save_extra,
            user_id=user.id,
        )
        msg = quote(f"Correo enviado a: {', '.join(result['recipients'])}")
        return RedirectResponse(url=f"/billing/{invoice_id}?success={msg}", status_code=302)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)


@router.post("/config/email/save")
async def billing_email_config_save(
    request: Request,
    db: Session = Depends(get_db),
    action: str = Form("save"),
    test_email: str = Form(""),
    smtp_enabled: str = Form(""),
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form(""),
    smtp_use_tls: str = Form(""),
    billing_email_subject: str = Form(""),
    billing_email_body: str = Form(""),
    billing_auto_send_email: str = Form(""),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    existing = db.query(CompanyConfig).first()
    enabled = smtp_enabled == "on"
    from_addr = smtp_from.strip()
    user_addr = smtp_user.strip() or from_addr

    if enabled:
        if not smtp_host.strip() or not from_addr:
            return RedirectResponse(
                url="/billing/config/sri?error=" + quote("Indique el correo electrónico de la empresa."),
                status_code=302,
            )
        has_pwd = bool((smtp_password or "").strip()) or smtp_password_configured(existing)
        if not has_pwd:
            return RedirectResponse(
                url="/billing/config/sri?error=" + quote(
                    "Ingrese la contraseña de aplicación de su correo (no la contraseña normal de la cuenta)."
                ),
                status_code=302,
            )

    verify = action == "verify"
    if verify:
        recipient = test_email.strip().lower()
        if not recipient or "@" not in recipient:
            return RedirectResponse(
                url="/billing/config/sri?error=" + quote("Indique a qué correo enviar la prueba de verificación."),
                status_code=302,
            )
        if not enabled:
            return RedirectResponse(
                url="/billing/config/sri?error=" + quote("Active el envío de correo para poder verificar."),
                status_code=302,
            )
        trial = build_smtp_settings_from_form(
            enabled=True,
            host=smtp_host,
            port=smtp_port,
            user=user_addr,
            from_addr=from_addr,
            password_plain=smtp_password,
            use_tls=smtp_use_tls == "on",
            existing_config=existing,
        )
        company = (
            (existing.sri_razon_social if existing else None)
            or (existing.company_name if existing else None)
            or "Su empresa"
        )
        try:
            send_test_email(smtp=trial, to_address=recipient, company_name=company)
        except EmailDeliveryError as exc:
            return RedirectResponse(
                url="/billing/config/sri?error=" + quote(f"No se pudo enviar el correo de prueba.\n\n{exc}"),
                status_code=302,
            )

    config = existing or CompanyConfig()
    if not config.id:
        db.add(config)

    config.smtp_enabled = enabled
    config.smtp_host = smtp_host.strip() or None
    config.smtp_port = max(1, min(int(smtp_port or 587), 65535))
    config.smtp_from = from_addr or None
    config.smtp_user = user_addr or None
    config.smtp_use_tls = smtp_use_tls == "on"
    save_smtp_password(config, smtp_password)

    config.billing_email_subject = billing_email_subject.strip() or None
    config.billing_email_body = billing_email_body.strip() or None
    config.billing_auto_send_email = billing_auto_send_email == "on"
    db.commit()

    if verify:
        log_activity(
            db,
            "BILLING_EMAIL_VERIFIED",
            f"Correo verificado; prueba enviada a {recipient}",
        )
        return RedirectResponse(
            url="/billing/config/sri?success=email_verified&to=" + quote(recipient),
            status_code=302,
        )

    log_activity(db, "BILLING_EMAIL_CONFIG", "Configuración de correo y plantilla de facturas actualizada")
    return RedirectResponse(url="/billing/config/sri?success=email", status_code=302)


@router.post("/{invoice_id}/regenerar-clave")
async def billing_regenerar_clave(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        regenerar_clave_borrador(db, invoice_id, user_id=user.id)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)
    return RedirectResponse(
        url=f"/billing/{invoice_id}?success={quote('Clave de acceso regenerada. Puede emitir de nuevo.')}",
        status_code=302,
    )


@router.post("/{invoice_id}/renumerar")
async def billing_renumerar(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        inv = renumerar_borrador(db, invoice_id, user_id=user.id)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)
    return RedirectResponse(
        url=f"/billing/{invoice_id}?success={quote('Nuevo comprobante ' + inv.numero_comprobante)}",
        status_code=302,
    )


@router.post("/{invoice_id}/anular")
async def billing_anular(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_create")
    if isinstance(user, RedirectResponse):
        return user
    try:
        anular_invoice(db, invoice_id, user_id=user.id)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)
    return RedirectResponse(url="/billing/?success=factura_anulada", status_code=302)


@router.post("/{invoice_id}/emit")
async def billing_emit(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_emit")
    if isinstance(user, RedirectResponse):
        return user
    try:
        result = emit_invoice(db, invoice_id, user_id=user.id)
        log_activity(db, "FACTURA_ENVIADA", f"Factura #{invoice_id} — estado {result.get('estado')}")
        if result.get("success"):
            return RedirectResponse(url=f"/billing/{invoice_id}?success=autorizada", status_code=302)
        msg = result.get("message", "En proceso")
        return RedirectResponse(url=f"/billing/{invoice_id}?success={quote(msg)}", status_code=302)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)


@router.post("/{invoice_id}/sync")
async def billing_sync(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request, "billing_emit")
    if isinstance(user, RedirectResponse):
        return user
    try:
        result = sync_invoice_from_sri(db, invoice_id)
        log_activity(db, "FACTURA_SINCRONIZADA", f"Factura #{invoice_id} — {result.get('estado')}")
        return RedirectResponse(url=f"/billing/{invoice_id}?success=sincronizada", status_code=302)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/{invoice_id}?error={quote(str(exc))}", status_code=302)


@router.get("/{invoice_id}/xml")
async def billing_xml(invoice_id: int, request: Request, variant: str = "autorizado", db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not invoice:
        return RedirectResponse(url="/billing/", status_code=302)
    content = {
        "autorizado": invoice.xml_autorizado,
        "firmado": invoice.xml_firmado,
        "generado": invoice.xml_generado,
    }.get(variant, invoice.xml_autorizado)
    if not content:
        return RedirectResponse(url=f"/billing/{invoice_id}?error=XML+no+disponible", status_code=302)
    filename = f"factura_{invoice.numero_comprobante}_{variant}.xml"
    return Response(content=content, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{invoice_id}/ride")
async def billing_ride(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = _billing_guard(request)
    if isinstance(user, RedirectResponse):
        return user
    invoice = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not invoice:
        return RedirectResponse(url="/billing/", status_code=302)
    config = db.query(CompanyConfig).first()
    dir_sucursal = None
    if invoice.codigo_establecimiento:
        est = (
            db.query(SriEstablishment)
            .filter(SriEstablishment.codigo == invoice.codigo_establecimiento)
            .first()
        )
        if est:
            dir_sucursal = est.direccion
    pdf = generate_ride_pdf(invoice, config, dir_sucursal=dir_sucursal)
    filename = f"RIDE_{invoice.numero_comprobante}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/config/sri", response_class=HTMLResponse)
async def billing_sri_config(request: Request, db: Session = Depends(get_db)):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    if not has_permission(user.role, "billing_config"):
        return RedirectResponse(url="/", status_code=302)

    config = db.query(CompanyConfig).first()
    if not config:
        config = CompanyConfig()
        db.add(config)
        db.commit()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    establishments = (
        db.query(SriEstablishment)
        .options(
            joinedload(SriEstablishment.emission_points).joinedload(SriEmissionPoint.sequences)
        )
        .all()
    )
    validation = validate_sri_config(db, config, cert)
    default_est = None
    if config.sri_default_establishment:
        default_est = (
            db.query(SriEstablishment)
            .filter(SriEstablishment.codigo == config.sri_default_establishment)
            .first()
        )

    return templates.TemplateResponse(
        request=request,
        name="billing/config_sri.html",
        context={
            "user": user,
            "config": config,
            "default_est": default_est,
            "has_certificate": cert is not None,
            "establishments": establishments,
            "validation": validation,
            "success": request.query_params.get("success"),
            "email_verified_to": request.query_params.get("to"),
            "error": request.query_params.get("error"),
            "smtp_configured": smtp_configured(config),
            "smtp_password_set": smtp_password_configured(config),
            "smtp_source": "db" if (config and config.smtp_enabled and config.smtp_host) else ("env" if smtp_configured(None) else None),
            "default_email_subject": get_default_subject(config),
            "default_email_body": get_default_body(config),
        },
    )


@router.post("/config/sri/save")
async def billing_sri_config_save(
    request: Request,
    db: Session = Depends(get_db),
    sri_ruc: str = Form(""),
    sri_razon_social: str = Form(""),
    sri_nombre_comercial: str = Form(""),
    sri_direccion_matriz: str = Form(""),
    sri_obligado_contabilidad: str = Form(""),
    sri_contribuyente_especial: str = Form(""),
    sri_contribuyente_rimpe: str = Form(""),
    sri_ambiente: str = Form("PRUEBAS"),
    sri_tipo_emision: str = Form("NORMAL"),
    sri_email_notificacion: str = Form(""),
    sri_default_establishment: str = Form("001"),
    sri_default_emission_point: str = Form("001"),
    sri_active: str = Form(""),
    est_nombre: str = Form(""),
    est_direccion: str = Form(""),
    certificate: UploadFile | None = File(None),
    certificate_password: str = Form(""),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    existing_cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    cert_data = await certificate.read() if certificate and certificate.filename else b""
    cert_uploaded = bool(cert_data)

    form_check = validate_sri_form_input(
        sri_ruc=sri_ruc,
        sri_razon_social=sri_razon_social,
        sri_direccion_matriz=sri_direccion_matriz,
        sri_email_notificacion=sri_email_notificacion,
        sri_default_establishment=sri_default_establishment,
        sri_default_emission_point=sri_default_emission_point,
        certificate_uploaded=cert_uploaded,
        certificate_password=certificate_password,
        has_existing_certificate=existing_cert is not None,
    )
    if not form_check.valido:
        msg = quote(form_check.errores[0].mensaje)
        return RedirectResponse(url=f"/billing/config/sri?error={msg}", status_code=302)

    config = db.query(CompanyConfig).first() or CompanyConfig()
    if not config.id:
        db.add(config)

    razon = sri_razon_social.strip()
    config.sri_ruc = sri_ruc.strip()
    config.sri_razon_social = razon
    config.company_name = razon or config.company_name
    config.sri_nombre_comercial = sri_nombre_comercial.strip() or razon
    config.sri_direccion_matriz = sri_direccion_matriz.strip()
    config.sri_obligado_contabilidad = sri_obligado_contabilidad == "on"
    config.sri_contribuyente_especial = sri_contribuyente_especial.strip() or None
    config.sri_contribuyente_rimpe = sri_contribuyente_rimpe.strip() or None
    config.sri_ambiente = sri_ambiente if sri_ambiente in ("PRUEBAS", "PRODUCCION") else "PRUEBAS"
    config.sri_tipo_emision = sri_tipo_emision if sri_tipo_emision in ("NORMAL", "CONTINGENCIA") else "NORMAL"
    config.sri_email_notificacion = sri_email_notificacion.strip() or None
    config.sri_default_establishment = sri_default_establishment.strip().zfill(3)[-3:]
    config.sri_default_emission_point = sri_default_emission_point.strip().zfill(3)[-3:]
    config.sri_active = sri_active == "on"

    codigo_est = config.sri_default_establishment
    pto_code = config.sri_default_emission_point
    dir_est = (est_direccion or sri_direccion_matriz).strip()
    nombre_est = (est_nombre or "").strip()
    if nombre_est.lower() == "none":
        nombre_est = ""
    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo_est).first()
    if not est:
        est = SriEstablishment(
            codigo=codigo_est,
            nombre=nombre_est or None,
            direccion=dir_est,
        )
        db.add(est)
        db.flush()
    else:
        if nombre_est:
            est.nombre = nombre_est
        elif est.nombre == "None":
            est.nombre = None
        est.direccion = dir_est

    pto = (
        db.query(SriEmissionPoint)
        .filter(SriEmissionPoint.establishment_id == est.id, SriEmissionPoint.codigo == pto_code)
        .first()
    )
    if not pto:
        pto = SriEmissionPoint(establishment_id=est.id, codigo=pto_code)
        db.add(pto)
        db.flush()
        db.add(SriSequence(emission_point_id=pto.id, tipo_comprobante="FACTURA", ultimo_numero=0))
        db.add(SriSequence(emission_point_id=pto.id, tipo_comprobante="NOTA_CREDITO", ultimo_numero=0))

    if cert_uploaded:
        cert = existing_cert or SriCertificate()
        if not cert.id:
            db.add(cert)
        cert.encrypted_p12 = encrypt_bytes(cert_data)
        cert.encrypted_password = encrypt_text(certificate_password)
        log_activity(db, "SRI_CERTIFICADO", "Certificado electrónico actualizado")

    db.commit()
    log_activity(db, "SRI_CONFIG", "Configuración SRI guardada (formulario único)")
    return RedirectResponse(url="/billing/config/sri?success=ok", status_code=302)


@router.post("/config/sri/certificate")
async def billing_sri_certificate_upload(
    request: Request,
    db: Session = Depends(get_db),
    certificate: UploadFile = File(...),
    certificate_password: str = Form(...),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    data = await certificate.read()
    if not data:
        return RedirectResponse(url="/billing/config/sri?error=Certificado+vacío", status_code=302)

    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    if not cert:
        cert = SriCertificate()
        db.add(cert)

    cert.encrypted_p12 = encrypt_bytes(data)
    cert.encrypted_password = encrypt_text(certificate_password)
    db.commit()
    log_activity(db, "SRI_CERTIFICADO", "Certificado electrónico actualizado")
    return RedirectResponse(url="/billing/config/sri?success=cert", status_code=302)


@router.post("/config/sri/establishment")
async def billing_sri_establishment(
    request: Request,
    db: Session = Depends(get_db),
    codigo: str = Form(...),
    nombre: str = Form(""),
    direccion: str = Form(...),
    punto_emision: str = Form("001"),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    codigo = codigo.strip().zfill(3)[-3:]
    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo).first()
    if not est:
        est = SriEstablishment(codigo=codigo, nombre=nombre.strip() or None, direccion=direccion.strip())
        db.add(est)
        db.flush()
    else:
        est.nombre = nombre.strip() or est.nombre
        est.direccion = direccion.strip()

    pto_code = punto_emision.strip().zfill(3)[-3:]
    pto = (
        db.query(SriEmissionPoint)
        .filter(SriEmissionPoint.establishment_id == est.id, SriEmissionPoint.codigo == pto_code)
        .first()
    )
    if not pto:
        pto = SriEmissionPoint(establishment_id=est.id, codigo=pto_code)
        db.add(pto)
        db.flush()
        db.add(SriSequence(emission_point_id=pto.id, tipo_comprobante="FACTURA", ultimo_numero=0))
        db.add(SriSequence(emission_point_id=pto.id, tipo_comprobante="NOTA_CREDITO", ultimo_numero=0))

    db.commit()
    return RedirectResponse(url="/billing/config/sri?success=est", status_code=302)


@router.post("/config/sri/sequence")
async def billing_sri_sequence(
    request: Request,
    db: Session = Depends(get_db),
    emission_point_id: int = Form(...),
    proximo_secuencial: int = Form(...),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    try:
        update_sequence_manual(db, emission_point_id, proximo_secuencial)
    except ValueError as exc:
        return RedirectResponse(url=f"/billing/config/sri?error={quote(str(exc))}", status_code=302)
    return RedirectResponse(url="/billing/config/sri?success=seq", status_code=302)
