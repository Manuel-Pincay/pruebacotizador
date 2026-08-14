"""Pago tienda: registro pendiente + confirmación staff + timeline pedido."""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.services.store_order_service import store_order_status_code, store_payment_summary
from app.utils.urls import erp_path
from tests.conftest import _delete_quotation_tree, user_cookie
from tests.store_portal_helpers import portal_cookies


def _png_bytes() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _store_product(db: Session) -> Product:
    suffix = uuid.uuid4().hex[:8]
    product = Product(
        code=f"PAY{suffix}",
        name=f"Pay Product {suffix}",
        price=40.0,
        cost=10,
        stock=5,
        custom=False,
        active=True,
        store_visible=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_store_payment_pending_then_confirm(
    client: TestClient, db: Session, ventas_user
):
    product = _store_product(db)
    portal, cookies = portal_cookies(db)
    qid = None
    try:
        add = client.post(
            "/tienda/carrito/agregar",
            data={"product_id": str(product.id), "quantity": "1"},
            cookies=cookies,
            follow_redirects=False,
        )
        jar = {**cookies, **add.cookies}
        checkout = client.post(
            "/tienda/checkout",
            data={"phone": "0998887766"},
            cookies=jar,
            follow_redirects=False,
        )
        location = checkout.headers.get("location", "")
        parts = location.split("?")[0].rstrip("/").split("/")
        qid = int(parts[-2])
        token = parts[-1]

        pay = client.post(
            f"/tienda/pedido/{qid}/{token}/pago",
            data={"amount": "40.00", "reference": "TRX-1"},
            files={
                "transfer_receipt": ("comp.png", io.BytesIO(_png_bytes()), "image/png")
            },
            follow_redirects=False,
        )
        assert pay.status_code in (302, 303)

        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        assert q is not None
        assert q.has_pending_payment_verification is True
        assert float(q.total_paid) == 0.0
        assert store_payment_summary(q)["code"] == "waiting"
        assert store_order_status_code(q) == "receptado"

        payment = q.payments[0]
        confirm = client.post(
            erp_path(f"/payments/{payment.id}/confirm"),
            cookies=user_cookie(ventas_user.username),
            follow_redirects=False,
        )
        assert confirm.status_code in (302, 303)

        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        assert float(q.total_paid) == 40.0
        assert q.payment_status == "pagada"
        assert store_payment_summary(q)["code"] == "confirmed"

        page = client.get(f"/tienda/pedido/{qid}/{token}")
        assert page.status_code == 200
        assert "Pago confirmado" in page.text
        assert "Receptado" in page.text
    finally:
        if qid:
            _delete_quotation_tree(db, qid)
        db.query(Product).filter(Product.id == product.id).delete(
            synchronize_session=False
        )
        db.query(Client).filter(Client.id == portal.id).delete(synchronize_session=False)
        db.commit()


def test_order_page_requires_token(client: TestClient, db: Session):
    product = _store_product(db)
    portal, cookies = portal_cookies(db)
    qid = None
    try:
        add = client.post(
            "/tienda/carrito/agregar",
            data={"product_id": str(product.id), "quantity": "1"},
            cookies=cookies,
            follow_redirects=False,
        )
        jar = {**cookies, **add.cookies}
        checkout = client.post(
            "/tienda/checkout",
            data={"phone": "0990001111"},
            cookies=jar,
            follow_redirects=False,
        )
        parts = checkout.headers.get("location", "").split("?")[0].rstrip("/").split("/")
        qid = int(parts[-2])
        bad = client.get(f"/tienda/pedido/{qid}", follow_redirects=False)
        assert bad.status_code in (302, 303)
    finally:
        if qid:
            _delete_quotation_tree(db, qid)
        db.query(Product).filter(Product.id == product.id).delete(
            synchronize_session=False
        )
        db.query(Client).filter(Client.id == portal.id).delete(synchronize_session=False)
        db.commit()


def test_store_order_auto_cancels_without_receipt(client: TestClient, db: Session):
    from datetime import datetime, timedelta

    from app.services.store_order_service import (
        STORE_RECEIPT_DEADLINE_DAYS,
        maybe_auto_cancel_store_order,
        store_order_status_code,
        store_payment_summary,
    )

    product = _store_product(db)
    portal, cookies = portal_cookies(db)
    qid = None
    try:
        add = client.post(
            "/tienda/carrito/agregar",
            data={"product_id": str(product.id), "quantity": "1"},
            cookies=cookies,
            follow_redirects=False,
        )
        jar = {**cookies, **add.cookies}
        checkout = client.post(
            "/tienda/checkout",
            data={"phone": "0992223344"},
            cookies=jar,
            follow_redirects=False,
        )
        parts = checkout.headers.get("location", "").split("?")[0].rstrip("/").split("/")
        qid = int(parts[-2])
        token = parts[-1]

        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        q.created_at = datetime.utcnow() - timedelta(days=STORE_RECEIPT_DEADLINE_DAYS + 1)
        db.commit()

        assert maybe_auto_cancel_store_order(db, q) is True
        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        assert q.status == "cancelada"
        assert store_order_status_code(q) == "cancelado"
        assert store_payment_summary(q)["can_upload"] is False

        page = client.get(f"/tienda/pedido/{qid}/{token}")
        assert page.status_code == 200
        assert "Pedido cancelado" in page.text
        assert "Enviar comprobante" not in page.text

        blocked = client.post(
            f"/tienda/pedido/{qid}/{token}/pago",
            data={"amount": "40.00", "reference": "X"},
            files={
                "transfer_receipt": ("comp.png", io.BytesIO(_png_bytes()), "image/png")
            },
            follow_redirects=False,
        )
        assert blocked.status_code in (302, 303)
        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        assert len(q.payments or []) == 0
    finally:
        if qid:
            _delete_quotation_tree(db, qid)
        db.query(Product).filter(Product.id == product.id).delete(
            synchronize_session=False
        )
        db.query(Client).filter(Client.id == portal.id).delete(synchronize_session=False)
        db.commit()
