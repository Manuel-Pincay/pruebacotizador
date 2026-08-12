"""IVA SRI automático al facturar desde cotización (sin cambiar cotizador)."""

from types import SimpleNamespace

from app.services.tax_service import (
    quotation_item_to_line,
    resolve_quotation_billing_iva,
)


def test_billing_iva_upgrades_zero_product_to_sri_default():
    product = SimpleNamespace(code="P1", name="Letrero", tarifa_iva=0, codigo_iva="0")
    tarifa, codigo = resolve_quotation_billing_iva(product, 15)
    assert tarifa == 15
    assert codigo == "4"


def test_billing_iva_keeps_transport_at_zero():
    product = SimpleNamespace(
        code="SRV-TRANSPORTE",
        name="Servicio de transporte",
        tarifa_iva=0,
        codigo_iva="0",
    )
    tarifa, codigo = resolve_quotation_billing_iva(product, 15)
    assert tarifa == 0
    assert codigo == "0"


def test_billing_iva_respects_catalog_15():
    product = SimpleNamespace(code="P2", name="Item", tarifa_iva=15, codigo_iva="4")
    tarifa, codigo = resolve_quotation_billing_iva(product, 15)
    assert tarifa == 15
    assert codigo == "4"


def test_quotation_item_to_line_applies_sri_flag():
    item = SimpleNamespace(
        id=9,
        quantity=2,
        unit_price=10,
        item_discount=0,
        detail="Letrero",
        product=SimpleNamespace(id=1, code="L1", name="Letrero", tarifa_iva=0, codigo_iva="0", codigo_auxiliar=None),
    )
    line = quotation_item_to_line(item, 0, 15, apply_sri_billing_iva=True)
    assert line["tarifa_iva"] == 15
    assert line["codigo_iva"] == "4"
    assert line["valor_iva"] == 3.0  # 20 * 0.15


def test_quotation_item_without_sri_flag_keeps_zero():
    item = SimpleNamespace(
        id=9,
        quantity=2,
        unit_price=10,
        item_discount=0,
        detail="Letrero",
        product=SimpleNamespace(id=1, code="L1", name="Letrero", tarifa_iva=0, codigo_iva="0", codigo_auxiliar=None),
    )
    line = quotation_item_to_line(item, 0, 0, apply_sri_billing_iva=False)
    assert line["tarifa_iva"] == 0
    assert line["valor_iva"] == 0
