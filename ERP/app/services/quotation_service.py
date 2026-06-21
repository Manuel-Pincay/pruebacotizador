def compute_item_total(quantity, unit_price, item_discount=0) -> float:
    gross = float(quantity or 0) * float(unit_price or 0)
    discount = float(item_discount or 0)
    return gross * (1 - discount / 100)


def recalculate_quotation(
    quotation,
    db
):

    subtotal = 0.0
    for item in quotation.items:
        item_discount = getattr(item, "item_discount", 0) or 0
        item_total = compute_item_total(
            item.quantity,
            item.unit_price,
            item_discount,
        )
        item.total = item_total
        subtotal += item_total

    quotation.subtotal = subtotal

    discount = quotation.discount or 0

    iva = quotation.iva or 0

    subtotal_discount = (
        subtotal -
        (
            subtotal *
            discount / 100
        )
    )

    shipping = float(getattr(quotation, "shipping_cost", None) or 0)

    quotation.total = (
        subtotal_discount *
        (
            1 +
            iva / 100
        )
    ) + shipping

    db.commit()
