"""Helpers de sesión portal para tests de tienda."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.services.store_auth import CLIENT_COOKIE, register_portal_client, sign_client_session


def portal_cookies(db: Session, *, email: str | None = None) -> tuple[Client, dict]:
    suffix = uuid.uuid4().hex[:8]
    email = email or f"portal_{suffix}@example.com"
    client, _code = register_portal_client(
        db,
        name=f"Portal {suffix}",
        email=email,
        phone="0991112233",
        password="clave123",
        auto_activate=True,
    )
    db.commit()
    db.refresh(client)
    return client, {CLIENT_COOKIE: sign_client_session(client.id)}


def login_portal(client_http: TestClient, email: str, password: str = "clave123") -> dict:
    resp = client_http.post(
        "/tienda/cuenta/login",
        data={"email": email, "password": password, "next": "/tienda/cuenta/"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    return {CLIENT_COOKIE: resp.cookies.get(CLIENT_COOKIE)}
