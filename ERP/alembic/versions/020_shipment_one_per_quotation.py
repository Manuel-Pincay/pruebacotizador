"""Una guía por cotización + client_id para guías sin cotización.

Revision ID: 020_shipment_one_per_quotation
Revises: 019_design_item_fulfillment
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "020_shipment_one_per_quotation"
down_revision: Union[str, None] = "019_design_item_fulfillment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Mantener solo la guía más reciente por cotización
    dup_ids = conn.execute(
        sa.text(
            """
            SELECT s.id
            FROM shipments s
            WHERE s.quotation_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM shipments s2
                WHERE s2.quotation_id = s.quotation_id
                  AND s2.id > s.id
              )
            """
        )
    ).fetchall()
    for (sid,) in dup_ids:
        conn.execute(sa.text("DELETE FROM shipments WHERE id = :id"), {"id": sid})

    with op.batch_alter_table("shipments") as batch:
        batch.add_column(sa.Column("client_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_shipments_client_id_clients",
            "clients",
            ["client_id"],
            ["id"],
        )
        batch.create_index(
            "ix_shipments_quotation_id_unique",
            ["quotation_id"],
            unique=True,
        )
        batch.create_index("ix_shipments_client_id", ["client_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("shipments") as batch:
        batch.drop_index("ix_shipments_client_id")
        batch.drop_index("ix_shipments_quotation_id_unique")
        batch.drop_constraint("fk_shipments_client_id_clients", type_="foreignkey")
        batch.drop_column("client_id")
