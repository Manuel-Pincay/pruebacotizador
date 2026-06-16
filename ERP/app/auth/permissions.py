from fastapi import Request
from fastapi.responses import RedirectResponse

ROLE_ADMIN = "admin"
ROLE_VENTAS = "ventas"
ROLE_PRODUCCION = "produccion"
ROLE_DISENADOR = "disenador"
ROLE_DESPACHO = "despacho"
ROLE_TRANSPORTE = "transporte"

SUPPORTED_ROLES = [
    ROLE_ADMIN,
    ROLE_VENTAS,
    ROLE_PRODUCCION,
    ROLE_DISENADOR,
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
        "production_condensed", "fabrication_condensed", "inventory", "shipments", "users", "imports", "product_settings", "config",
        "design_dashboard", "design_pending", "design_orders",
    },
    ROLE_VENTAS: {
        "dashboard", "clients", "products_read", "quotations", "sales_tracking",
        "production_condensed", "fabrication_condensed",
        "shipments",
    },
    ROLE_PRODUCCION: {
        "dashboard", "production", "fabrication_condensed",
    },
    ROLE_DISENADOR: {
        "design_dashboard",
        "design_pending",
        "design_orders",
        "production_condensed",
        "fabrication_condensed",
        "shipments",
        "profile",
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


def get_login_redirect_url(role: str) -> str:
    if role == ROLE_DISENADOR:
        return "/design/dashboard"
    if role == ROLE_PRODUCCION:
        return "/"
    if role in {ROLE_DESPACHO, ROLE_TRANSPORTE}:
        return "/shipments"
    return "/"
