"""Campos para tienda virtual y origen de cotizaciones.

Revision ID: 015_store_foundation
Revises: 014_design_size_usb
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "015_store_foundation"
down_revision: Union[str, None] = "014_design_size_usb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "store_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "quotations",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="erp",
        ),
    )
    op.add_column(
        "quotations",
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "quotations",
        sa.Column("created_by_client_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_quotations_created_by_user",
        "quotations",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_quotations_created_by_client",
        "quotations",
        "clients",
        ["created_by_client_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "clients",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column(
            "portal_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("clients", "portal_active")
    op.drop_column("clients", "password_hash")
    op.drop_constraint("fk_quotations_created_by_client", "quotations", type_="foreignkey")
    op.drop_constraint("fk_quotations_created_by_user", "quotations", type_="foreignkey")
    op.drop_column("quotations", "created_by_client_id")
    op.drop_column("quotations", "created_by_user_id")
    op.drop_column("quotations", "source")
    op.drop_column("products", "store_visible")
