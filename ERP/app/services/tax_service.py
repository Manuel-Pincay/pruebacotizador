from app.utils.sri_constants import codigo_iva_from_tarifa


def round2(value) -> float:
    return round(float(value or 0), 2)


def parse_tarifa_iva(value, default: float = 0.0) -> float:
    """Permite tarifa 0% sin tratarlo como falsy."""
    if value is None or value == "":
        return float(default)
    return float(value)


def default_tarifa_from_config(config) -> float:
    """IVA comercial de cotizaciones (0% es válido). No usar para factura SRI."""
    if config is None:
        return 0.0
    return parse_tarifa_iva(getattr(config, "iva_default", None), default=0.0)


def default_sri_tarifa_from_config(config) -> float:
    """IVA SRI al facturar desde cotización (p. ej. 15%). Independiente del cotizador."""
    if config is None:
        return 15.0
    return parse_tarifa_iva(getattr(config, "sri_iva_default", None), default=15.0)


# Códigos SRI que deben permanecer en 0% aunque haya default de facturación.
_SRI_ZERO_CODIGOS = {"6", "7"}  # No objeto de impuesto / Exento IVA


def _is_transport_product(product) -> bool:
    if product is None:
        return False
    code = (getattr(product, "code", None) or "").strip().upper()
    name = (getattr(product, "name", None) or "").strip().lower()
    return code == "SRV-TRANSPORTE" or name == "servicio de transporte"


def is_shipping_item(item) -> bool:
    """True si la línea es el servicio de transporte / costo de envío."""
    if item is None:
        return False
    if isinstance(item, dict):
        if item.get("is_transport"):
            return True
        detail = (item.get("detail") or "").strip().lower()
        return detail == "servicio de transporte"
    if _is_transport_product(getattr(item, "product", None)):
        return True
    return (getattr(item, "detail", None) or "").strip().lower() == "servicio de transporte"


def resolve_product_tarifa_iva(product, default_tarifa_iva: float) -> float:
    """Tarifa IVA del producto; 0% no se sustituye por el default."""
    if product is None:
        return float(default_tarifa_iva)
    tarifa = getattr(product, "tarifa_iva", None)
    if tarifa is None or tarifa == "":
        return float(default_tarifa_iva)
    return float(tarifa)


def resolve_product_codigo_iva(product, tarifa_iva: float) -> str:
    codigo = getattr(product, "codigo_iva", None) if product else None
    if codigo is not None and str(codigo).strip() != "":
        return str(codigo).strip()
    return codigo_iva_from_tarifa(tarifa_iva)


def resolve_quotation_billing_iva(product, sri_default_tarifa: float) -> tuple[float, str]:
    """
    IVA para líneas de factura SRI creadas desde cotización.

    Las cotizaciones pueden ir al 0% comercial; al facturar se aplica
    ``sri_iva_default`` automáticamente. Excepciones: transporte y
    productos marcados como no objeto / exento.
    """
    sri_default = float(sri_default_tarifa if sri_default_tarifa is not None else 15.0)
    if _is_transport_product(product):
        return 0.0, "0"

    codigo_raw = ""
    if product is not None:
        codigo_raw = str(getattr(product, "codigo_iva", None) or "").strip()
    if codigo_raw in _SRI_ZERO_CODIGOS:
        return 0.0, codigo_raw

    catalog_tarifa = None
    if product is not None:
        raw = getattr(product, "tarifa_iva", None)
        if raw is not None and raw != "":
            catalog_tarifa = float(raw)

    # Producto ya configurado con tarifa gravada (>0) → respetar catálogo
    if catalog_tarifa is not None and catalog_tarifa > 0:
        return catalog_tarifa, resolve_product_codigo_iva(product, catalog_tarifa)

    # 0% / sin configurar / heredado de cotización → IVA SRI vigente
    return sri_default, codigo_iva_from_tarifa(sri_default)


