from fastapi import Request
from fastapi.responses import RedirectResponse

ROLE_ADMIN = "admin"
ROLE_VENTAS = "ventas"
ROLE_PRODUCCION = "produccion"
ROLE_DESPACHO = "despacho"
ROLE_TRANSPORTE = "transporte"

SUPPORTED_ROLES = [
    ROLE_ADMIN,
    ROLE_VENTAS,
    ROLE_PRODUCCION,
    ROLE_DESPACHO,
    ROLE_TRANSPORTE,
    "bodega",
    "gerencia",
]

ROLE_ALIASES = {
    ROLE_TRANSPORTE: ROLE_DESPACHO,
    ROLE_DESPACHO: ROLE_TRANSPORTE,
}

ROLE_PERMISSIONS = {
    ROLE_ADMIN: {
        "dashboard", "clients", "products", "quotations", "production",
        "inventory", "shipments", "users", "imports", "product_settings", "config",
    },
    ROLE_VENTAS: {
        "dashboard", "clients", "products_read", "quotations", "sales_tracking",
    },
    ROLE_PRODUCCION: {
        "dashboard", "production",
    },
    ROLE_DESPACHO: {
        "shipments",
    },
    ROLE_TRANSPORTE: {
        "shipments",
    },
}


def _expand_roles(allowed_roles: list) -> set:
    expanded = set(allowed_roles)
    for role in list(allowed_roles):
        alias = ROLE_ALIASES.get(role)
        if alias:
            expanded.add(alias)
    return expanded


def role_required(request: Request, allowed_roles: list):
    from app.auth.auth_handler import login_required

    user = login_required(request)

    if isinstance(user, RedirectResponse):
        return user

    if not getattr(user, "active", True):
        return RedirectResponse(url="/login", status_code=302)

    expanded = _expand_roles(allowed_roles)
    if user.role not in expanded:
        return RedirectResponse(url="/login", status_code=302)

    return user


def has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    if permission in perms:
        return True
    if permission == "products_read" and "products" in perms:
        return True
    alias = ROLE_ALIASES.get(role)
    if alias:
        return permission in ROLE_PERMISSIONS.get(alias, set())
    return False
