"""Orden de producción unificada + historial

Revision ID: 009_unified_production_order
Revises: 008_design_order_perms
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_unified_production_order"
down_revision: Union[str, None] = "008_design_order_perms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DESIGN_COLUMNS = [
    ("design_file_name", sa.String(255)),
    ("design_material", sa.String(50)),
    ("design_size", sa.String(100)),
    ("design_usb_reference", sa.String(100)),
    ("design_notes", sa.Text()),
    ("design_copies", sa.Integer()),
    ("design_completed_at", sa.DateTime()),
    ("design_completed_by", sa.Integer()),
    ("assigned_to_user_id", sa.Integer()),
    ("updated_at", sa.DateTime()),
]

STATUS_MAP = {
    "pendiente": "pendiente_diseno",
    "diseño": "en_diseno",
    "diseno": "en_diseno",
    "produccion": "en_produccion",
    "empacado": "empaque",
    "enviado": "despachado",
    "entregado": "entregado",
}


def upgrade() -> None:
    for column, col_type in DESIGN_COLUMNS:
        op.add_column("production_orders", sa.Column(column, col_type, nullable=True))

    op.create_foreign_key(
        "fk_production_orders_design_completed_by",
        "production_orders",
        "users",
        ["design_completed_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_production_orders_assigned_to_user_id",
        "production_orders",
        "users",
        ["assigned_to_user_id"],
        ["id"],
    )

    op.create_table(
        "production_order_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_order_history_order_id",
        "production_order_history",
        ["production_order_id"],
    )

    conn = op.get_bind()
    for old, new in STATUS_MAP.items():
        conn.execute(
            sa.text("UPDATE production_orders SET status = :new WHERE lower(status) = :old"),
            {"old": old, "new": new},
        )

    conn.execute(
        sa.text(
            "INSERT INTO production_order_history (production_order_id, status, notes, created_at) "
            "SELECT id, status, 'Migración de estado', created_at FROM production_orders"
        )
    )

    if conn.dialect.name == "sqlite":
        conn.execute(sa.text("DROP TABLE IF EXISTS design_orders"))
    else:
        op.drop_index("ix_design_orders_quotation_item_id", table_name="design_orders")
        op.drop_table("design_orders")


def downgrade() -> None:
    op.drop_index("ix_production_order_history_order_id", table_name="production_order_history")
    op.drop_table("production_order_history")
    op.drop_constraint("fk_production_orders_assigned_to_user_id", "production_orders", type_="foreignkey")
    op.drop_constraint("fk_production_orders_design_completed_by", "production_orders", type_="foreignkey")
    for column, _ in reversed(DESIGN_COLUMNS):
        op.drop_column("production_orders", column)
