"""Preparación de esquema MySQL (Alembic)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parent.parent
    return Config(str(root / "alembic.ini"))


def run_alembic_upgrade() -> str:
    """Aplica migraciones pendientes hasta head. Devuelve la revisión actual."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    return head or "head"


def prepare_database() -> None:
    """Crea o actualiza el esquema MySQL desde cero con Alembic."""
    print("  → Aplicando migraciones Alembic (automático)...")
    head = run_alembic_upgrade()
    print(f"  ✓ Esquema al día (revisión: {head})")
