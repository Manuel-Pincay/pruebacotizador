def escape_xml(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_decimal(value, decimals=2) -> str:
    return f"{float(value):.{decimals}f}"


def format_date_sri(dt) -> str:
    return dt.strftime("%d/%m/%Y")


def format_cantidad(value) -> str:
    formatted = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def format_precio_unitario(value) -> str:
    formatted = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def format_entero_o_decimal(value) -> str:
    n = float(value)
    if n == int(n):
        return str(int(n))
    return f"{n:.2f}"


def format_tarifa(value) -> str:
    return f"{float(value):.1f}"
