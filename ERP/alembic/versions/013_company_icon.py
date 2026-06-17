"""Add company_icon column for sidebar/favicon separate from PDF logo."""

from alembic import op
import sqlalchemy as sa


revision = "013_company_icon"
down_revision = "012_quotation_item_logo_type"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company_config",
        sa.Column("company_icon", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("company_config", "company_icon")
