"""Unitarios P0: bloqueo de edición de cotizaciones."""

from types import SimpleNamespace

from app.services.quotation_service import (
    compute_item_total,
    quotation_can_edit_content,
    quotation_edit_lock_reason,
)


def test_editable_pending():
    q = SimpleNamespace(status="pendiente", electronic_invoice=None, production_order=None)
    assert quotation_edit_lock_reason(q) is None
    assert quotation_can_edit_content(q) is True


def test_locked_when_invoiced():
    q = SimpleNamespace(
        status="aprobada",
        electronic_invoice=object(),
        production_order=None,
    )
    reason = quotation_edit_lock_reason(q)
    assert reason is not None
    assert "facturada" in reason.lower()


def test_locked_advanced_status():
    for status in ("produccion", "enviada", "enviado", "entregada", "entregado"):
        q = SimpleNamespace(
            status=status,
            electronic_invoice=None,
            production_order=None,
        )
        reason = quotation_edit_lock_reason(q)
        assert reason is not None, status
        assert quotation_can_edit_content(q) is False


def test_locked_cancelled_or_expired():
    for status in ("cancelada", "vencida"):
        q = SimpleNamespace(status=status, electronic_invoice=None, production_order=None)
        assert quotation_edit_lock_reason(q) is not None


def test_editable_when_po_in_design():
    q = SimpleNamespace(
        status="aprobada",
        electronic_invoice=None,
        production_order=SimpleNamespace(status="diseno"),
    )
    assert quotation_edit_lock_reason(q) is None


def test_locked_when_po_beyond_design():
    q = SimpleNamespace(
        status="aprobada",
        electronic_invoice=None,
        production_order=SimpleNamespace(status="produccion"),
    )
    reason = quotation_edit_lock_reason(q)
    assert reason is not None
    assert "producción" in reason.lower() or "duplicar" in reason.lower()


def test_missing_quotation():
    assert quotation_edit_lock_reason(None) == "Cotización no encontrada"


def test_compute_item_total_discount_edges():
    assert compute_item_total(2, 50, 0) == 100.0
    assert compute_item_total(2, 50, 50) == 50.0
    assert compute_item_total(2, 50, 100) == 0.0
