"""Constantes SRI compartidas (formas de pago, tipos de identificación)."""

FORMAS_PAGO = [
    {"codigo": "01", "label": "Sin utilización del sistema financiero (Efectivo)"},
    {"codigo": "15", "label": "Compensación de deudas"},
    {"codigo": "16", "label": "Tarjeta de débito"},
    {"codigo": "17", "label": "Dinero electrónico"},
    {"codigo": "18", "label": "Tarjeta prepago"},
    {"codigo": "19", "label": "Tarjeta de crédito"},
    {"codigo": "20", "label": "Otros con utilización del sistema financiero"},
    {"codigo": "21", "label": "Endoso de títulos"},
]

TIPOS_IDENTIFICACION = [
    {"value": "RUC", "label": "RUC"},
    {"value": "CEDULA", "label": "Cédula"},
    {"value": "PASAPORTE", "label": "Pasaporte"},
    {"value": "CONSUMIDOR_FINAL", "label": "Consumidor final"},
    {"value": "IDENTIFICACION_EXTERIOR", "label": "Identificación del exterior"},
]

CONSUMIDOR_FINAL = "9999999999999"

# Tabla SRI codigoPorcentaje (IVA) según tarifa
TARIFA_IVA_TO_CODIGO = {
    0: "0",
    5: "5",
    12: "2",
    13: "10",
    14: "3",
    15: "4",
}

# Opciones para catálogo de productos (facturación SRI)
TARIFAS_IVA_PRODUCTO = [
    {"tarifa": 0, "codigo": "0", "label": "0% — Sin IVA"},
    {"tarifa": 5, "codigo": "5", "label": "5%"},
    {"tarifa": 12, "codigo": "2", "label": "12%"},
    {"tarifa": 13, "codigo": "10", "label": "13%"},
    {"tarifa": 14, "codigo": "3", "label": "14%"},
    {"tarifa": 15, "codigo": "4", "label": "15% — Tarifa vigente"},
]


def codigo_iva_from_tarifa(tarifa_iva, codigo_iva=None) -> str:
    if codigo_iva:
        return str(codigo_iva)
    tarifa = round(float(tarifa_iva or 0), 2)
    for t, code in TARIFA_IVA_TO_CODIGO.items():
        if abs(tarifa - t) < 0.001:
            return code
    return "4" if tarifa > 0 else "0"


def inferir_tipo_identificacion(identificacion: str) -> str:
    identificacion = (identificacion or "").strip()
    if identificacion == CONSUMIDOR_FINAL:
        return "CONSUMIDOR_FINAL"
    if len(identificacion) == 13 and identificacion.isdigit():
        return "RUC"
    if len(identificacion) == 10 and identificacion.isdigit():
        return "CEDULA"
    if identificacion and identificacion.replace("-", "").isalnum():
        return "PASAPORTE"
    return "IDENTIFICACION_EXTERIOR"


def label_forma_pago(codigo: str) -> str:
    for item in FORMAS_PAGO:
        if item["codigo"] == codigo:
            return item["label"]
    return codigo


MOTIVOS_NOTA_CREDITO = [
    "ANULACIÓN DE FACTURA",
    "DEVOLUCIÓN DE MERCADERÍA",
    "DESCUENTO COMERCIAL",
    "ERROR EN FACTURACIÓN",
]
