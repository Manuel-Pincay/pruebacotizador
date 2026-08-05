"""Fixtures compartidos para tests P0 del ERP."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

# Evita UnicodeEncodeError al importar app.database en consolas cp1252.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.session import sign_user_session
from app.database import SessionLocal
from app.models.client import Client
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.quotation_event import QuotationEvent
from app.models.user import User


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def unique_suffix() -> str:
    return uuid.uuid4().hex[:10]


@pytest.fixture
def ventas_user(db: Session, unique_suffix: str) -> Generator[User, None, None]:
    user = User(
        username=f"pytest_ventas_{unique_suffix}",
        full_name="Pytest Ventas",
        password=hash_password("test-pass-123"),
        role="ventas",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    try:
        yield user
    finally:
        db.rollback()
        from app.models.quotation_event import QuotationEvent

        db.query(QuotationEvent).filter(QuotationEvent.user_id == uid).update(
            {QuotationEvent.user_id: None},
            synchronize_session=False,
        )
        db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        db.commit()


@pytest.fixture
def produccion_user(db: Session, unique_suffix: str) -> Generator[User, None, None]:
    user = User(
        username=f"pytest_prod_{unique_suffix}",
        full_name="Pytest Produccion",
        password=hash_password("test-pass-123"),
        role="produccion",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    try:
        yield user
    finally:
        db.rollback()
        from app.models.quotation_event import QuotationEvent

        db.query(QuotationEvent).filter(QuotationEvent.user_id == uid).update(
            {QuotationEvent.user_id: None},
            synchronize_session=False,
        )
        db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        db.commit()


@pytest.fixture
def test_client_row(db: Session, unique_suffix: str) -> Generator[Client, None, None]:
    row = Client(
        name=f"Pytest Cliente {unique_suffix}",
        ruc_ci=f"99{unique_suffix[:11]}".ljust(13, "0")[:13],
        phone="0999999999",
        email=f"pytest_{unique_suffix}@example.com",
        client_type="persona",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    cid = row.id
    try:
        yield row
    finally:
        db.rollback()
        db.query(Client).filter(Client.id == cid).delete(synchronize_session=False)
        db.commit()


def _make_quotation(
    db: Session,
    client_row: Client,
    *,
    status: str = "pendiente",
) -> Quotation:
    quotation = Quotation(
        client_id=client_row.id,
        subtotal=100.0,
        discount=0.0,
        iva=12.0,
        total=112.0,
        shipping_cost=0.0,
        status=status,
    )
    db.add(quotation)
    db.flush()
    item = QuotationItem(
        quotation_id=quotation.id,
        quantity=2,
        detail="Producto pytest",
        measure="",
        theme="",
        color="",
        logo=False,
        logo_type="sin_logo",
        item_discount=0,
        unit_price=50.0,
        total=100.0,
    )
    db.add(item)
    db.commit()
    db.refresh(quotation)
    return quotation


def _delete_quotation_tree(db: Session, quotation_id: int) -> None:
    from app.models.production_order import ProductionOrder
    from app.models.production_order_history import ProductionOrderHistory
    from app.models.raw_material_movement import RawMaterialMovement
    from app.models.quotation_payment import QuotationPayment
    from app.models.quotation_design import QuotationDesign

    order_ids = [
        row[0]
        for row in db.query(ProductionOrder.id)
        .filter(ProductionOrder.quotation_id == quotation_id)
        .all()
    ]
    if order_ids:
        db.query(RawMaterialMovement).filter(
            RawMaterialMovement.production_order_id.in_(order_ids)
        ).update(
            {RawMaterialMovement.production_order_id: None},
            synchronize_session=False,
        )
        db.query(ProductionOrderHistory).filter(
            ProductionOrderHistory.production_order_id.in_(order_ids)
        ).delete(synchronize_session=False)
        db.query(ProductionOrder).filter(
            ProductionOrder.id.in_(order_ids)
        ).delete(synchronize_session=False)

    db.query(QuotationEvent).filter(
        QuotationEvent.quotation_id == quotation_id
    ).delete(synchronize_session=False)
    db.query(QuotationPayment).filter(
        QuotationPayment.quotation_id == quotation_id
    ).delete(synchronize_session=False)
    db.query(QuotationDesign).filter(
        QuotationDesign.quotation_id == quotation_id
    ).delete(synchronize_session=False)
    db.query(QuotationItem).filter(
        QuotationItem.quotation_id == quotation_id
    ).delete(synchronize_session=False)
    db.query(Quotation).filter(Quotation.id == quotation_id).delete(
        synchronize_session=False
    )
    db.commit()


@pytest.fixture
def pending_quotation(
    db: Session, test_client_row: Client
) -> Generator[Quotation, None, None]:
    quotation = _make_quotation(db, test_client_row, status="pendiente")
    qid = quotation.id
    try:
        yield quotation
    finally:
        db.rollback()
        _delete_quotation_tree(db, qid)


@pytest.fixture
def locked_quotation(
    db: Session, test_client_row: Client
) -> Generator[Quotation, None, None]:
    quotation = _make_quotation(db, test_client_row, status="produccion")
    qid = quotation.id
    try:
        yield quotation
    finally:
        db.rollback()
        _delete_quotation_tree(db, qid)


def user_cookie(username: str) -> dict[str, str]:
    return {"user": sign_user_session(username)}
