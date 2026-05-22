import json
from urllib import request
from datetime import datetime
from datetime import date
from datetime import timedelta

from fastapi import UploadFile
from fastapi import File

import shutil
import uuid
from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi.responses import FileResponse
from datetime import date
from datetime import timedelta

from app.models import quotation
from app.utils.pdf import generate_quotation_pdf

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement

router = APIRouter(
    prefix="/quotations",
    tags=["quotations"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/new",
    response_class=HTMLResponse
)
async def new_quotation(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "ventas"]
    )

    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).all()

    products = db.query(Product).all()

    return templates.TemplateResponse(
    request=request,
    name="quotation_new.html",
    context={
        "clients": clients,
        "products": products
    }
)

@router.get(
    "/",
    response_class=HTMLResponse
)
async def quotations_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "ventas"]
    )

    if isinstance(user, RedirectResponse):
        return user

    quotations = db.query(
        Quotation
    ).order_by(
        Quotation.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="quotations.html",
        context={
            "quotations": quotations
        }
    )

@router.get(
    "/{quotation_id}",
    response_class=HTMLResponse
)
async def quotation_detail(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "ventas"]
    )

    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    return templates.TemplateResponse(
        request=request,
        name="quotation_detail.html",
        context={
            "quotation": quotation
        }
    )

@router.get("/{quotation_id}/approve")
async def approve_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # APROBAR
    quotation.status = "aprobada"

    db.commit()

    return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )

@router.get("/{quotation_id}/cancel")
async def cancel_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO SI ESTÁ PENDIENTE
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    quotation.status = "cancelada"

    db.commit()

    return RedirectResponse(
        url="/quotations",
        status_code=302
    )

@router.get("/{quotation_id}/delete")
async def delete_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # BORRAR ITEMS
    db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).delete()

    # BORRAR COTIZACIÓN
    db.delete(quotation)

    db.commit()

    return RedirectResponse(
        url="/quotations",
        status_code=302
    )

@router.get("/{quotation_id}/edit",
    response_class=HTMLResponse
)
async def edit_quotation_page(

    quotation_id: int,

    request: Request,

    db: Session = Depends(get_db)

):

    user = role_required(
        request,
        ["admin", "ventas"]
    )

    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    clients = db.query(Client).all()

    products = db.query(Product).all()

    items = db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).all()

    # ITEMS PARA JS
    items_json = []

    for item in items:

        items_json.append({

            "type": "inventory",

            "product_id": None,

            "quantity": item.quantity,

            "detail": item.detail,

            "price": item.unit_price,

            "total": item.total

        })

    return templates.TemplateResponse(

        request=request,

        name="quotation_new.html",

        context={

            "clients": clients,

            "products": products,

            "quotation": quotation,

            "items_json": json.dumps(items_json),

            "edit_mode": True

        }

    )

@router.post("/{quotation_id}/edit")
async def update_quotation(

    quotation_id: int,

    client_id: int = Form(...),

    subtotal: float = Form(...),

    discount: float = Form(...),

    iva: float = Form(...),

    total: float = Form(...),

    items: str = Form(...),

    db: Session = Depends(get_db)

):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # UPDATE HEADER
    quotation.client_id = client_id

    quotation.subtotal = subtotal

    quotation.discount = discount

    quotation.iva = iva

    quotation.total = total

    # DELETE OLD ITEMS
    db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).delete()

    items_data = json.loads(items)

    # INSERT NEW ITEMS
    for item in items_data:

        quotation_item = QuotationItem(

            quotation_id=quotation.id,

            quantity=item.get(
                "quantity",
                1
            ),

            detail=item.get(
                "detail",
                ""
            ),

            unit_price=item.get(
                "price",
                0.0
            ),

            total=item.get(
                "total",
                0.0
            )

        )

        db.add(quotation_item)

    db.commit()

    return RedirectResponse(

        url=f"/quotations/{quotation.id}",

        status_code=302

    )



