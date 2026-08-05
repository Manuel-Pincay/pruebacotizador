"""Manejo global de errores: páginas legibles en lugar de pantalla negra."""
from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import settings

logger = logging.getLogger("erp.errors")
_templates = Jinja2Templates(directory="app/templates")


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    path = request.url.path
    if path.startswith("/api/") or path.endswith(".json"):
        return True
    if "application/json" in accept and "text/html" not in accept.lower():
        return True
    return False


def _hints_for_exception(exc: Exception) -> list[str]:
    text = f"{type(exc).__name__} {exc}".lower()
    hints: list[str] = []

    if isinstance(exc, OperationalError) or "can't connect" in text or "connection refused" in text:
        hints.extend([
            "Verifique que MySQL esté en ejecución (servicios.msc → MySQL80).",
            "Revise DATABASE_URL en el archivo .env (usuario, clave, host y base).",
            "Ejecute: venv\\Scripts\\python.exe scripts\\verify_startup.py",
        ])
    elif isinstance(exc, ProgrammingError) or "doesn't exist" in text or "unknown column" in text:
        hints.extend([
            "El esquema de la base puede estar desactualizado.",
            "Ejecute: venv\\Scripts\\python.exe scripts\\ensure_database.py",
            "O reinicie con iniciar_servidor.bat para aplicar migraciones.",
        ])
    elif "erp_encryption_key" in text or "encryption" in text:
        hints.append("Configure ERP_ENCRYPTION_KEY en .env (iniciar_servidor.bat la genera automáticamente).")
    elif "page.items" in text or "pagination" in text:
        hints.append("Reinicie el servidor (Ctrl+C y luego iniciar_servidor.bat) para cargar la versión actualizada.")

    if not hints:
        hints.append("Si el problema continúa, reinicie el servidor y revise la consola donde corre el ERP.")
    return hints


def _describe_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, StarletteHTTPException):
        titles = {404: "Página no encontrada", 403: "Acceso denegado", 401: "Sesión requerida"}
        title = titles.get(exc.status_code, f"Error HTTP {exc.status_code}")
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return title, detail

    if isinstance(exc, RequestValidationError):
        parts: list[str] = []
        for err in exc.errors():
            loc = " → ".join(str(x) for x in err.get("loc", ()) if x != "body")
            msg = err.get("msg", "valor inválido")
            if loc:
                parts.append(f"{loc}: {msg}")
            else:
                parts.append(msg)
        message = "; ".join(parts) if parts else "Revise los campos del formulario e intente de nuevo."
        return "Datos inválidos", message

    if isinstance(exc, SQLAlchemyError):
        return "Error de base de datos", str(getattr(exc, "orig", exc))

    return type(exc).__name__, str(exc) or "Ocurrió un error inesperado."


def _build_payload(request: Request, exc: Exception, *, status_code: int) -> dict[str, Any]:
    title, message = _describe_exception(exc)
    hints = _hints_for_exception(exc)
    show_details = not settings.is_production

    payload: dict[str, Any] = {
        "title": title,
        "message": message,
        "status_code": status_code,
        "path": str(request.url.path),
        "hints": hints,
        "show_details": show_details,
        "detail": message if show_details else None,
        "traceback": traceback.format_exc() if show_details else None,
    }
    return payload


def _render_error_page(request: Request, payload: dict[str, Any], status_code: int) -> HTMLResponse:
    return _templates.TemplateResponse(
        request=request,
        name="errors/page.html",
        context=payload,
        status_code=status_code,
    )


def _error_response(request: Request, exc: Exception, *, status_code: int) -> Response:
    payload = _build_payload(request, exc, status_code=status_code)
    logger.exception(
        "Error %s en %s %s: %s",
        status_code,
        request.method,
        request.url.path,
        payload["message"],
    )
    if status_code >= 500:
        try:
            from app.auth.session import resolve_user_session
            from app.services.notification_service import NotificationService

            username = resolve_user_session(request.cookies.get("user")) or "—"
            NotificationService.notify_system_error(
                module=f"{request.method} {payload['path']}",
                detail=f"{payload['title']}: {payload['message']}",
                user=username,
            )
        except Exception:
            pass
    if _wants_json(request):
        return JSONResponse(
            status_code=status_code,
            content={
                "error": payload["title"],
                "message": payload["message"],
                "hints": payload["hints"],
                "detail": payload.get("detail"),
                "path": payload["path"],
            },
        )
    return _render_error_page(request, payload, status_code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return _error_response(request, exc, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return _error_response(request, exc, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        return _error_response(request, exc, status_code=500)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return _error_response(request, exc, status_code=500)
