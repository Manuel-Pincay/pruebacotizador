"""Diseños múltiples y tracking por cotización

Revision ID: 005_designs
Revises: 004_tracking
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_designs"
down_revision: Union[str, None] = "004_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quotation_designs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quotation_designs_quotation_id",
        "quotation_designs",
        ["quotation_id"],
        unique=False,
    )

    with op.batch_alter_table("production_tracking") as batch_op:
        batch_op.add_column(sa.Column("quotation_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_production_tracking_quotation_id",
            "quotations",
            ["quotation_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_production_tracking_quotation_id",
            ["quotation_id"],
        )
        batch_op.alter_column("quotation_item_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("production_tracking") as batch_op:
        batch_op.drop_constraint("uq_production_tracking_quotation_id", type_="unique")
        batch_op.drop_constraint("fk_production_tracking_quotation_id", type_="foreignkey")
        batch_op.drop_column("quotation_id")
        batch_op.alter_column("quotation_item_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_quotation_designs_quotation_id", table_name="quotation_designs")
    op.drop_table("quotation_designs")
