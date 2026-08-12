"""Producto.active (archivo / soft-delete).

Revision ID: 013_product_active
Revises: 012_sri_iva_default
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "013_product_active"
down_revision: Union[str, None] = "012_sri_iva_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "active")
