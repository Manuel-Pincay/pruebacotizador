"""Código de verificación de email del portal tienda.

Revision ID: 018_portal_email_verify
Revises: 017_store_home_cms
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "018_portal_email_verify"
down_revision: Union[str, None] = "017_store_home_cms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("portal_verify_code", sa.String(10), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column("portal_verify_expires", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "portal_verify_expires")
    op.drop_column("clients", "portal_verify_code")
