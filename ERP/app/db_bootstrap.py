"""Preparación de esquema MySQL (Alembic + columnas legacy)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_alembic_upgrade() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    command.upgrade(cfg, "head")


def prepare_database() -> None:
    """Aplica migraciones Alembic y ajustes de esquema incrementales."""
    run_alembic_upgrade()

    from app.db_migrations import run_schema_migrations

    run_schema_migrations()
