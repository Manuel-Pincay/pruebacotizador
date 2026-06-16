"""Normalización de estados de cotización (compatibilidad enviada/enviado)."""


def expand_quotation_statuses(statuses: list[str]) -> list[str]:
    expanded = set()
    for s in statuses:
        s = s.strip().lower()
        if s in ("enviada", "enviado"):
            expanded.update(["enviada", "enviado"])
        elif s in ("entregada", "entregado"):
            expanded.update(["entregada", "entregado"])
        else:
            expanded.add(s)
    return list(expanded)


def expand_status_filter(status: str) -> list[str]:
    if not status:
        return []
    statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
    return expand_quotation_statuses(statuses)


SENT_STATUSES = ["enviada", "enviado"]
DELIVERED_STATUSES = ["entregada", "entregado"]
COMPLETED_STATUSES = ["produccion"] + SENT_STATUSES + DELIVERED_STATUSES

PRODUCTION_STAGE_LABELS = {
    "pendiente": "Pendiente",
    "diseño": "En Producción",
    "produccion": "En Producción",
    "empacado": "Terminada",
    "enviado": "Terminada",
    "entregado": "Terminada",
}
