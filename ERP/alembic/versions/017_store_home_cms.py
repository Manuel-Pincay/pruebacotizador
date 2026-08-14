"""Carrusel y publicidad del home de la tienda.

Revision ID: 017_store_home_cms
Revises: 016_store_payment_verify
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "017_store_home_cms"
down_revision: Union[str, None] = "016_store_payment_verify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_slides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(400), nullable=True),
        sa.Column("cta_text", sa.String(80), nullable=True),
        sa.Column("cta_url", sa.String(255), nullable=True),
        sa.Column("image", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "store_home_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("show_top_bar", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("top_bar_left", sa.String(200), nullable=True),
        sa.Column("top_bar_right", sa.String(200), nullable=True),
        sa.Column("accent_color", sa.String(20), nullable=True),
        sa.Column("feature_1_title", sa.String(80), nullable=True),
        sa.Column("feature_1_text", sa.String(200), nullable=True),
        sa.Column("feature_2_title", sa.String(80), nullable=True),
        sa.Column("feature_2_text", sa.String(200), nullable=True),
        sa.Column("feature_3_title", sa.String(80), nullable=True),
        sa.Column("feature_3_text", sa.String(200), nullable=True),
        sa.Column("show_categories", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("featured_categories", sa.Text(), nullable=True),
        sa.Column("show_featured_products", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("featured_product_ids", sa.Text(), nullable=True),
        sa.Column("show_trust_bar", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("trust_1_title", sa.String(80), nullable=True),
        sa.Column("trust_1_text", sa.String(160), nullable=True),
        sa.Column("trust_2_title", sa.String(80), nullable=True),
        sa.Column("trust_2_text", sa.String(160), nullable=True),
        sa.Column("trust_3_title", sa.String(80), nullable=True),
        sa.Column("trust_3_text", sa.String(160), nullable=True),
        sa.Column("trust_4_title", sa.String(80), nullable=True),
        sa.Column("trust_4_text", sa.String(160), nullable=True),
        sa.Column("show_newsletter", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("newsletter_title", sa.String(160), nullable=True),
        sa.Column("footer_blurb", sa.Text(), nullable=True),
        sa.Column("contact_address", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(80), nullable=True),
        sa.Column("contact_email", sa.String(120), nullable=True),
        sa.Column("contact_hours", sa.String(120), nullable=True),
        sa.Column("contact_whatsapp", sa.String(40), nullable=True),
        sa.Column("social_instagram", sa.String(255), nullable=True),
        sa.Column("social_facebook", sa.String(255), nullable=True),
        sa.Column("social_tiktok", sa.String(255), nullable=True),
        sa.Column("nav_extra_links", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("store_home_settings")
    op.drop_table("store_slides")
