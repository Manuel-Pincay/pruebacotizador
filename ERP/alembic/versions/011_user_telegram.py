"""Telegram chat ID y preferencia de notificación en usuarios.

Revision ID: 011_user_telegram
Revises: 010_events_notifications
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "011_user_telegram"
down_revision: Union[str, None] = "010_events_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_notify",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_notify")
    op.drop_column("users", "telegram_chat_id")
