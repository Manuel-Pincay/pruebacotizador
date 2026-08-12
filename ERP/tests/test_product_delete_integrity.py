"""Archivar / borrar productos y mensajes de IntegrityError."""

from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError

from app.services.product_delete_service import (
    archive_product,
    product_delete_block_reason,
    reactivate_product,
)
from app.utils.db_errors import integrity_error_user_message


def test_integrity_fk_quotation_items_message():
    orig = Exception(
        '(1451, "Cannot delete or update a parent row: a foreign key constraint fails '
        "('erpinnova'.'quotation_items', CONSTRAINT 'quotation_items_ibfk_1' "
        "FOREIGN KEY ('product_id') REFERENCES 'products' ('id'))\")"
    )
    exc = IntegrityError("DELETE", {}, orig)
    msg = integrity_error_user_message(exc)
    assert "cotizaciones" in msg.lower()
    assert "pymysql" not in msg.lower()


def test_archive_sets_inactive():
    db = MagicMock()
    product = MagicMock(code="P1", active=True, name="Letrero")
    archive_product(db, product)
    assert product.active is False
    db.flush.assert_called()


def test_reactivate_sets_active():
    db = MagicMock()
    product = MagicMock(code="P1", active=False)
    reactivate_product(db, product)
    assert product.active is True


def test_cannot_archive_transport():
    db = MagicMock()
    product = MagicMock(code="SRV-TRANSPORTE", active=True)
    try:
        archive_product(db, product)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "transporte" in str(exc).lower()


def test_product_delete_suggests_archive_when_in_quotation():
    db = MagicMock()
    product = MagicMock(code="P1")

    def query_side_effect(model):
        m = MagicMock()
        # First call may be Product lookup inside product_delete_block_reason
        name = getattr(model, "__name__", str(model))
        if "Product" in name or getattr(model, "__tablename__", "") == "products":
            m.filter.return_value.first.return_value = product
            return m
        # QuotationItem / others → referenced
        m.filter.return_value.limit.return_value.first.return_value = (1,)
        return m

    db.query.side_effect = query_side_effect
    reason = product_delete_block_reason(db, 4)
    assert reason is not None
    assert "cotizaciones" in reason.lower() or "archiv" in reason.lower()
