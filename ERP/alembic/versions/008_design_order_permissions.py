"""Campos created_by y assigned_to en design_orders

Revision ID: 008_design_order_perms
Revises: 007_design_orders
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_design_order_perms"
down_revision: Union[str, None] = "007_design_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("design_orders", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column("design_orders", sa.Column("assigned_to", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_design_orders_created_by",
        "design_orders",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_design_orders_assigned_to",
        "design_orders",
        "users",
        ["assigned_to"],
        ["id"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE design_orders SET created_by = designer_id, assigned_to = designer_id "
            "WHERE designer_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_design_orders_assigned_to", "design_orders", type_="foreignkey")
    op.drop_constraint("fk_design_orders_created_by", "design_orders", type_="foreignkey")
    op.drop_column("design_orders", "assigned_to")
    op.drop_column("design_orders", "created_by")
