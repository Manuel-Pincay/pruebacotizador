"""Colores personalizables de etiquetas / guías de envío.

Revision ID: 009_guide_label_colors
Revises: 008_raw_materials
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "009_guide_label_colors"
down_revision: Union[str, None] = "008_raw_materials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column("guide_accent_color", sa.String(20), nullable=True, server_default="#d6452a"),
    )
    op.add_column(
        "company_config",
        sa.Column("guide_border_color", sa.String(20), nullable=True, server_default="#8a97a8"),
    )
    op.add_column(
        "company_config",
        sa.Column("guide_muted_color", sa.String(20), nullable=True, server_default="#6b7785"),
    )


def downgrade() -> None:
    op.drop_column("company_config", "guide_muted_color")
    op.drop_column("company_config", "guide_border_color")
    op.drop_column("company_config", "guide_accent_color")
