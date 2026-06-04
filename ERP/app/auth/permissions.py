from fastapi import Request
from fastapi.responses import RedirectResponse

ROLE_ADMIN = "admin"
ROLE_VENTAS = "ventas"
ROLE_PRODUCCION = "produccion"

SUPPORTED_ROLES = [
    ROLE_ADMIN,
    ROLE_VENTAS,
    ROLE_PRODUCCION,
    "transporte",
    "bodega",
    "gerencia",
]


def role_required(request: Request, allowed_roles: list):
    from app.auth.auth_handler import login_required

    user = login_required(request)

    if isinstance(user, RedirectResponse):
        return user

    if user.role not in allowed_roles:
        return RedirectResponse(
            url="/login",
            status_code=302
        )

    return user
