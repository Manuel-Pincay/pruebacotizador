"""Índices de rendimiento MySQL

Revision ID: 002_indexes
Revises: 001_initial
Create Date: 2026-06-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_indexes"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_clients_name", "clients", ["name"], unique=False)
    op.create_index("ix_products_code", "products", ["code"], unique=False)
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_quotations_client_id", "quotations", ["client_id"], unique=False)
    op.create_index("ix_quotations_status", "quotations", ["status"], unique=False)
    op.create_index(
        "ix_quotation_items_quotation_id",
        "quotation_items",
        ["quotation_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_orders_status",
        "production_orders",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_production_orders_quotation_id",
        "production_orders",
        ["quotation_id"],
        unique=False,
    )
    op.create_index(
        "ix_shipments_quotation_id",
        "shipments",
        ["quotation_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_product_id",
        "inventory_movements",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_product_id", table_name="inventory_movements")
    op.drop_index("ix_shipments_quotation_id", table_name="shipments")
    op.drop_index("ix_production_orders_quotation_id", table_name="production_orders")
    op.drop_index("ix_production_orders_status", table_name="production_orders")
    op.drop_index("ix_quotation_items_quotation_id", table_name="quotation_items")
    op.drop_index("ix_quotations_status", table_name="quotations")
    op.drop_index("ix_quotations_client_id", table_name="quotations")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_code", table_name="products")
    op.drop_index("ix_clients_name", table_name="clients")
