import random
from datetime import datetime


TIPO_COMPROBANTE_CODE = {
    "FACTURA": "01",
    "NOTA_CREDITO": "04",
    "NOTA_DEBITO": "05",
    "GUIA_REMISION": "06",
    "RETENCION": "07",
}

TIPO_IDENTIFICACION_SRI = {
    "RUC": "04",
    "CEDULA": "05",
    "PASAPORTE": "06",
    "CONSUMIDOR_FINAL": "07",
    "IDENTIFICACION_EXTERIOR": "08",
}


def digito_verificador(clave48: str) -> int:
    factor = 2
    suma = 0
    for digit in reversed(clave48):
        suma += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    mod = 11 - (suma % 11)
    if mod == 11:
        return 0
    if mod == 10:
        return 1
    return mod


def generar_clave_acceso(
    fecha_emision: datetime,
    tipo_comprobante: str,
    ruc: str,
    ambiente: str,
    codigo_establecimiento: str,
    codigo_punto_emision: str,
    secuencial: str,
    tipo_emision: str = "NORMAL",
) -> str:
    dd = f"{fecha_emision.day:02d}"
    mm = f"{fecha_emision.month:02d}"
    yyyy = f"{fecha_emision.year:04d}"
    fecha = f"{dd}{mm}{yyyy}"

    tipo_doc = TIPO_COMPROBANTE_CODE.get(tipo_comprobante, "01")
    amb = "2" if ambiente == "PRODUCCION" else "1"
    serie = f"{codigo_establecimiento}{codigo_punto_emision}"
    sec = secuencial.zfill(9)
    codigo_numerico = f"{random.randint(0, 99999999):08d}"
    emision = "2" if tipo_emision == "CONTINGENCIA" else "1"

    clave48 = f"{fecha}{tipo_doc}{ruc}{amb}{serie}{sec}{codigo_numerico}{emision}"
    verificador = digito_verificador(clave48)
    return f"{clave48}{verificador}"


def tipo_identificacion_sri(tipo: str) -> str:
    return TIPO_IDENTIFICACION_SRI.get(tipo or "", "07")


def ambiente_desde_clave(clave: str | None) -> str | None:
    """Dígito 24 de la clave: 1 = PRUEBAS, 2 = PRODUCCIÓN."""
    if not clave or len(clave) < 24:
        return None
    d = clave[23]
    if d == "2":
        return "PRODUCCION"
    if d == "1":
        return "PRUEBAS"
    return None
