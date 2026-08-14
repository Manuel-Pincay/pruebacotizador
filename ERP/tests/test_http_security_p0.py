"""HTTP P0: auth, bloqueo de edición, duplicar, secretadmin."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.quotation_event import QuotationEvent
from app.models.user import User
from app.utils.urls import ERP_PREFIX, erp_path
from tests.conftest import user_cookie


def test_store_home_is_public(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "Acceso interno" in response.text


def test_legacy_erp_path_redirects(client: TestClient):
    response = client.get("/quotations/")
    assert response.status_code == 307
    assert response.headers.get("location", "").startswith(ERP_PREFIX + "/quotations")


def test_anonymous_quotations_redirects(client: TestClient):
    response = client.get(erp_path("/quotations/"))
    assert response.status_code in (302, 303)
    assert "/login" in response.headers.get("location", "")
    assert ERP_PREFIX in response.headers.get("location", "")


def test_anonymous_pdf_redirects(client: TestClient, pending_quotation: Quotation):
    response = client.get(erp_path(f"/quotations/{pending_quotation.id}/pdf"))
    assert response.status_code in (302, 303)
    assert "/login" in response.headers.get("location", "")


def test_produccion_cannot_access_quotations(
    client: TestClient, produccion_user: User
):
    response = client.get(
        erp_path("/quotations/"),
        cookies=user_cookie(produccion_user.username),
    )
    assert response.status_code in (302, 303)
    # Sin permiso de cotizaciones → login (comportamiento actual)
    assert "/login" in response.headers.get("location", "")


def test_ventas_can_open_quotation_detail(
    client: TestClient, ventas_user: User, pending_quotation: Quotation
):
    response = client.get(
        erp_path(f"/quotations/{pending_quotation.id}"),
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code == 200
    assert f"#{pending_quotation.id}" in response.text or str(pending_quotation.id) in response.text


def test_locked_quotation_rejects_quantity_update(
    client: TestClient, ventas_user: User, locked_quotation: Quotation, db: Session
):
    item = (
        db.query(QuotationItem)
        .filter(QuotationItem.quotation_id == locked_quotation.id)
        .first()
    )
    assert item is not None
    response = client.post(
        erp_path(f"/quotations/quotation-items/{item.id}/update-quantity"),
        data={"quantity": "5"},
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code == 403
    body = response.json()
    assert body.get("success") is False


def test_locked_quotation_allows_duplicate(
    client: TestClient,
    ventas_user: User,
    locked_quotation: Quotation,
    db: Session,
):
    source_id = locked_quotation.id
    response = client.post(
        erp_path(f"/quotations/{source_id}/duplicate"),
        cookies=user_cookie(ventas_user.username),
    )
    assert response.status_code in (302, 303)
    location = response.headers.get("location", "")
    assert "/quotations/" in location
    clone_id = int(location.rstrip("/").split("/")[-1].split("?")[0])
    assert clone_id != source_id

    db.rollback()
    clone = db.query(Quotation).filter(Quotation.id == clone_id).first()
    assert clone is not None, f"clone_id={clone_id} location={location!r}"
    assert (clone.status or "").lower() == "pendiente"
    items = (
        db.query(QuotationItem).filter(QuotationItem.quotation_id == clone_id).all()
    )
    assert len(items) >= 1

    # Cleanup clone (source lo limpia el fixture)
    db.query(QuotationEvent).filter(
        QuotationEvent.quotation_id.in_([clone_id, source_id])
    ).delete(synchronize_session=False)
    db.query(QuotationItem).filter(QuotationItem.quotation_id == clone_id).delete(
        synchronize_session=False
    )
    db.query(Quotation).filter(Quotation.id == clone_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_secretadmin_backup_requires_session(client: TestClient):
    response = client.post(erp_path("/secretadmin/backup"))
    assert response.status_code in (302, 303)
    assert "secretadmin" in response.headers.get("location", "")
