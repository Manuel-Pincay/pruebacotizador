"""Origen de cumplimiento por ítem de diseño (inventario vs producción).

Revision ID: 019_design_item_fulfillment
Revises: 018_portal_email_verify
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "019_design_item_fulfillment"
down_revision: Union[str, None] = "018_portal_email_verify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quotation_items",
        sa.Column(
            "fulfill_from_inventory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "quotation_items",
        sa.Column(
            "design_item_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("quotation_items", "design_item_done")
    op.drop_column("quotation_items", "fulfill_from_inventory")
