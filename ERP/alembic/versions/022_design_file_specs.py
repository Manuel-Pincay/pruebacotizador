"""Especificaciones por archivo (material y medida) en órdenes de producción.

Revision ID: 022_design_file_specs
Revises: 021_design_file_names_text
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "022_design_file_specs"
down_revision: Union[str, None] = "021_design_file_names_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("design_file_specs", sa.Text(), nullable=True))
        batch_op.alter_column(
            "design_material",
            existing_type=sa.String(length=50),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.alter_column(
            "design_material",
            existing_type=sa.Text(),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.drop_column("design_file_specs")
