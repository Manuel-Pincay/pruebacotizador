"""Cotización: tipo de logo por ítem (sin logo / grabado / impreso)."""

from alembic import op
import sqlalchemy as sa

revision = "012_quotation_item_logo_type"
down_revision = "011_shipping_item_image"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "quotation_items",
        sa.Column(
            "logo_type",
            sa.String(length=20),
            server_default="sin_logo",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE quotation_items SET logo_type = 'grabado' "
        "WHERE logo = 1 OR logo = TRUE"
    )


def downgrade():
    op.drop_column("quotation_items", "logo_type")
