"""Columna company_icon — ya incluida en 001_initial (migración de compatibilidad)

Revision ID: 004_company_icon
Revises: 002_sri_billing
"""
from typing import Sequence, Union

from alembic import op


revision: str = "004_company_icon"
down_revision: Union[str, None] = "002_sri_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # company_icon ya está en 001_initial_schema para instalaciones nuevas.
    pass


def downgrade() -> None:
    pass
