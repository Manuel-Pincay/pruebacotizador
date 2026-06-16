"""Guías de envío: cédula destinatario y remitente configurable."""

from alembic import op
import sqlalchemy as sa

revision = "010_shipment_guide_config"
down_revision = "009_unified_production_order"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shipments", sa.Column("customer_id_number", sa.String(), nullable=True))
    op.add_column("company_config", sa.Column("guide_sender_name", sa.String(), nullable=True))
    op.add_column("company_config", sa.Column("guide_sender_city", sa.String(), server_default="Manta"))
    op.add_column("company_config", sa.Column("guide_sender_region", sa.String(), server_default="Ecuador"))
    op.add_column("company_config", sa.Column("guide_sender_phone", sa.String(), nullable=True))
    op.add_column("company_config", sa.Column("guide_sender_address", sa.String(), nullable=True))


def downgrade():
    op.drop_column("company_config", "guide_sender_address")
    op.drop_column("company_config", "guide_sender_phone")
    op.drop_column("company_config", "guide_sender_region")
    op.drop_column("company_config", "guide_sender_city")
    op.drop_column("company_config", "guide_sender_name")
    op.drop_column("shipments", "customer_id_number")
