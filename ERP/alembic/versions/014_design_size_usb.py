"""Catálogos Medida (diseño) y USB.

Revision ID: 014_design_size_usb
Revises: 013_product_active
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "014_design_size_usb"
down_revision: Union[str, None] = "013_product_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_SIZES = ["120x90", "50x100", "10x10", "Retazo", "Plancha Completa", "A4", "A3"]
_DEFAULT_USBS = ["USB #1", "USB #2", "USB Azul", "USB Rojo", "USB Producción"]


def upgrade() -> None:
    op.create_table(
        "product_sizes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.create_table(
        "usb_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    sizes = sa.table("product_sizes", sa.column("name", sa.String))
    usbs = sa.table("usb_references", sa.column("name", sa.String))
    op.bulk_insert(sizes, [{"name": n} for n in _DEFAULT_SIZES])
    op.bulk_insert(usbs, [{"name": n} for n in _DEFAULT_USBS])


def downgrade() -> None:
    op.drop_table("usb_references")
    op.drop_table("product_sizes")
