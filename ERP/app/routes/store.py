"""Tienda virtual pública: catálogo, carrito y checkout → cotización store."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.company_config import CompanyConfig
from app.models.quotation import Quotation
from app.services.store_auth import (
    CLIENT_COOKIE,
    PortalEmailPending,
    authenticate_portal_client,
    client_cookie_options,
    confirm_portal_email,
    get_portal_client,
    register_portal_client,
    resend_portal_verify_code,
    send_portal_verify_email,
    sign_client_session,
    sign_verify_token,
    resolve_verify_token,
)
from app.services.store_cart import (
    CART_COOKIE,
    cart_add,
    cart_cookie_options,
    cart_remove,
    cart_set_qty,
    load_cart,
    sign_cart,
)
from app.services.store_catalog import (
    cart_subtotal,
    create_store_quotation,
    get_store_product,
    list_store_products,
    resolve_cart_lines,
    store_category_options,
)
from app.services.store_home_service import (
    featured_category_cards,
    featured_products,
    get_or_create_home_settings,
    list_active_slides,
    parse_nav_links,
    store_theme_color,
)
from app.utils.context import get_global_config
from app.utils.image_storage import product_image_url, store_slide_image_url
from app.utils.urls import ERP_PREFIX, erp_path

router = APIRouter(tags=["store"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["erp_prefix"] = ERP_PREFIX
templates.env.globals["erp_url"] = erp_path
templates.env.globals["product_image_url"] = product_image_url
templates.env.globals["store_slide_image_url"] = store_slide_image_url


def _base_context(request: Request, db: Session, **extra):
    config = db.query(CompanyConfig).first()
    home_settings = get_or_create_home_settings(db)
    cart_items = load_cart(request.cookies.get(CART_COOKIE))
    cart_count = sum(int(i["quantity"]) for i in cart_items)
    portal_client = get_portal_client(db, request.cookies.get(CLIENT_COOKIE))
    primary = store_theme_color(
        home_settings,
        config.primary_color if config else None,
    )
    ctx = {
        "config": config,
        "home_settings": home_settings,
        "erp_login_url": erp_path("/login"),
        "cart_count": cart_count,
        "company_name": (config.company_name if config else None) or "Nuestra tienda",
        "primary_color": primary,
        "nav_links": parse_nav_links(home_settings.nav_extra_links),
        "portal_client": portal_client,
    }
    ctx.update(extra)
    return ctx


def _login_redirect(next_url: str = "/tienda/cuenta/") -> RedirectResponse:
    from urllib.parse import quote

    safe = next_url if next_url.startswith("/") and not next_url.startswith("//") else "/tienda/cuenta/"
    return RedirectResponse(
        url=f"/tienda/cuenta/login?next={quote(safe)}",
        status_code=302,
    )


def _require_portal_client(request: Request, db: Session, *, next_url: str = ""):
    client = get_portal_client(db, request.cookies.get(CLIENT_COOKIE))
    if not client:
        return _login_redirect(next_url or request.url.path)
    return client


def _set_cart_cookie(response: RedirectResponse, items: list[dict]) -> RedirectResponse:
    opts = cart_cookie_options()
    if items:
        response.set_cookie(key=CART_COOKIE, value=sign_cart(items), **opts)
    else:
        response.delete_cookie(key=CART_COOKIE, path="/")
    return response


def _set_client_cookie(response: RedirectResponse, client_id: int) -> RedirectResponse:
    opts = client_cookie_options()
    response.set_cookie(
        key=CLIENT_COOKIE,
        value=sign_client_session(client_id),
        **opts,
    )
    return response


@router.get("/", response_class=HTMLResponse)
async def store_home(request: Request, db: Session = Depends(get_db)):
    settings = get_or_create_home_settings(db)
    products = featured_products(db, settings, limit=8)
    return templates.TemplateResponse(
        request=request,
        name="store/home.html",
        context=_base_context(
            request,
            db,
            products=products,
            slides=list_active_slides(db),
            category_cards=featured_category_cards(db, settings),
            categories=store_category_options(db),
        ),
    )


@router.get("/tienda", response_class=HTMLResponse)
async def store_catalog(
    request: Request,
    q: str = "",
    category: str = "",
    db: Session = Depends(get_db),
):
    products, total = list_store_products(db, q=q, category=category, limit=60)
    return templates.TemplateResponse(
        request=request,
        name="store/catalog.html",
        context=_base_context(
            request,
            db,
            products=products,
            total=total,
            q=q,
            category=category,
            categories=store_category_options(db),
        ),
    )


@router.get("/tienda/producto/{product_id}", response_class=HTMLResponse)
async def store_product_detail(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    product = get_store_product(db, product_id)
    if not product:
        return RedirectResponse(url="/tienda?error=producto", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="store/product.html",
        context=_base_context(request, db, product=product),
    )


@router.get("/tienda/carrito", response_class=HTMLResponse)
async def store_cart_view(request: Request, db: Session = Depends(get_db)):
    raw = load_cart(request.cookies.get(CART_COOKIE))
    lines = resolve_cart_lines(db, raw)
    return templates.TemplateResponse(
        request=request,
        name="store/cart.html",
        context=_base_context(
            request,
            db,
            lines=lines,
            subtotal=cart_subtotal(lines),
            flash=request.query_params.get("ok", ""),
            error=request.query_params.get("error", ""),
        ),
    )


@router.post("/tienda/carrito/agregar")
async def store_cart_add(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(1),
    next: str = Form("/tienda/carrito"),
    db: Session = Depends(get_db),
):
    portal = _require_portal_client(
        request, db, next_url="/tienda/carrito"
    )
    if isinstance(portal, RedirectResponse):
        return portal

    product = get_store_product(db, product_id)
    if not product:
        return RedirectResponse(url="/tienda?error=producto", status_code=302)

    items = cart_add(load_cart(request.cookies.get(CART_COOKIE)), product_id, quantity)
    dest = next if next.startswith("/") and not next.startswith("//") else "/tienda/carrito"
    response = RedirectResponse(url=dest, status_code=303)
    return _set_cart_cookie(response, items)


@router.post("/tienda/carrito/actualizar")
async def store_cart_update(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db),
):
    items = cart_set_qty(load_cart(request.cookies.get(CART_COOKIE)), product_id, quantity)
    response = RedirectResponse(url="/tienda/carrito", status_code=303)
    return _set_cart_cookie(response, items)


@router.post("/tienda/carrito/quitar")
async def store_cart_remove(
    request: Request,
    product_id: int = Form(...),
    db: Session = Depends(get_db),
):
    items = cart_remove(load_cart(request.cookies.get(CART_COOKIE)), product_id)
    response = RedirectResponse(url="/tienda/carrito", status_code=303)
    return _set_cart_cookie(response, items)


@router.get("/tienda/checkout", response_class=HTMLResponse)
async def store_checkout_form(request: Request, db: Session = Depends(get_db)):
    portal = _require_portal_client(request, db, next_url="/tienda/checkout")
    if isinstance(portal, RedirectResponse):
        return portal

    raw = load_cart(request.cookies.get(CART_COOKIE))
    lines = resolve_cart_lines(db, raw)
    if not lines:
        return RedirectResponse(url="/tienda/carrito?error=vacio", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="store/checkout.html",
        context=_base_context(
            request,
            db,
            lines=lines,
            subtotal=cart_subtotal(lines),
            error=request.query_params.get("error", ""),
            form={
                "phone": portal.phone or "",
                "ruc_ci": portal.ruc_ci or "",
                "address": portal.address or "",
                "notes": "",
            },
        ),
    )


@router.post("/tienda/checkout")
async def store_checkout_submit(
    request: Request,
    phone: str = Form(""),
    ruc_ci: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.utils.text_format import format_title_words

    portal = _require_portal_client(request, db, next_url="/tienda/checkout")
    if isinstance(portal, RedirectResponse):
        return portal

    raw = load_cart(request.cookies.get(CART_COOKIE))
    lines = resolve_cart_lines(db, raw)
    if not lines:
        return RedirectResponse(url="/tienda/carrito?error=vacio", status_code=302)

    form = {
        "phone": (phone or "").strip() or (portal.phone or ""),
        "ruc_ci": (ruc_ci or "").strip(),
        "address": format_title_words((address or "").strip()),
        "notes": (notes or "").strip(),
    }
    if len(form["phone"]) < 7:
        return templates.TemplateResponse(
            request=request,
            name="store/checkout.html",
            context=_base_context(
                request,
                db,
                lines=lines,
                subtotal=cart_subtotal(lines),
                error="Indica un teléfono válido",
                form=form,
            ),
            status_code=400,
        )

    try:
        if form["phone"]:
            portal.phone = form["phone"]
        if form["address"]:
            portal.address = form["address"]
        if form["ruc_ci"] and not portal.ruc_ci:
            portal.ruc_ci = form["ruc_ci"]

        quotation = create_store_quotation(db, client=portal, lines=lines)

        db.commit()
        db.refresh(quotation)
        qid = quotation.id
        token = quotation.store_access_token
        notify_client = portal.name or "Cliente tienda"
        notify_phone = portal.phone or form["phone"] or "—"
        notify_email = portal.email or "—"
        notify_total = float(quotation.total or 0)
        notify_items = len(quotation.items or [])
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="store/checkout.html",
            context=_base_context(
                request,
                db,
                lines=lines,
                subtotal=cart_subtotal(lines),
                error=str(exc),
                form=form,
            ),
            status_code=400,
        )
    except Exception:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="store/checkout.html",
            context=_base_context(
                request,
                db,
                lines=lines,
                subtotal=cart_subtotal(lines),
                error="No se pudo crear la cotización. Intenta de nuevo.",
                form=form,
            ),
            status_code=500,
        )

    try:
        from app.utils.activity import log_activity
        from app.utils.quotation_events import log_quotation_event

        log_activity(db, "Cotización tienda", f"Cotización #{qid} (tienda)")
        if form["notes"]:
            log_quotation_event(
                db,
                qid,
                "nota_cliente",
                form["notes"][:500],
                None,
            )
        db.commit()
    except Exception:
        db.rollback()

    try:
        from app.services.notification_service import NotificationService

        NotificationService.notify_store_order_created(
            client=notify_client,
            phone=notify_phone,
            email=notify_email,
            quotation_id=qid,
            total=notify_total,
            items_count=notify_items,
        )
    except Exception:
        pass

    response = RedirectResponse(
        url=f"/tienda/pedido/{qid}/{token}?ok=1",
        status_code=303,
    )
    return _set_cart_cookie(response, [])


def _load_store_order(db: Session, quotation_id: int, token: str) -> Quotation | None:
    if not token:
        return None
    quotation = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.items),
            joinedload(Quotation.client),
            joinedload(Quotation.payments),
            joinedload(Quotation.production_order),
            joinedload(Quotation.electronic_invoice),
        )
        .filter(
            Quotation.id == quotation_id,
            Quotation.source == "store",
            Quotation.store_access_token == token,
        )
        .first()
    )
    if quotation:
        from app.services.store_order_service import maybe_auto_cancel_store_order

        maybe_auto_cancel_store_order(db, quotation)
    return quotation


@router.get("/tienda/pedido/{quotation_id}", response_class=HTMLResponse)
async def store_order_legacy_redirect(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Sin token no se muestra el pedido (protección básica)."""
    return RedirectResponse(url="/tienda", status_code=302)


