"""Correos adicionales cliente y envío automático de facturas.

Revision ID: 005_invoice_email
Revises: 004_company_icon
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "005_invoice_email"
down_revision: Union[str, None] = "004_company_icon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("additional_emails_json", sa.Text(), nullable=True))
    op.add_column("company_config", sa.Column("billing_email_subject", sa.String(255), nullable=True))
    op.add_column("company_config", sa.Column("billing_email_body", sa.Text(), nullable=True))
    op.add_column("company_config", sa.Column("billing_auto_send_email", sa.Boolean(), server_default="1"))
    op.add_column("electronic_invoices", sa.Column("email_sent_at", sa.DateTime(), nullable=True))
    op.add_column("electronic_invoices", sa.Column("email_sent_to_json", sa.Text(), nullable=True))
    op.add_column("electronic_invoices", sa.Column("email_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("electronic_invoices", "email_last_error")
    op.drop_column("electronic_invoices", "email_sent_to_json")
    op.drop_column("electronic_invoices", "email_sent_at")
    op.drop_column("company_config", "billing_auto_send_email")
    op.drop_column("company_config", "billing_email_body")
    op.drop_column("company_config", "billing_email_subject")
    op.drop_column("clients", "additional_emails_json")
