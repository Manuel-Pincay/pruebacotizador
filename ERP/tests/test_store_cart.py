"""Tienda: catálogo, carrito y checkout → cotización source=store."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.services.store_auth import CLIENT_COOKIE
from app.services.store_cart import CART_COOKIE, cart_add, sign_cart
from tests.conftest import _delete_quotation_tree
from tests.store_portal_helpers import portal_cookies


def _make_store_product(db: Session, *, visible: bool = True, price: float = 25.0) -> Product:
    suffix = uuid.uuid4().hex[:8]
    product = Product(
        code=f"ST{suffix}",
        name=f"Producto Tienda {suffix}",
        description="Demo tienda",
        category="Demo",
        price=price,
        cost=10,
        stock=10,
        custom=False,
        active=True,
        store_visible=visible,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_catalog_shows_only_store_visible(client: TestClient, db: Session):
    visible = _make_store_product(db, visible=True)
    hidden = _make_store_product(db, visible=False)
    try:
        response = client.get("/tienda")
        assert response.status_code == 200
        assert visible.name in response.text
        assert hidden.name not in response.text
    finally:
        db.query(Product).filter(Product.id.in_([visible.id, hidden.id])).delete(
            synchronize_session=False
        )
        db.commit()


def test_cart_requires_login(client: TestClient, db: Session):
    product = _make_store_product(db)
    try:
        add = client.post(
            "/tienda/carrito/agregar",
            data={"product_id": str(product.id), "quantity": "1"},
            follow_redirects=False,
        )
        assert add.status_code in (302, 303)
        assert "/tienda/cuenta/login" in add.headers.get("location", "")
    finally:
        db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        db.commit()


def test_cart_add_and_checkout_creates_store_quotation(client: TestClient, db: Session):
    product = _make_store_product(db, price=12.5)
    portal, cookies = portal_cookies(db)
    qid = None
    try:
        add = client.post(
            "/tienda/carrito/agregar",
            data={"product_id": str(product.id), "quantity": "2", "next": "/tienda/carrito"},
            cookies=cookies,
            follow_redirects=False,
        )
        assert add.status_code in (302, 303)
        assert CART_COOKIE in add.cookies
        jar = {**cookies, **add.cookies}

        cart = client.get("/tienda/carrito", cookies=jar)
        assert cart.status_code == 200
        assert product.name in cart.text

        checkout = client.post(
            "/tienda/checkout",
            data={"phone": "0991112233", "address": "Calle Demo"},
            cookies=jar,
            follow_redirects=False,
        )
        assert checkout.status_code in (302, 303)
        location = checkout.headers.get("location", "")
        assert "/tienda/pedido/" in location
        parts = location.split("?")[0].rstrip("/").split("/")
        qid = int(parts[-2])
        token = parts[-1]
        assert token

        db.rollback()
        q = db.query(Quotation).filter(Quotation.id == qid).first()
        assert q is not None
        assert (q.source or "") == "store"
        assert q.client_id == portal.id
        assert q.store_access_token == token
        assert (q.status or "").lower() == "pendiente"
        assert abs(float(q.total or 0) - 25.0) < 0.01 or abs(float(q.subtotal or 0) - 25.0) < 0.01
        assert len(q.items) == 1
        assert q.items[0].quantity == 2

        account = client.get("/tienda/cuenta/", cookies=cookies)
        assert account.status_code == 200
        assert f"#{qid}" in account.text or str(qid) in account.text
    finally:
        if qid:
            _delete_quotation_tree(db, qid)
        db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        db.query(Client).filter(Client.id == portal.id).delete(synchronize_session=False)
        db.commit()


def test_hidden_product_cannot_be_added(client: TestClient, db: Session):
    product = _make_store_product(db, visible=False)
    try:
        items = cart_add([], product.id, 1)
        cookie = sign_cart(items)
        response = client.get("/tienda/carrito", cookies={CART_COOKIE: cookie})
        assert response.status_code == 200
        assert product.name not in response.text
    finally:
        db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        db.commit()
