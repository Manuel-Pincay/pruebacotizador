"""Carrito de tienda pública (cookie firmada, sin sesión ERP)."""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config.settings import settings

CART_COOKIE = "store_cart"
CART_MAX_LINES = 40
CART_MAX_QTY = 999
CART_MAX_AGE = 60 * 60 * 24 * 14  # 14 días

_cart_serializer = URLSafeTimedSerializer(
    settings.secret_key,
    salt="store-cart-v1",
)


def _normalize_items(raw: list | None) -> list[dict]:
    items: list[dict] = []
    if not isinstance(raw, list):
        return items
    seen: dict[int, int] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("product_id"))
            qty = int(row.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        if pid < 1 or qty < 1:
            continue
        qty = min(qty, CART_MAX_QTY)
        seen[pid] = min(seen.get(pid, 0) + qty, CART_MAX_QTY)
        if len(seen) >= CART_MAX_LINES:
            break
    for pid, qty in seen.items():
        items.append({"product_id": pid, "quantity": qty})
    return items


def sign_cart(items: list[dict]) -> str:
    return _cart_serializer.dumps({"items": _normalize_items(items)})


def load_cart(cookie_value: str | None) -> list[dict]:
    if not cookie_value:
        return []
    try:
        data = _cart_serializer.loads(cookie_value, max_age=CART_MAX_AGE)
        return _normalize_items(data.get("items"))
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return []


def cart_add(items: list[dict], product_id: int, quantity: int = 1) -> list[dict]:
    try:
        pid = int(product_id)
        qty = int(quantity)
    except (TypeError, ValueError):
        return items
    if pid < 1 or qty < 1:
        return items
    qty = min(qty, CART_MAX_QTY)
    merged = {int(i["product_id"]): int(i["quantity"]) for i in items}
    merged[pid] = min(merged.get(pid, 0) + qty, CART_MAX_QTY)
    if len(merged) > CART_MAX_LINES and pid not in {int(i["product_id"]) for i in items}:
        return items
    return [{"product_id": k, "quantity": v} for k, v in merged.items()]


def cart_set_qty(items: list[dict], product_id: int, quantity: int) -> list[dict]:
    try:
        pid = int(product_id)
        qty = int(quantity)
    except (TypeError, ValueError):
        return items
    if pid < 1:
        return items
    if qty < 1:
        return [i for i in items if int(i["product_id"]) != pid]
    qty = min(qty, CART_MAX_QTY)
    found = False
    out: list[dict] = []
    for i in items:
        if int(i["product_id"]) == pid:
            out.append({"product_id": pid, "quantity": qty})
            found = True
        else:
            out.append(i)
    if not found:
        out.append({"product_id": pid, "quantity": qty})
    return out[:CART_MAX_LINES]


def cart_remove(items: list[dict], product_id: int) -> list[dict]:
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return items
    return [i for i in items if int(i["product_id"]) != pid]


def cart_cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": CART_MAX_AGE,
        "path": "/",
    }
