"""Mejoras cotizaciones (ya aplicada en BD local)

Revision ID: 003_quotation_enhancements
Revises: 001_initial
Create Date: 2026-07-20

Esta revisión existe para alinear el historial Alembic con bases de datos
que ya tenían cambios de cotización aplicados manualmente o desde otra rama.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "003_quotation_enhancements"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cambios ya presentes en la base de datos local.
    pass


def downgrade() -> None:
    pass
