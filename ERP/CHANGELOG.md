# Registro de cambios — Auditoría ERP

## Fase 2 — Correcciones críticas y altas

- **`app/routes/quotations.py`**: Reordenadas rutas literales (`/completed`, `/catalog`, `/tracking`, `/quotation-items/*`) antes de `/{quotation_id}`. Importado `recalculate_quotation`. Auth en todos los endpoints. Corregido `previous_stock` en inventario. Añadido redirect en `shipping_quotation`. PDF protegido con auth.
- **`app/services/pdf_sections.py`**: Path del logo corregido (`uploads/logos/`).
- **`app/utils/pdf.py`**: Eliminado import erróneo.
- **`app/templates/partials/client_catalog_table.html`**: Template creado.
- **`app/routes/products.py`**: Auth en APIs y mutaciones. Validación de imágenes.
- **`app/routes/product_settings.py`**: Auth admin en las 15 rutas.
- **`app/routes/production.py`**: Auth en `move` y `update`. Helpers centralizados.
- **`app/routes/shipments.py`**, **`imports.py`**: Auth en endpoints faltantes.
- **`uploads/products/*.py`**: Archivo malicioso eliminado.

## Fase 3 — Sistema de roles

- **`app/auth/permissions.py`**: Matriz `ROLE_PERMISSIONS`, alias `despacho`/`transporte`, validación `User.active`.
- **`app/auth/security.py`**: bcrypt para nuevos hashes; compatibilidad SHA256 legacy.

## Fase 4 — Módulo Ventas

- **`GET /quotations/tracking`**: Vista de seguimiento comercial con pipeline.
- **`app/templates/sales_tracking.html`**: Template del pipeline.
- **`app/routes/dashboard.py`**: KPIs pendientes y aprobadas para rol ventas.
- **`app/templates/base.html`**: Enlace Seguimiento Comercial en sidebar ventas.

## Fase 5 — Módulo Producción

- Rol `produccion`: acceso a dashboard, listado y detalle (kanban/calendario solo admin).
- **`joinedload`**: Reduce N+1 en listados de producción.

## Fase 6 — Flujo cotización → producción → despacho

- **`app/services/production_helpers.py`**: `ensure_production_order`, validaciones de transición.
- **`app/utils/status_helpers.py`**: Normalización de estados enviada/enviado.
- Estados de envío unificados a `enviado` / `entregado` en nuevas transiciones.

## Fase 7 — UX y rendimiento

- Una sola llamada a `inject_global_config()` en `base.html`.
- Consultas con `joinedload` en cotizaciones y producción.

## Archivos nuevos

- `app/utils/status_helpers.py`
- `app/utils/upload_helpers.py`
- `app/services/production_helpers.py`
- `app/templates/partials/client_catalog_table.html`
- `app/templates/sales_tracking.html`

## Notas hosting (2026-06)

- Cookies de sesión firmadas (`app/auth/session.py`); sesiones antiguas siguen válidas hasta re-login.
- Secretos configurables vía `.env` (ver `.env.example`); valores actuales como fallback.
- Paginación en `/quotations` y `/clients/api/list` (`ERP_PER_PAGE`, default 20).

## Notas

- URLs existentes sin cambios.
- Tablas y lógica de negocio core preservadas.
- Contraseñas legacy SHA256 siguen funcionando; nuevas usan bcrypt.
