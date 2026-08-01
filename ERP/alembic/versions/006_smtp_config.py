"""Correo SMTP en company_config (editable desde el ERP).

Revision ID: 006_smtp_config
Revises: 005_invoice_email
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "006_smtp_config"
down_revision: Union[str, None] = "005_invoice_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company_config", sa.Column("smtp_enabled", sa.Boolean(), server_default="0"))
    op.add_column("company_config", sa.Column("smtp_host", sa.String(255), nullable=True))
    op.add_column("company_config", sa.Column("smtp_port", sa.Integer(), server_default="587"))
    op.add_column("company_config", sa.Column("smtp_user", sa.String(255), nullable=True))
    op.add_column("company_config", sa.Column("smtp_password_encrypted", sa.String(512), nullable=True))
    op.add_column("company_config", sa.Column("smtp_from", sa.String(255), nullable=True))
    op.add_column("company_config", sa.Column("smtp_use_tls", sa.Boolean(), server_default="1"))


def downgrade() -> None:
    op.drop_column("company_config", "smtp_use_tls")
    op.drop_column("company_config", "smtp_from")
    op.drop_column("company_config", "smtp_password_encrypted")
    op.drop_column("company_config", "smtp_user")
    op.drop_column("company_config", "smtp_port")
    op.drop_column("company_config", "smtp_host")
    op.drop_column("company_config", "smtp_enabled")
