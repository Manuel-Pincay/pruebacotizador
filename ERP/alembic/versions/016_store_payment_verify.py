"""Verificación de abonos tienda + instrucciones de transferencia + token de pedido.

Revision ID: 016_store_payment_verify
Revises: 015_store_foundation
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "016_store_payment_verify"
down_revision: Union[str, None] = "015_store_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quotation_payments",
        sa.Column(
            "verification_status",
            sa.String(20),
            nullable=False,
            server_default="confirmed",
        ),
    )
    op.add_column(
        "quotation_payments",
        sa.Column("verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "quotation_payments",
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_quotation_payments_verified_by",
        "quotation_payments",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "quotations",
        sa.Column("store_access_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_quotations_store_access_token",
        "quotations",
        ["store_access_token"],
        unique=True,
    )
    op.add_column(
        "company_config",
        sa.Column("store_payment_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_config", "store_payment_instructions")
    op.drop_index("ix_quotations_store_access_token", table_name="quotations")
    op.drop_column("quotations", "store_access_token")
    op.drop_constraint(
        "fk_quotation_payments_verified_by",
        "quotation_payments",
        type_="foreignkey",
    )
    op.drop_column("quotation_payments", "verified_by_user_id")
    op.drop_column("quotation_payments", "verified_at")
    op.drop_column("quotation_payments", "verification_status")
