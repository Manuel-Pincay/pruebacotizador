def recalculate_quotation(
    quotation,
    db
):

    subtotal = sum(
        item.total
        for item in quotation.items
    )

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

    quotation.total = (
        subtotal_discount *
        (
            1 +
            iva / 100
        )
    )

    db.commit()