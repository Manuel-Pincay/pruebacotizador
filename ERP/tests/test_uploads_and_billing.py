"""Unitarios P0: uploads y validación previa a facturar."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.invoice_service import validate_quotation_for_billing
from app.utils.image_storage import (
    UploadValidationError,
    validate_receipt_content,
    validate_receipt_filename,
    validate_upload_filename,
)


def test_upload_filename_allows_images():
    assert validate_upload_filename("foto.PNG") == "png"
    assert validate_upload_filename("a.webp") == "webp"


def test_upload_filename_blocks_dangerous():
    for name in ("x.exe", "a.php", "b.svg", "c.js", "d.pdf"):
        with pytest.raises(UploadValidationError):
            validate_upload_filename(name)


def test_receipt_filename_allows_pdf():
    assert validate_receipt_filename("comprobante.PDF") == "pdf"


def test_receipt_content_mismatch():
    with pytest.raises(UploadValidationError):
        validate_receipt_content("pdf", b"not-a-pdf")


def test_receipt_content_pdf_ok():
    validate_receipt_content("pdf", b"%PDF-1.4 fake")


def _mock_db_no_sri():
    db = MagicMock()
    # CompanyConfig / SriCertificate → None
    query = MagicMock()
    query.first.return_value = None
    query.order_by.return_value.first.return_value = None
    db.query.return_value = query
    return db


def test_billing_rejects_unpaid():
    q = SimpleNamespace(
        status="aprobada",
        electronic_invoice=None,
        payment_status="sin_abono",
        items=[SimpleNamespace(id=1, detail="Item", product=None)],
        client=None,
    )
    result = validate_quotation_for_billing(_mock_db_no_sri(), q)
    codes = {e.campo for e in result.errores}
    assert "cotizacion.pago" in codes


def test_billing_rejects_already_invoiced():
    q = SimpleNamespace(
        status="aprobada",
        electronic_invoice=object(),
        payment_status="pagada",
        items=[SimpleNamespace(id=1, detail="Item", product=None)],
        client=None,
    )
    result = validate_quotation_for_billing(_mock_db_no_sri(), q)
    codes = {e.campo for e in result.errores}
    assert "cotizacion.factura" in codes


def test_billing_rejects_wrong_status():
    q = SimpleNamespace(
        status="pendiente",
        electronic_invoice=None,
        payment_status="pagada",
        items=[SimpleNamespace(id=1, detail="Item", product=None)],
        client=None,
    )
    result = validate_quotation_for_billing(_mock_db_no_sri(), q)
    codes = {e.campo for e in result.errores}
    assert "cotizacion.estado" in codes
