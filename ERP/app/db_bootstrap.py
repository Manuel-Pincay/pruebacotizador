"""Preparación de esquema MySQL (Alembic)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_alembic_upgrade() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    command.upgrade(cfg, "head")


def prepare_database() -> None:
    """Crea o actualiza el esquema MySQL desde cero con Alembic."""
    run_alembic_upgrade()
