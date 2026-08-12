"""IVA SRI por defecto (independiente del IVA comercial de cotizaciones).

Revision ID: 012_sri_iva_default
Revises: 011_user_telegram
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "012_sri_iva_default"
down_revision: Union[str, None] = "011_user_telegram"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "sri_iva_default",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )


def downgrade() -> None:
    op.drop_column("company_config", "sri_iva_default")
