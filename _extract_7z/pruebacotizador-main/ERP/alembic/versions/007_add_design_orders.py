"""Órdenes de diseño internas para producción

Revision ID: 007_design_orders
Revises: 006_design
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_design_orders"
down_revision: Union[str, None] = "006_design"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "design_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_item_id", sa.Integer(), nullable=False),
        sa.Column("designer_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("material", sa.String(length=50), nullable=False),
        sa.Column("size", sa.String(length=100), nullable=False),
        sa.Column("usb_reference", sa.String(length=100), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("copies", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["designer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["quotation_item_id"], ["quotation_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_design_orders_quotation_item_id",
        "design_orders",
        ["quotation_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_design_orders_quotation_item_id", table_name="design_orders")
    op.drop_table("design_orders")
