def recalculate_quotation(
    quotation,
    db
):

    subtotal = 0.0
    for item in quotation.items:
        item_total = item.total
        if item_total is None:
            item_total = float((item.quantity or 0) * (item.unit_price or 0))
            item.total = item_total
        else:
            item_total = float(item_total)

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
