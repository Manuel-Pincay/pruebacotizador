"""Materia prima de fabricación y vínculo con órdenes de producción.

Revision ID: 008_raw_materials
Revises: 007_credit_notes
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "008_raw_materials"
down_revision: Union[str, None] = "007_credit_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="plancha"),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("size", sa.String(80), nullable=True),
        sa.Column("thickness", sa.String(40), nullable=True),
        sa.Column("color", sa.String(60), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="planchas"),
        sa.Column("stock", sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(300), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_raw_materials_kind", "raw_materials", ["kind"])
    op.create_index("ix_raw_materials_material_type", "raw_materials", ["material_type"])

    op.create_table(
        "raw_material_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_material_id", sa.Integer(), sa.ForeignKey("raw_materials.id"), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("previous_stock", sa.Float(), nullable=False),
        sa.Column("new_stock", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("production_order_id", sa.Integer(), sa.ForeignKey("production_orders.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_raw_material_movements_raw_material_id", "raw_material_movements", ["raw_material_id"])

    op.add_column(
        "production_orders",
        sa.Column("use_fabrication_materials", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "production_orders",
        sa.Column("raw_material_id", sa.Integer(), sa.ForeignKey("raw_materials.id"), nullable=True),
    )
    op.add_column("production_orders", sa.Column("raw_material_qty", sa.Float(), nullable=True))

    # Semillas básicas (stock 0; el usuario reabastece)
    conn = op.get_bind()
    seeds = [
        ("plancha", "MDF", "Plancha MDF 2.44x1.22", "2.44x1.22 m", "3mm", None, "planchas", 0, 5),
        ("plancha", "MDF", "Plancha MDF 2.44x1.22", "2.44x1.22 m", "5.5mm", None, "planchas", 0, 5),
        ("plancha", "Acrílico", "Plancha Acrílico transparente", "1.22x2.44 m", "3mm", "Transparente", "planchas", 0, 3),
        ("vinil", "Vinil", "Vinil para impresión", None, None, None, "metros", 0, 20),
        ("vinil", "Vinil", "Vinil de color", None, None, "Negro", "metros", 0, 10),
        ("vinil", "Vinil", "Vinil de color", None, None, "Blanco", "metros", 0, 10),
        ("vinil", "Vinil", "Vinil de color", None, None, "Rojo", "metros", 0, 5),
        ("vinil", "Vinil", "Vinil de color", None, None, "Azul", "metros", 0, 5),
    ]
    for kind, material_type, name, size, thickness, color, unit, stock, min_stock in seeds:
        conn.execute(
            sa.text(
                """
                INSERT INTO raw_materials
                (kind, material_type, name, size, thickness, color, unit, stock, min_stock, active, created_at, updated_at)
                VALUES
                (:kind, :material_type, :name, :size, :thickness, :color, :unit, :stock, :min_stock, 1, NOW(), NOW())
                """
            ),
            {
                "kind": kind,
                "material_type": material_type,
                "name": name,
                "size": size,
                "thickness": thickness,
                "color": color,
                "unit": unit,
                "stock": stock,
                "min_stock": min_stock,
            },
        )


def downgrade() -> None:
    op.drop_column("production_orders", "raw_material_qty")
    op.drop_column("production_orders", "raw_material_id")
    op.drop_column("production_orders", "use_fabrication_materials")
    op.drop_index("ix_raw_material_movements_raw_material_id", table_name="raw_material_movements")
    op.drop_table("raw_material_movements")
    op.drop_index("ix_raw_materials_material_type", table_name="raw_materials")
    op.drop_index("ix_raw_materials_kind", table_name="raw_materials")
    op.drop_table("raw_materials")
