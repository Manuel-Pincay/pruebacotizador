import os
import shutil

from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import UploadFile
from fastapi import File

from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import StreamingResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.utils.activity import log_activity

from app.auth.auth_handler import role_required

from app.services.excel_importer import (
    create_clients_template,
    create_products_template,
    export_clients_excel,
    export_filename,
    export_products_excel,
    export_quotations_excel,
    import_clients,
    import_products
)

router = APIRouter(
    prefix="/imports",
    tags=["imports"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config

templates.env.globals[
    'inject_global_config'
] = get_global_config

UPLOAD_DIR = "uploads/imports"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# ==========================================
# PAGE
# ==========================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def imports_page(
    request: Request
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request=request,
        name="imports/index.html",
        context={}
    )


# ==========================================
# CLIENT TEMPLATE
# ==========================================

@router.get("/clients/template")
async def clients_template(request: Request):

    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    path = "clients_template.xlsx"

    create_clients_template(path)

    return FileResponse(
        path=path,
        filename=path
    )


@router.get("/clients/export")
async def export_clients(
    request: Request,
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    buffer = export_clients_excel(db)
    filename = export_filename("clientes")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================
# PRODUCT TEMPLATE
# ==========================================

@router.get("/products/template")
async def products_template(request: Request):

    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    path = "products_template.xlsx"

    create_products_template(path)

    return FileResponse(
        path=path,
        filename=path
    )


@router.get("/products/export")
async def export_products(
    request: Request,
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    buffer = export_products_excel(db)
    filename = export_filename("productos")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/quotations/export")
async def export_quotations(
    request: Request,
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    buffer = export_quotations_excel(db)
    filename = export_filename("cotizaciones")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================
# IMPORT CLIENTS
# ==========================================

@router.post("/clients/upload")
async def upload_clients(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    file_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(file_path, "wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    imported = import_clients(
        db,
        file_path
    )

    try:
        description = f"{imported} clientes importados" if imported and imported > 0 else "Ningún cliente importado"
        log_activity(
            db,
            "Importación",
            description
        )
    except Exception:
        pass

    return RedirectResponse(
        url="/imports/?success=clients",
        status_code=302
    )


# ==========================================
# IMPORT PRODUCTS
# ==========================================

@router.post("/products/upload")
async def upload_products(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    file_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(file_path, "wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    imported = import_products(
        db,
        file_path
    )

    try:
        description = f"{imported} productos importados" if imported and imported > 0 else "Ningún producto importado"
        log_activity(
            db,
            "Importación",
            description
        )
    except Exception:
        pass

    return RedirectResponse(
        url="/imports/?success=products",
        status_code=302
    )