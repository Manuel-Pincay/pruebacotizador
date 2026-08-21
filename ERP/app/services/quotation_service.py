from app.services.tax_service import is_shipping_item


def compute_item_total(quantity, unit_price, item_discount=0) -> float:
    gross = float(quantity or 0) * float(unit_price or 0)
    discount = float(item_discount or 0)
    return gross * (1 - discount / 100)


# Estados de cotización donde ya no se editan productos / totales
ADVANCED_QUOTATION_STATUSES = {
    "produccion",
    "enviada",
    "enviado",
    "entregada",
    "entregado",
}


def quotation_edit_lock_reason(quotation) -> str | None:
    """Motivo por el que no se puede editar contenido. None = editable.
    Duplicar no usa este bloqueo.
    """
    if not quotation:
        return "Cotización no encontrada"

    if getattr(quotation, "electronic_invoice", None):
        return "Ya está facturada. Puedes duplicarla si necesitas una nueva versión."

    st = (quotation.status or "").lower().strip()
    if st in {"cancelada", "vencida"}:
        return "Está cancelada o vencida. Reactívala o duplícala para continuar."

    if st in ADVANCED_QUOTATION_STATUSES:
        return "Está en producción avanzada o entregada. Usa Duplicar para una nueva cotización."

    po = getattr(quotation, "production_order", None)
    if po and po.status:
        from app.services.production_order_service import (
            DESIGN_PHASE_STATUSES,
            normalize_status,
        )

        po_st = normalize_status(po.status)
        if po_st not in DESIGN_PHASE_STATUSES and po_st != "cancelado":
            return (
                "La orden de producción ya avanzó más allá de diseño. "
                "Usa Duplicar si necesitas cambiar productos."
            )

    return None


def quotation_can_edit_content(quotation) -> bool:
    return quotation_edit_lock_reason(quotation) is None


def recalculate_quotation(
    quotation,
    db
):
    products_subtotal = 0.0
    shipping = 0.0
    for item in quotation.items:
        item_discount = getattr(item, "item_discount", 0) or 0
        item_total = compute_item_total(
            item.quantity,
            item.unit_price,
            item_discount,
        )
        item.total = item_total
        if is_shipping_item(item):
            shipping += item_total
        else:
            products_subtotal += item_total

    quotation.subtotal = products_subtotal

    discount = quotation.discount or 0

    iva = quotation.iva or 0

    subtotal_discount = (
        products_subtotal -
        (
            products_subtotal *
            discount / 100
        )
    )

    quotation.total = subtotal_discount * (1 + iva / 100) + shipping

    db.commit()