@router.get("/tienda/pedido/{quotation_id}/{token}", response_class=HTMLResponse)
async def store_order_status(
    quotation_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.services.store_order_service import (
        store_order_timeline,
        store_payment_summary,
    )
    from app.services.production_helpers import quotation_estimated_delivery

    quotation = _load_store_order(db, quotation_id, token)
    if not quotation:
        return RedirectResponse(url="/tienda", status_code=302)

    config = db.query(CompanyConfig).first()
    return templates.TemplateResponse(
        request=request,
        name="store/order.html",
        context=_base_context(
            request,
            db,
            quotation=quotation,
            token=token,
            ok=request.query_params.get("ok") == "1",
            flash=request.query_params.get("flash", ""),
            error=request.query_params.get("error", ""),
            timeline=store_order_timeline(quotation),
            payment_summary=store_payment_summary(quotation),
            estimated_delivery=quotation_estimated_delivery(quotation),
            payment_instructions=(
                (config.store_payment_instructions or "").strip()
                if config
                else ""
            ),
        ),
    )


@router.post("/tienda/pedido/{quotation_id}/{token}/pago")
async def store_order_register_payment(
    quotation_id: int,
    token: str,
    request: Request,
    amount: str = Form(...),
    reference: str = Form(""),
    transfer_receipt: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Cliente registra transferencia + comprobante (queda pendiente de verificación)."""
    from datetime import datetime

    from app.models.quotation_payment import (
        PAYMENT_STATUS_PENDING,
        QuotationPayment,
    )
    from app.services.payment_service import (
        PaymentValidationError,
        parse_amount,
        validate_payment_amount,
    )
    from app.utils.image_storage import (
        MAX_PAYMENT_RECEIPT_BYTES,
        UploadValidationError,
        read_upload_bytes,
        save_payment_receipt,
        validate_receipt_content,
        validate_receipt_filename,
    )

    quotation = _load_store_order(db, quotation_id, token)
    if not quotation:
        return RedirectResponse(url="/tienda", status_code=302)

    order_url = f"/tienda/pedido/{quotation_id}/{token}"

    from app.services.store_order_service import store_order_is_cancelled

    if store_order_is_cancelled(quotation):
        from urllib.parse import quote

        return RedirectResponse(
            url=f"{order_url}?error={quote('Este pedido está cancelado. Ya no puedes registrar pagos.')}",
            status_code=303,
        )

    try:
        parsed_amount = parse_amount(amount)
        validate_payment_amount(quotation, parsed_amount)

        if not transfer_receipt or not transfer_receipt.filename:
            raise UploadValidationError("Sube el comprobante de transferencia.")

        ext = validate_receipt_filename(transfer_receipt.filename)
        data = await read_upload_bytes(transfer_receipt, MAX_PAYMENT_RECEIPT_BYTES)
        validate_receipt_content(ext, data)
        receipt_filename = save_payment_receipt(data, ext)

        payment = QuotationPayment(
            quotation_id=quotation.id,
            amount=parsed_amount,
            payment_date=datetime.utcnow(),
            payment_method="transferencia",
            reference=(reference or "").strip()[:100] or None,
            notes="Registrado por el cliente desde la tienda",
            transfer_receipt=receipt_filename,
            verification_status=PAYMENT_STATUS_PENDING,
        )
        db.add(payment)
        db.commit()
    except (PaymentValidationError, UploadValidationError) as exc:
        db.rollback()
        from urllib.parse import quote

        return RedirectResponse(
            url=f"{order_url}?error={quote(str(exc))}",
            status_code=303,
        )
    except Exception:
        db.rollback()
        from urllib.parse import quote

        return RedirectResponse(
            url=f"{order_url}?error={quote('No se pudo registrar el pago. Intenta de nuevo.')}",
            status_code=303,
        )

    try:
        from app.utils.activity import log_activity

        log_activity(
            db,
            "Comprobante tienda",
            f"Cotización #{quotation_id}: esperando verificación",
        )
        db.commit()
    except Exception:
        db.rollback()

    return RedirectResponse(url=f"{order_url}?flash=pago_enviado", status_code=303)


@router.get("/tienda/pedido/{quotation_id}/{token}/comprobante/{payment_id}")
async def store_order_receipt(
    quotation_id: int,
    token: str,
    payment_id: int,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    from app.utils.image_storage import (
        is_payment_receipt_pdf,
        resolve_payment_receipt_path,
    )

    quotation = _load_store_order(db, quotation_id, token)
    if not quotation:
        return RedirectResponse(url="/tienda", status_code=302)

    payment = next((p for p in quotation.payments if p.id == payment_id), None)
    if not payment or not payment.transfer_receipt:
        return RedirectResponse(
            url=f"/tienda/pedido/{quotation_id}/{token}",
            status_code=302,
        )

    path = resolve_payment_receipt_path(payment.transfer_receipt)
    if not path:
        return RedirectResponse(
            url=f"/tienda/pedido/{quotation_id}/{token}",
            status_code=302,
        )

    media_type = (
        "application/pdf"
        if is_payment_receipt_pdf(payment.transfer_receipt)
        else "image/webp"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)


# ─── Cuenta del cliente ─────────────────────────────────────────────


@router.get("/tienda/cuenta/", response_class=HTMLResponse)
async def store_account(request: Request, db: Session = Depends(get_db)):
    from app.services.store_order_service import (
        STORE_ORDER_LABELS,
        maybe_auto_cancel_store_order,
        store_order_status_code,
        store_payment_summary,
    )
    from app.services.production_helpers import quotation_estimated_delivery

    portal = _require_portal_client(request, db, next_url="/tienda/cuenta/")
    if isinstance(portal, RedirectResponse):
        return portal

    orders = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.payments),
            joinedload(Quotation.production_order),
            joinedload(Quotation.electronic_invoice),
        )
        .filter(
            Quotation.source == "store",
            Quotation.client_id == portal.id,
        )
        .order_by(Quotation.created_at.desc())
        .limit(50)
        .all()
    )
    active_codes = {"receptado", "fabricacion", "enviado"}
    rows = []
    for q in orders:
        maybe_auto_cancel_store_order(db, q)
        code = store_order_status_code(q)
        rows.append(
            {
                "quotation": q,
                "order_code": code,
                "order_label": STORE_ORDER_LABELS.get(code, code),
                "payment": store_payment_summary(q),
                "is_active": code in active_codes,
                "is_cancelled": code == "cancelado",
                "estimated_delivery": quotation_estimated_delivery(q),
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="store/account.html",
        context=_base_context(
            request,
            db,
            orders=rows,
            active_orders=[r for r in rows if r["is_active"]],
            past_orders=[r for r in rows if not r["is_active"]],
        ),
    )


@router.get("/tienda/cuenta/login", response_class=HTMLResponse)
async def store_account_login_form(request: Request, db: Session = Depends(get_db)):
    if get_portal_client(db, request.cookies.get(CLIENT_COOKIE)):
        return RedirectResponse(url="/tienda/cuenta/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="store/login.html",
        context=_base_context(
            request,
            db,
            error=request.query_params.get("error", ""),
            next_url=request.query_params.get("next", "/tienda/cuenta/"),
        ),
    )


@router.post("/tienda/cuenta/login")
async def store_account_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/tienda/cuenta/"),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    from app.config.settings import settings
    from app.services.store_auth import issue_verify_code
    from app.services.smtp_config_service import smtp_configured
    from app.models.client import Client
    from app.models.company_config import CompanyConfig

    try:
        client = authenticate_portal_client(db, email=email, password=password)
    except PortalEmailPending as pending:
        dev_code = None
        try:
            row = db.query(Client).filter(Client.id == pending.client_id).first()
            if row:
                code = issue_verify_code(row)
                config = db.query(CompanyConfig).first()
                if smtp_configured(config):
                    try:
                        send_portal_verify_email(db, row, code)
                    except Exception:
                        pass
                elif not settings.is_production:
                    dev_code = code
                db.commit()
        except Exception:
            db.rollback()
        token = sign_verify_token(pending.client_id)
        url = (
            f"/tienda/cuenta/verificar?t={quote(token)}"
            f"&next={quote(next if next.startswith('/') else '/tienda/cuenta/')}"
        )
        if dev_code:
            url += f"&dev_code={quote(dev_code)}"
        return RedirectResponse(url=url, status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="store/login.html",
            context=_base_context(
                request,
                db,
                error=str(exc),
                next_url=next,
                form_email=email,
            ),
            status_code=400,
        )

    dest = next if next.startswith("/") and not next.startswith("//") else "/tienda/cuenta/"
    response = RedirectResponse(url=dest, status_code=303)
    return _set_client_cookie(response, client.id)


@router.get("/tienda/cuenta/registro", response_class=HTMLResponse)
async def store_account_register_form(request: Request, db: Session = Depends(get_db)):
    if get_portal_client(db, request.cookies.get(CLIENT_COOKIE)):
        return RedirectResponse(url="/tienda/cuenta/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="store/register.html",
        context=_base_context(
            request,
            db,
            error="",
            form={},
            next_url=request.query_params.get("next", "/tienda/cuenta/"),
        ),
    )


@router.post("/tienda/cuenta/registro")
async def store_account_register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    ruc_ci: str = Form(""),
    address: str = Form(""),
    next: str = Form("/tienda/cuenta/"),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    from app.config.settings import settings
    from app.services.email_service import EmailDeliveryError
    from app.services.smtp_config_service import smtp_configured
    from app.models.company_config import CompanyConfig

    form = {
        "name": name,
        "email": email,
        "phone": phone,
        "ruc_ci": ruc_ci,
        "address": address,
    }
    if (password or "") != (password2 or ""):
        return templates.TemplateResponse(
            request=request,
            name="store/register.html",
            context=_base_context(
                request,
                db,
                error="Las claves no coinciden",
                form=form,
                next_url=next,
            ),
            status_code=400,
        )

    config = db.query(CompanyConfig).first()
    smtp_ok = smtp_configured(config)
    # En desarrollo sin SMTP: permite registro y muestra el código en pantalla
    allow_dev_code = not settings.is_production and not smtp_ok

    try:
        client, code = register_portal_client(
            db,
            name=name,
            email=email,
            phone=phone,
            password=password,
            ruc_ci=ruc_ci,
            address=address,
            auto_activate=False,
        )
        if smtp_ok:
            send_portal_verify_email(db, client, code or "")
        elif not allow_dev_code:
            raise EmailDeliveryError(
                "No se pudo enviar el correo de verificación. Intenta más tarde."
            )
        db.commit()
        db.refresh(client)
        cid = client.id
        email_out = client.email or email
        # Solo en desarrollo sin SMTP se revela el código
        dev_code = code if allow_dev_code else None
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="store/register.html",
            context=_base_context(
                request,
                db,
                error=str(exc),
                form=form,
                next_url=next,
            ),
            status_code=400,
        )
    except EmailDeliveryError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="store/register.html",
            context=_base_context(
                request,
                db,
                error=str(exc),
                form=form,
                next_url=next,
            ),
            status_code=400,
        )
    except Exception:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="store/register.html",
            context=_base_context(
                request,
                db,
                error="No se pudo crear la cuenta. Intenta de nuevo.",
                form=form,
                next_url=next,
            ),
            status_code=500,
        )

    dest = next if next.startswith("/") and not next.startswith("//") else "/tienda/cuenta/"
    token = sign_verify_token(cid)
    url = f"/tienda/cuenta/verificar?t={quote(token)}&next={quote(dest)}"
    if dev_code:
        url += f"&dev_code={quote(dev_code)}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/tienda/cuenta/verificar", response_class=HTMLResponse)
async def store_account_verify_form(request: Request, db: Session = Depends(get_db)):
    token = request.query_params.get("t", "")
    client_id = resolve_verify_token(token)
    if not client_id:
        return RedirectResponse(url="/tienda/cuenta/registro", status_code=302)
    from app.models.client import Client

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return RedirectResponse(url="/tienda/cuenta/registro", status_code=302)
    if client.portal_active:
        return RedirectResponse(url="/tienda/cuenta/login", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="store/verify.html",
        context=_base_context(
            request,
            db,
            error=request.query_params.get("error", ""),
            flash=request.query_params.get("ok", ""),
            verify_token=token,
            email_masked=_mask_email(client.email or ""),
            next_url=request.query_params.get("next", "/tienda/cuenta/"),
            dev_code=request.query_params.get("dev_code", ""),
        ),
    )


@router.post("/tienda/cuenta/verificar")
async def store_account_verify(
    request: Request,
    code: str = Form(...),
    t: str = Form(...),
    next: str = Form("/tienda/cuenta/"),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    client_id = resolve_verify_token(t)
    if not client_id:
        return RedirectResponse(url="/tienda/cuenta/registro", status_code=302)
    try:
        client = confirm_portal_email(db, client_id=client_id, code=code)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=(
                f"/tienda/cuenta/verificar?t={quote(t)}"
                f"&next={quote(next)}&error={quote(str(exc))}"
            ),
            status_code=303,
        )

    dest = next if next.startswith("/") and not next.startswith("//") else "/tienda/cuenta/"
    response = RedirectResponse(url=dest, status_code=303)
    return _set_client_cookie(response, client.id)


@router.post("/tienda/cuenta/verificar/reenviar")
async def store_account_verify_resend(
    request: Request,
    t: str = Form(...),
    next: str = Form("/tienda/cuenta/"),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    from app.config.settings import settings
    from app.services.email_service import EmailDeliveryError
    from app.services.smtp_config_service import smtp_configured
    from app.models.company_config import CompanyConfig

    client_id = resolve_verify_token(t)
    if not client_id:
        return RedirectResponse(url="/tienda/cuenta/registro", status_code=302)

    config = db.query(CompanyConfig).first()
    smtp_ok = smtp_configured(config)
    allow_dev = not settings.is_production and not smtp_ok
    try:
        from app.services.store_auth import issue_verify_code
        from app.models.client import Client

        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError("Cuenta no encontrada.")
        code = issue_verify_code(client)
        if smtp_ok:
            send_portal_verify_email(db, client, code)
        elif not allow_dev:
            raise EmailDeliveryError("Correo no configurado.")
        db.commit()
        url = (
            f"/tienda/cuenta/verificar?t={quote(t)}&next={quote(next)}&ok=1"
        )
        if allow_dev:
            url += f"&dev_code={quote(code)}"
        return RedirectResponse(url=url, status_code=303)
    except (ValueError, EmailDeliveryError) as exc:
        db.rollback()
        return RedirectResponse(
            url=(
                f"/tienda/cuenta/verificar?t={quote(t)}"
                f"&next={quote(next)}&error={quote(str(exc))}"
            ),
            status_code=303,
        )


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked = user[0] + "*"
    else:
        masked = user[0] + "*" * (len(user) - 2) + user[-1]
    return f"{masked}@{domain}"


@router.get("/tienda/cuenta/logout")
async def store_account_logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key=CLIENT_COOKIE, path="/")
    return response
