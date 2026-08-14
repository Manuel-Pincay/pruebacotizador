"""Prefijos de URL: tienda en / y ERP en /erp."""

from __future__ import annotations

from fastapi.responses import RedirectResponse

ERP_PREFIX = "/erp"

# Primer segmento de paths legacy del ERP (sin el prefijo /erp).
# Usado por middleware para redirigir /quotations → /erp/quotations.
ERP_LEGACY_ROOTS = frozenset(
    {
        "login",
        "logout",
        "quotations",
        "clients",
        "products",
        "product-settings",
        "payments",
        "production",
        "design",
        "inventory",
        "shipments",
        "users",
        "secretadmin",
        "imports",
        "billing",
        "reports",
        "notifications",
        "store-cms",
    }
)


def erp_path(path: str = "/") -> str:
    """Convierte '/quotations' → '/erp/quotations'. Idempotente si ya tiene /erp."""
    if not path:
        return ERP_PREFIX + "/"
    if not path.startswith("/"):
        path = "/" + path
    if path == ERP_PREFIX or path.startswith(ERP_PREFIX + "/"):
        return path
    if path == "/":
        return ERP_PREFIX + "/"
    return ERP_PREFIX + path


def erp_redirect(path: str, status_code: int = 302) -> RedirectResponse:
    return RedirectResponse(url=erp_path(path), status_code=status_code)


def strip_erp_prefix(path: str) -> str:
    """'/erp/quotations' → '/quotations' (para nav_active en templates)."""
    if path == ERP_PREFIX or path == ERP_PREFIX + "/":
        return "/"
    if path.startswith(ERP_PREFIX + "/"):
        return path[len(ERP_PREFIX) :] or "/"
    return path
