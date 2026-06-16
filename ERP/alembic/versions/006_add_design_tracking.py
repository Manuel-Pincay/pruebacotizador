"""Seguimiento de diseño por ítem personalizado

Revision ID: 006_design
Revises: 005_designs
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_design"
down_revision: Union[str, None] = "005_designs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "design_tracking",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_item_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["quotation_item_id"], ["quotation_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quotation_item_id"),
    )
    op.create_table(
        "design_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("design_tracking_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_name", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["design_tracking_id"], ["design_tracking.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("design_observations")
    op.drop_table("design_tracking")
