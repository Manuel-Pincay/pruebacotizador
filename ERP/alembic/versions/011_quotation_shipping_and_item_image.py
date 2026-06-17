"""Cotizaciones: costo de envío e imagen por ítem."""

from alembic import op
import sqlalchemy as sa

revision = "011_shipping_item_image"
down_revision = "010_shipment_guide_config"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "quotations",
        sa.Column("shipping_cost", sa.Float(), server_default="0", nullable=True),
    )
    op.add_column(
        "quotation_items",
        sa.Column("product_image", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("quotation_items", "product_image")
    op.drop_column("quotations", "shipping_cost")