def compute_line(
    cantidad,
    precio_unitario,
    descuento=0,
    tarifa_iva=None,
    codigo_iva=None,
):
    cantidad = float(cantidad or 0)
    precio_unitario = float(precio_unitario or 0)
    descuento = float(descuento or 0)
    tarifa = parse_tarifa_iva(tarifa_iva, default=0.0)
    codigo = codigo_iva_from_tarifa(tarifa, codigo_iva)

    precio_total_sin_impuesto = round2(cantidad * precio_unitario - descuento)
    valor_iva = round2(precio_total_sin_impuesto * tarifa / 100)

    return {
        "precio_total_sin_impuesto": precio_total_sin_impuesto,
        "tarifa_iva": tarifa,
        "codigo_iva": codigo,
        "valor_iva": valor_iva,
    }


def compute_invoice_totals(lines, descuento_global=0, propina=0):
    subtotal_sin_impuestos = round2(sum(float(l["precio_total_sin_impuesto"]) for l in lines))
    subtotal_iva = round2(sum(float(l["valor_iva"]) for l in lines))
    descuento_global = round2(descuento_global)
    propina = round2(propina)
    importe_total = round2(subtotal_sin_impuestos + subtotal_iva - descuento_global + propina)
    return {
        "subtotal_sin_impuestos": subtotal_sin_impuestos,
        "subtotal_iva": subtotal_iva,
        "descuento": descuento_global,
        "propina": propina,
        "importe_total": importe_total,
    }


def quotation_item_to_line(
    item,
    global_discount_pct=0,
    default_tarifa_iva=0,
    *,
    apply_sri_billing_iva: bool = False,
):
    """Convierte un QuotationItem a línea fiscal SRI.

    Con ``apply_sri_billing_iva=True`` (facturar desde cotización) usa el IVA
    SRI configurado aunque el producto/cotización estén en 0% comercial.
    """
    from app.services.quotation_service import compute_item_total

    item_discount = float(getattr(item, "item_discount", 0) or 0)
    gross_total = compute_item_total(item.quantity, item.unit_price, item_discount)
    global_discount_pct = float(global_discount_pct or 0)
    line_subtotal = round2(gross_total * (1 - global_discount_pct / 100))

    quantity = float(item.quantity or 1)
    descuento_abs = round2(quantity * float(item.unit_price or 0) - line_subtotal)
    if descuento_abs < 0:
        descuento_abs = 0

    product = getattr(item, "product", None)
    if apply_sri_billing_iva:
        tarifa_iva, codigo_iva = resolve_quotation_billing_iva(product, default_tarifa_iva)
    else:
        tarifa_iva = resolve_product_tarifa_iva(product, default_tarifa_iva)
        codigo_iva = resolve_product_codigo_iva(product, tarifa_iva)
    codigo_principal = (
        (getattr(product, "code", None) or "").strip()
        or f"COT-{item.id}"
    )
    codigo_auxiliar = getattr(product, "codigo_auxiliar", None)
    descripcion = (
        getattr(item, "detail", None)
        or (getattr(product, "name", None) if product else None)
        or f"Ítem {item.id}"
    )

    calc = compute_line(
        quantity,
        float(item.unit_price or 0),
        descuento_abs,
        tarifa_iva,
        codigo_iva,
    )

    return {
        "product_id": getattr(product, "id", None),
        "quotation_item_id": item.id,
        "codigo_principal": codigo_principal[:50],
        "codigo_auxiliar": (codigo_auxiliar or "")[:50] or None,
        "descripcion": str(descripcion)[:500],
        "cantidad": quantity,
        "precio_unitario": float(item.unit_price or 0),
        "descuento": descuento_abs,
        **calc,
    }


def shipping_line(shipping_cost, default_tarifa_iva=0):
    shipping_cost = float(shipping_cost or 0)
    if shipping_cost <= 0:
        return None
    calc = compute_line(1, shipping_cost, 0, default_tarifa_iva)
    return {
        "product_id": None,
        "quotation_item_id": None,
        "codigo_principal": "ENVIO",
        "codigo_auxiliar": None,
        "descripcion": "Costo de envío",
        "cantidad": 1,
        "precio_unitario": shipping_cost,
        "descuento": 0,
        **calc,
    }
