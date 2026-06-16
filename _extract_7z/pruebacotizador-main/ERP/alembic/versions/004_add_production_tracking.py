"""Tabla production_tracking

Revision ID: 004_tracking
Revises: 003_payments
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_tracking"
down_revision: Union[str, None] = "003_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_tracking",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_item_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["quotation_item_id"], ["quotation_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quotation_item_id"),
    )
    op.create_index(
        "ix_production_tracking_quotation_item_id",
        "production_tracking",
        ["quotation_item_id"],
        unique=True,
    )
    op.create_index(
        "ix_production_tracking_status",
        "production_tracking",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_production_tracking_status", table_name="production_tracking")
    op.drop_index(
        "ix_production_tracking_quotation_item_id",
        table_name="production_tracking",
    )
    op.drop_table("production_tracking")
