import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config.settings import settings  # noqa: E402
from app.database import Base  # noqa: E402
import app.models  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _ensure_alembic_version_table(connection) -> None:
    """MySQL: revision ids largos requieren version_num > VARCHAR(32)."""
    insp = inspect(connection)
    if not insp.has_table("alembic_version"):
        connection.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(128) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        return

    for col in insp.get_columns("alembic_version"):
        if col["name"] != "version_num":
            continue
        length = getattr(col["type"], "length", None)
        if length is not None and length < 128:
            connection.execute(
                text(
                    "ALTER TABLE alembic_version "
                    "MODIFY version_num VARCHAR(128) NOT NULL"
                )
            )
        break


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _ensure_alembic_version_table(connection)
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
