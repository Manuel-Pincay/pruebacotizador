"""Ampliar design_file_name para varios archivos por orden.

Revision ID: 021_design_file_names_text
Revises: 020_shipment_one_per_quotation
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "021_design_file_names_text"
down_revision: Union[str, None] = "020_shipment_one_per_quotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.alter_column(
            "design_file_name",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.alter_column(
            "design_file_name",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
