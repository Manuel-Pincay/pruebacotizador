"""Varias materias primas por orden de producción.

Revision ID: 023_fabrication_raw_materials
Revises: 022_design_file_specs
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "023_fabrication_raw_materials"
down_revision: Union[str, None] = "022_design_file_specs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("fabrication_raw_materials", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_column("fabrication_raw_materials")
