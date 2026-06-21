"""Descuento por ítem en cotización."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_item_discount"
down_revision: Union[str, None] = "013_company_icon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quotation_items",
        sa.Column("item_discount", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("quotation_items", "item_discount")
