import os

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
from app.config.settings import settings
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
from app.utils.image_storage import (
    UploadValidationError,
    delete_logo_file,
    logo_image_url,
    read_upload_bytes,
    save_logo_image,
    validate_upload_filename,
)

templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["logo_image_url"] = logo_image_url

UPLOAD_DIR = "uploads/logos"

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    if password == settings.secretadmin_password:
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

    return templates.TemplateResponse(
        request=request,
        name="admin/config.html",
        context={"config": config}
    )


@router.get("/storage", response_class=HTMLResponse)
async def admin_storage(request: Request, db: Session = Depends(get_db)):
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        return RedirectResponse(url="/secretadmin/", status_code=302)

    from app.services.storage_stats import collect_storage_stats

    stats = collect_storage_stats(db)
    return templates.TemplateResponse(
        request=request,
        name="admin/storage.html",
        context={"stats": stats},
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
    iva_default: int = Form(default=19),
    logo: UploadFile = File(None),
    request: Request = Request,
    db: Session = Depends(get_db)
):
    """Save company configuration"""

    # Check if authenticated
    if not is_admin_session_valid(request.cookies.get("admin_token")):
        raise HTTPException(status_code=401, detail="Not authenticated")

    config = get_or_create_config(db)

    # Update configuration
    config.company_name = company_name
    config.primary_color = primary_color
    config.secondary_color = secondary_color
    config.accent_color = accent_color
    config.font_color = font_color
    config.quotation_validity_days = quotation_validity_days
    config.quotation_footer_text = quotation_footer_text
    config.iva_default = iva_default

    # Handle logo upload
    if logo and logo.filename:
        try:
            validate_upload_filename(logo.filename)
            data = await read_upload_bytes(logo, 3 * 1024 * 1024)
            delete_logo_file(config.logo)
            config.logo = save_logo_image(data)
        except UploadValidationError:
            return RedirectResponse(
                url="/secretadmin/config?error=logo_invalido",
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
