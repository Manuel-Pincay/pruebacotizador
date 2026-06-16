from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.database import get_db
from app.models.quotation import Quotation
from app.models.quotation_payment import QuotationPayment
from app.services.payment_service import (
    PaymentValidationError,
    get_quotation_or_raise,
    parse_amount,
    serialize_payment,
    validate_payment_amount,
)
from app.utils.activity import log_activity
from app.utils.image_storage import (
    UploadValidationError,
    delete_payment_receipt,
    is_payment_receipt_image,
    is_payment_receipt_pdf,
    payment_receipt_url,
    read_upload_bytes,
    resolve_payment_receipt_path,
    save_payment_receipt,
    validate_receipt_content,
    validate_receipt_filename,
    MAX_PAYMENT_RECEIPT_BYTES,
)

router = APIRouter(tags=["payments"])

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["payment_receipt_url"] = payment_receipt_url
templates.env.globals["is_payment_receipt_pdf"] = is_payment_receipt_pdf
templates.env.globals["is_payment_receipt_image"] = is_payment_receipt_image

QUOTATION_ROLES = ["admin", "ventas"]


def _require_quotation_access(request: Request):
    user = role_required(request, QUOTATION_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


def _get_payment_or_404(db: Session, payment_id: int) -> QuotationPayment | None:
    return (
        db.query(QuotationPayment)
        .filter(QuotationPayment.id == payment_id)
        .first()
    )


@router.get("/quotations/{quotation_id}/payments/add-modal")
async def add_payment_modal(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = (
        db.query(Quotation)
        .options(joinedload(Quotation.payments))
        .filter(Quotation.id == quotation_id)
        .first()
    )
    if not quotation:
        return JSONResponse(status_code=404, content={"message": "Cotización no encontrada."})

    return templates.TemplateResponse(
        request=request,
        name="partials/quotations/add_payment_modal.html",
        context={
            "quotation_id": quotation.id,
            "pending_balance": quotation.pending_balance,
            "today": datetime.utcnow().strftime("%Y-%m-%d"),
        },
    )


@router.get("/quotations/{quotation_id}/payments")
async def list_quotation_payments(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        quotation = get_quotation_or_raise(db, quotation_id)
    except PaymentValidationError as exc:
        return JSONResponse(status_code=404, content={"message": str(exc)})

    payments = (
        db.query(QuotationPayment)
        .filter(QuotationPayment.quotation_id == quotation.id)
        .order_by(QuotationPayment.payment_date.desc())
        .all()
    )

    return {
        "quotation_id": quotation.id,
        "total": float(quotation.total or 0),
        "total_paid": quotation.total_paid,
        "pending_balance": quotation.pending_balance,
        "payments": [serialize_payment(payment) for payment in payments],
    }


@router.post("/quotations/{quotation_id}/payments")
async def create_quotation_payment(
    quotation_id: int,
    request: Request,
    amount: str = Form(...),
    payment_date: str = Form(...),
    payment_method: str = Form(""),
    reference: str = Form(""),
    notes: str = Form(""),
    transfer_receipt: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        quotation = (
            db.query(Quotation)
            .options(joinedload(Quotation.payments))
            .filter(Quotation.id == quotation_id)
            .first()
        )
        if not quotation:
            raise PaymentValidationError("Cotización no encontrada.")

        parsed_amount = parse_amount(amount)
        validate_payment_amount(quotation, parsed_amount)

        try:
            parsed_date = datetime.fromisoformat(payment_date.replace("Z", "+00:00"))
        except ValueError:
            parsed_date = datetime.strptime(payment_date, "%Y-%m-%d")

        receipt_filename = None
        if transfer_receipt and transfer_receipt.filename:
            ext = validate_receipt_filename(transfer_receipt.filename)
            data = await read_upload_bytes(transfer_receipt, MAX_PAYMENT_RECEIPT_BYTES)
            validate_receipt_content(ext, data)
            receipt_filename = save_payment_receipt(data, ext)

        payment = QuotationPayment(
            quotation_id=quotation.id,
            amount=parsed_amount,
            payment_date=parsed_date,
            payment_method=payment_method.strip()[:50] or None,
            reference=reference.strip()[:100] or None,
            notes=notes.strip() or None,
            transfer_receipt=receipt_filename,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        quotation = (
            db.query(Quotation)
            .options(joinedload(Quotation.payments))
            .filter(Quotation.id == quotation_id)
            .first()
        )

        log_activity(
            db,
            "Abono registrado",
            f"Abono ${parsed_amount:.2f} en cotización #{quotation.id}",
        )

        return {
            "success": True,
            "payment": serialize_payment(payment),
            "total_paid": quotation.total_paid,
            "pending_balance": quotation.pending_balance,
        }

    except (PaymentValidationError, UploadValidationError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})


@router.get("/payments/{payment_id}/receipt")
async def get_payment_receipt(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    payment = _get_payment_or_404(db, payment_id)
    if not payment or not payment.transfer_receipt:
        return JSONResponse(status_code=404, content={"message": "Comprobante no encontrado."})

    path = resolve_payment_receipt_path(payment.transfer_receipt)
    if not path:
        return JSONResponse(status_code=404, content={"message": "Archivo no encontrado."})

    media_type = "application/pdf" if is_payment_receipt_pdf(payment.transfer_receipt) else "image/webp"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_quotation_access(request)
    if isinstance(user, RedirectResponse):
        return user

    payment = _get_payment_or_404(db, payment_id)
    if not payment:
        return JSONResponse(status_code=404, content={"success": False, "message": "Pago no encontrado."})

    quotation_id = payment.quotation_id
    receipt = payment.transfer_receipt

    db.delete(payment)
    db.commit()
    delete_payment_receipt(receipt)

    log_activity(
        db,
        "Abono eliminado",
        f"Abono eliminado de cotización #{quotation_id}",
    )

    return {"success": True, "quotation_id": quotation_id}
