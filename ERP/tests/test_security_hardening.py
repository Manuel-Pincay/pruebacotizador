"""Tests de endurecimiento de seguridad (POST mutables, uploads, create)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.models.user import User
from tests.conftest import _delete_quotation_tree, user_cookie


def test_approve_get_rejected(client: TestClient, ventas_user: User, pending_quotation: Quotation):
    response = client.get(
        f"/quotations/{pending_quotation.id}/approve",
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code == 405


def test_approve_post_ok(
    client: TestClient, ventas_user: User, pending_quotation: Quotation, db: Session
):
    qid = pending_quotation.id
    response = client.post(
        f"/quotations/{qid}/approve",
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code in (302, 303)
    assert f"/quotations/{qid}" in response.headers.get("location", "")
    db.rollback()
    q = db.query(Quotation).filter(Quotation.id == qid).first()
    assert q is not None
    assert (q.status or "").lower() == "aprobada"


def test_uploads_payments_not_public(client: TestClient):
    response = client.get("/uploads/payments/does-not-exist.webp")
    assert response.status_code == 404


def test_create_rejects_zero_quantity(
    client: TestClient, ventas_user: User, test_client_row
):
    import json

    payload = {
        "client_id": str(test_client_row.id),
        "subtotal": "100",
        "discount": "0",
        "iva": "12",
        "total": "112",
        "shipping_cost": "0",
        "items": json.dumps(
            [
                {
                    "type": "custom",
                    "detail": "Item inválido",
                    "quantity": 0,
                    "price": 10,
                    "item_discount": 0,
                }
            ]
        ),
    }
    response = client.post(
        "/quotations/create",
        data=payload,
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code == 400


def test_create_clamps_item_discount(
    client: TestClient, ventas_user: User, test_client_row, db: Session
):
    import json

    payload = {
        "client_id": str(test_client_row.id),
        "subtotal": "100",
        "discount": "150",
        "iva": "0",
        "total": "100",
        "shipping_cost": "0",
        "items": json.dumps(
            [
                {
                    "type": "custom",
                    "detail": "Item descuento alto",
                    "quantity": 1,
                    "price": 100,
                    "item_discount": 150,
                }
            ]
        ),
    }
    response = client.post(
        "/quotations/create",
        data=payload,
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code in (302, 303)
    location = response.headers.get("location", "")
    assert "/quotations/" in location
    qid = int(location.rstrip("/").split("/")[-1].split("?")[0])
    db.rollback()
    q = db.query(Quotation).filter(Quotation.id == qid).first()
    assert q is not None
    assert float(q.discount or 0) <= 100.0
    assert q.items
    assert float(q.items[0].item_discount or 0) <= 100.0
    _delete_quotation_tree(db, qid)


def test_production_secrets_validator():
    from app.config.settings import Settings

    s = Settings.__new__(Settings)
    s.app_env = "production"
    s.secret_key = "erp-dev-secret-change-in-production"
    s.secretadmin_password = "203211"
    try:
        s.validate_security_settings()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "ERP_SECRET_KEY" in str(exc)
