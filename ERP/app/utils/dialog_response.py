from __future__ import annotations

import json

from fastapi.responses import HTMLResponse


def dialog_message_response(
    message: str,
    *,
    dialog_type: str = "error",
    title: str = "Error",
    action: str = "window.history.back();",
    status_code: int = 400,
) -> HTMLResponse:
    """Página mínima que muestra un modal ErpDialog y ejecuta una acción."""
    safe_message = json.dumps(message, ensure_ascii=False)
    safe_title = json.dumps(title, ensure_ascii=False)
    safe_action = action.strip()
    if not safe_action.endswith(";"):
        safe_action += ";"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <script src="/static/js/erp-dialogs.js"></script>
</head>
<body>
<script>
  ErpDialog.{dialog_type}({safe_message}, {safe_title}).then(function () {{
    {safe_action}
  }});
</script>
</body>
</html>"""

    return HTMLResponse(content=html, status_code=status_code)
