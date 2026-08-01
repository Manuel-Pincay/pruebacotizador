from datetime import datetime, timedelta, timezone

# Ecuador no usa horario de verano; UTC-5 fijo (sin depender de tzdata en Windows).
ECUADOR_TZ = timezone(timedelta(hours=-5))


def now_ecuador() -> datetime:
    """Fecha/hora local Ecuador — como `new Date()` en FactuSRI."""
    return datetime.now(ECUADOR_TZ).replace(tzinfo=None)