@router.get("/{quotation_id}/production")
async def production_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    try:

        # =====================================
        # QUOTATION
        # =====================================

        quotation = db.query(
            Quotation
        ).filter(
            Quotation.id == quotation_id
        ).first()

        if not quotation:

            return RedirectResponse(
                url="/quotations/",
                status_code=302
            )

        # =====================================
        # ITEMS
        # =====================================

        items = db.query(
            QuotationItem
        ).filter(
            QuotationItem.quotation_id == quotation.id
        ).all()

        # =====================================
        # VALIDATE + DISCOUNT STOCK
        # =====================================

        for item in items:

            # IGNORE CUSTOM PRODUCTS
            if not item.product_id:
                continue

            product = db.query(
                Product
            ).filter(
                Product.id == item.product_id
            ).first()

            if not product:
                continue

            previous_stock = product.stock or 0

            new_stock = previous_stock - item.quantity

            # =====================================
            # NO NEGATIVE STOCK
            # =====================================

            if new_stock < 0:

                return HTMLResponse(
                    content=f"""
                    <h1>
                        Stock insuficiente
                    </h1>

                    <p>
                        Producto:
                        {product.name}
                    </p>

                    <p>
                        Disponible:
                        {previous_stock}
                    </p>

                    <p>
                        Solicitado:
                        {item.quantity}
                    </p>
                    """,
                    status_code=400
                )

            # =====================================
            # UPDATE STOCK
            # =====================================

            product.stock = new_stock

            # =====================================
            # CREATE MOVEMENT
            # =====================================

            movement = InventoryMovement(

                product_id=product.id,

                movement_type="salida",

                quantity=item.quantity,

                previous_stock=previous_stock,

                new_stock=new_stock,

                reason=f"Cotización #{quotation.id} → Producción"

            )

            db.add(movement)

        # =====================================
        # UPDATE QUOTATION
        # =====================================

        quotation.status = "produccion"

        # =====================================
        # CREATE PRODUCTION ORDER
        # =====================================

        production_order = ProductionOrder(

            quotation_id=quotation.id,

            status="pendiente",

            priority="media",

            delivery_date=quotation.delivery_date

        )

        db.add(production_order)

        # =====================================
        # SAVE
        # =====================================

        db.commit()

        return RedirectResponse(
            url="/production/",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        print(
            "ERROR PRODUCTION:",
            str(e)
        )

        return HTMLResponse(
            content=f"""
            <h1>
                Error enviando a producción
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )
    

@router.get("/{quotation_id}/shipping")
async def shipping_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    quotation.status = "enviada"

    db.commit()

    if quotation.status != "produccion":

        return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )


@router.get("/{quotation_id}/delivered")
async def delivered_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    quotation.status = "entregada"

    db.commit()

    return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )

@router.get("/{quotation_id}/pdf")
async def quotation_pdf(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    try:

        # =====================================
        # QUOTATION
        # =====================================

        quotation = db.query(
            Quotation
        ).filter(
            Quotation.id == quotation_id
        ).first()

        if not quotation:

            return HTMLResponse(
                content="""
                <h1>
                    Cotización no encontrada
                </h1>
                """,
                status_code=404
            )

        # =====================================
        # ITEMS
        # =====================================

        items = db.query(
            QuotationItem
        ).filter(
            QuotationItem.quotation_id == quotation_id
        ).all()

        # =====================================
        # CLIENT
        # =====================================

        client = db.query(
            Client
        ).filter(
            Client.id == quotation.client_id
        ).first()

        if not client:

            return HTMLResponse(
                content="""
                <h1>
                    Cliente no encontrado
                </h1>
                """,
                status_code=404
            )

        # =====================================
        # FILENAME
        # =====================================

        filename = f"quotation_{quotation_id}.pdf"

        # =====================================
        # GENERATE PDF
        # =====================================

        generate_quotation_pdf(
            quotation,
            items,
            client,
            filename
        )

        # =====================================
        # RETURN FILE
        # =====================================

        return FileResponse(
            path=filename,
            media_type="application/pdf",
            filename=filename
        )

    except Exception as e:

        print(
            "ERROR PDF:",
            str(e)
        )

        return HTMLResponse(
            content=f"""
            <h1>
                Error generando PDF
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )
    

@router.post("/create")
async def create_quotation(

    client_id: int = Form(...),

    subtotal: float = Form(...),

    discount: float = Form(...),

    delivery_date: str = Form(None),

    iva: float = Form(...),

    total: float = Form(...),

    items: str = Form(...),

    design_file: UploadFile = File(None),

    db: Session = Depends(get_db)

):

    # =========================================
    # PARSE DELIVERY DATE
    # =========================================

    parsed_delivery_date = None

    if delivery_date:

        parsed_delivery_date = datetime.strptime(
            delivery_date,
            "%Y-%m-%d"
        ).date()

    # =========================================
    # CREATE QUOTATION
    # =========================================

    filename = None

    if design_file:

        extension = design_file.filename.split(".")[-1]

        filename = f"{uuid.uuid4()}.{extension}"

        with open(

            f"uploads/designs/{filename}",

            "wb"

        ) as buffer:

            shutil.copyfileobj(
                design_file.file,
                buffer
        )
        
    """ dsa """

    quotation = Quotation(

        client_id=client_id,

        subtotal=subtotal,

        discount=discount,

        delivery_date=parsed_delivery_date,

        iva=iva,

        total=total,
        design_file=filename,

        status="pendiente"

    )

    db.add(quotation)

    db.commit()

    db.refresh(quotation)

    # =========================================
    # ITEMS
    # =========================================

    items_data = json.loads(items)

    for item in items_data:

        quotation_item = QuotationItem(

            quotation_id=quotation.id,

            quantity=item.get(
                "quantity",
                1
            ),

            detail=item.get(
                "detail",
                ""
            ),

            measure=item.get(
                "measure",
                ""
            ),

            theme=item.get(
                "theme",
                ""
            ),

            color=item.get(
                "color",
                ""
            ),

            logo=item.get(
                "logo",
                ""
            ),

            unit_price=item.get(
                "price",
                0.0
            ),

            total=item.get(
                "total",
                0.0
            )

        )

        db.add(quotation_item)

    db.commit()

    return RedirectResponse(

        url=f"/quotations/{quotation.id}",

        status_code=302

    )