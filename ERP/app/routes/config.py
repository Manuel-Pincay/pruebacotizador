from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi import UploadFile
from fastapi import File
from fastapi import HTTPException

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company_config import CompanyConfig
from app.auth.security import verify_admin_password
from app.auth.session import (
    admin_cookie_options,
    is_admin_session_valid,
    sign_admin_session,
)


# =====================================
# ROUTER
# =====================================

router = APIRouter(
    prefix="/secretadmin",
    tags=["admin"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
from urllib.parse import quote

from app.utils.image_storage import (
    UploadValidationError,
    delete_logo_file,
    logo_image_url,
    read_upload_bytes,
    save_company_icon,
    save_company_logo_image,
    validate_company_icon_filename,
    validate_upload_filename,
    MAX_LOGO_BYTES,
    MAX_COMPANY_LOGO_BYTES,
)

templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["logo_image_url"] = logo_image_url


# =====================================
# HELPER FUNCTIONS
# =====================================

def get_or_create_config(db: Session):
    """Get or create default company config"""
    config = db.query(CompanyConfig).first()
    if not config:
        config = CompanyConfig()
        db.add(config)
        db.commit()
    return config


# =====================================
# LOGIN PAGE
# =====================================

@router.get("/", response_class=HTMLResponse)
async def admin_login(request: Request):
    """Admin login page"""
    return templates.TemplateResponse(
        request=request,
        name="auth/admin_login.html",
        context={}
    )


# =====================================
# VERIFY PASSWORD
# =====================================

@router.post("/verify")
async def verify_password(
    password: str = Form(...),
    request: Request = Request,
    db: Session = Depends(get_db)
):
    """Verify admin password"""
    if verify_admin_password(password):
        get_or_create_config(db)
        response = RedirectResponse(
            url="/secretadmin/config",
            status_code=302
        )
        response.set_cookie(
            key="admin_token",
            value=sign_admin_session(),
            **admin_cookie_options(),
        )
        return response
    else:
        # Return to login with error
        return templates.TemplateResponse(
            request=request,
            name="auth/admin_login.html",
            context={"error": "Contraseña incorrecta"}
        )


# =====================================
# CONFIG PAGE
# =====================================

@router.get("/config", response_class=HTMLResponse)
async def admin_config(
    request: Request,
    db: Session = Depends(get_db)
):
    """Admin config page"""
    # Check if authenticated
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        return RedirectResponse(
            url="/secretadmin/",
            status_code=302
        )

    config = get_or_create_config(db)

    from app.services.smtp_config_service import (
        resolve_smtp_settings,
        smtp_configured,
        smtp_password_configured,
    )

    smtp = resolve_smtp_settings(config)
    return templates.TemplateResponse(
        request=request,
        name="admin/config.html",
        context={
            "config": config,
            "smtp_configured": smtp_configured(config),
            "smtp_password_set": smtp_password_configured(config),
            "smtp_source": smtp.source if smtp else None,
        },
    )


@router.post("/config/smtp/save")
async def admin_smtp_save(
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
):
    """Guarda / verifica SMTP desde Configuración de empresa."""
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.services.email_service import EmailDeliveryError, send_test_email
    from app.services.smtp_config_service import (
        build_smtp_settings_from_form,
        save_smtp_password,
        smtp_password_configured,
    )

    config = get_or_create_config(db)
    enabled = smtp_enabled == "on"
    from_addr = (smtp_from or "").strip()
    user_addr = (smtp_user or "").strip() or from_addr
    host_val = (smtp_host or "").strip() or "smtp.gmail.com"

    if enabled:
        if not from_addr:
            return RedirectResponse(
                url="/secretadmin/config?smtp_error="
                + quote("Indique el correo electrónico remitente."),
                status_code=302,
            )
        has_pwd = bool((smtp_password or "").strip()) or smtp_password_configured(
            config
        )
        if not has_pwd:
            return RedirectResponse(
                url="/secretadmin/config?smtp_error="
                + quote(
                    "Ingrese la contraseña de aplicación "
                    "(no la contraseña normal de la cuenta)."
                ),
                status_code=302,
            )

    if action == "verify":
        recipient = (test_email or "").strip().lower()
        if not recipient or "@" not in recipient:
            return RedirectResponse(
                url="/secretadmin/config?smtp_error="
                + quote("Indique a qué correo enviar la prueba."),
                status_code=302,
            )
        if not enabled:
            return RedirectResponse(
                url="/secretadmin/config?smtp_error="
                + quote("Active el envío de correo para poder verificar."),
                status_code=302,
            )
        trial = build_smtp_settings_from_form(
            enabled=True,
            host=host_val,
            port=smtp_port,
            user=user_addr,
            from_addr=from_addr,
            password_plain=smtp_password,
            use_tls=smtp_use_tls == "on",
            existing_config=config,
        )
        company = (config.company_name if config else None) or "Su empresa"
        try:
            send_test_email(smtp=trial, to_address=recipient, company_name=company)
        except EmailDeliveryError as exc:
            return RedirectResponse(
                url="/secretadmin/config?smtp_error="
                + quote(f"No se pudo enviar el correo de prueba.\n\n{exc}"),
                status_code=302,
            )
        return RedirectResponse(
            url=f"/secretadmin/config?smtp=ok&to={quote(recipient)}",
            status_code=302,
        )

    config.smtp_enabled = enabled
    config.smtp_host = host_val if enabled else (host_val or None)
    config.smtp_port = max(1, min(int(smtp_port or 587), 65535))
    config.smtp_from = from_addr or None
    config.smtp_user = user_addr or None
    config.smtp_use_tls = smtp_use_tls == "on"
    save_smtp_password(config, smtp_password)
    db.commit()

    return RedirectResponse(url="/secretadmin/config?smtp=saved", status_code=302)


@router.get("/storage", response_class=HTMLResponse)
async def admin_storage(request: Request, db: Session = Depends(get_db)):
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        return RedirectResponse(url="/secretadmin/", status_code=302)

    from app.services.storage_stats import collect_storage_stats
    from app.services.backup_service import list_backups

    stats = collect_storage_stats(db)
    backups = list_backups(15)
    return templates.TemplateResponse(
        request=request,
        name="admin/storage.html",
        context={
            "stats": stats,
            "backups": backups,
            "backup_ok": request.query_params.get("backup") == "1",
            "backup_error": request.query_params.get("backup_error", ""),
        },
    )


@router.post("/backup")
async def admin_run_backup(request: Request):
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        return RedirectResponse(url="/secretadmin/", status_code=302)

    from app.services.backup_service import create_mysql_backup

    try:
        path = create_mysql_backup()
        return RedirectResponse(
            url=f"/secretadmin/storage?backup=1&file={quote(path.name)}",
            status_code=302,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/secretadmin/storage?backup_error={quote(str(exc)[:180])}",
            status_code=302,
        )


# =====================================
# SAVE CONFIG
# =====================================

@router.post("/config/save")
async def save_config(
    company_name: str = Form(...),
    primary_color: str = Form(...),
    secondary_color: str = Form(...),
    accent_color: str = Form(...),
    font_color: str = Form(...),
    quotation_validity_days: int = Form(default=15),
    quotation_footer_text: str = Form(...),
    iva_default: int = Form(default=0),
    sri_iva_default: int = Form(default=15),
    store_payment_instructions: str = Form(""),
    guide_sender_name: str = Form(""),
    guide_sender_city: str = Form("Manta"),
    guide_sender_region: str = Form("Ecuador"),
    guide_sender_phone: str = Form(""),
    guide_sender_address: str = Form(""),
    guide_accent_color: str = Form("#d6452a"),
    guide_border_color: str = Form("#8a97a8"),
    guide_muted_color: str = Form("#6b7785"),
    company_icon: UploadFile = File(None),
    logo: UploadFile = File(None),
    request: Request = Request,
    db: Session = Depends(get_db)
):
    """Save company configuration"""

    # Check if authenticated
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        raise HTTPException(status_code=401, detail="Not authenticated")

    config = get_or_create_config(db)

    from app.services.shipment_service import DEFAULT_GUIDE_COLORS, _normalize_hex_color

    # Update configuration
    config.company_name = company_name
    config.primary_color = primary_color
    config.secondary_color = secondary_color
    config.accent_color = accent_color
    config.font_color = font_color
    config.quotation_validity_days = quotation_validity_days
    config.quotation_footer_text = quotation_footer_text
    config.iva_default = iva_default
    config.sri_iva_default = max(0, min(100, int(sri_iva_default)))
    config.store_payment_instructions = (store_payment_instructions or "").strip() or None
    config.guide_sender_name = guide_sender_name.strip() or None
    config.guide_sender_city = guide_sender_city.strip() or "Manta"
    config.guide_sender_region = guide_sender_region.strip() or "Ecuador"
    config.guide_sender_phone = guide_sender_phone.strip() or None
    config.guide_sender_address = guide_sender_address.strip() or None
    config.guide_accent_color = _normalize_hex_color(
        guide_accent_color, DEFAULT_GUIDE_COLORS["accent"]
    )
    config.guide_border_color = _normalize_hex_color(
        guide_border_color, DEFAULT_GUIDE_COLORS["border"]
    )
    config.guide_muted_color = _normalize_hex_color(
        guide_muted_color, DEFAULT_GUIDE_COLORS["muted"]
    )

    # Icono (sidebar / favicon)
    if company_icon and company_icon.filename:
        try:
            validate_company_icon_filename(company_icon.filename)
            data = await read_upload_bytes(company_icon, MAX_LOGO_BYTES)
            delete_logo_file(config.company_icon)
            config.company_icon = save_company_icon(data)
        except UploadValidationError as exc:
            return RedirectResponse(
                url=f"/secretadmin/config?error=icon&msg={quote(str(exc))}",
                status_code=302,
            )

    # Logo (PDF cotizaciones y guías)
    if logo and logo.filename:
        try:
            validate_upload_filename(logo.filename)
            data = await read_upload_bytes(logo, MAX_COMPANY_LOGO_BYTES)
            delete_logo_file(config.logo)
            config.logo = save_company_logo_image(data)
        except UploadValidationError as exc:
            return RedirectResponse(
                url=f"/secretadmin/config?error=logo&msg={quote(str(exc))}",
                status_code=302,
            )

    db.commit()

    return RedirectResponse(
        url="/secretadmin/config?success=true",
        status_code=302
    )


# =====================================
# LOGOUT
# =====================================

@router.get("/logout")
async def admin_logout():
    """Admin logout"""
    response = RedirectResponse(
        url="/secretadmin/",
        status_code=302
    )
    response.delete_cookie("admin_token", samesite="lax")
    return response
