from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from app.config.settings import settings


def create_db_engine(database_url: str):

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle,
    )


DATABASE_URL = settings.database_url

engine = create_db_engine(DATABASE_URL)

# =====================================
# TEST CONNECTION
# =====================================

try:

    with engine.connect() as conn:

        conn.execute(text("SELECT 1"))

    print("\n✓ Base de datos conectada correctamente\n")

except OperationalError as e:

    print("\n" + "=" * 60)
    print("ERROR DE CONEXIÓN A MYSQL")
    print("=" * 60)

    print(f"""
DATABASE_URL:

{DATABASE_URL}

Verifique:

1. MySQL está iniciado
2. Usuario y contraseña son correctos
3. La base de datos existe
4. El puerto es correcto
""")

    print(f"\nDetalle:\n{e}\n")

    raise SystemExit(1)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()