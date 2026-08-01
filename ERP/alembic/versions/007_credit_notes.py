"""Notas de crédito y vínculo con factura modificada.

Revision ID: 007_credit_notes
Revises: 006_smtp_config
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "007_credit_notes"
down_revision: Union[str, None] = "006_smtp_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "electronic_invoices",
        sa.Column("invoice_modificado_id", sa.Integer(), sa.ForeignKey("electronic_invoices.id"), nullable=True),
    )
    op.add_column("electronic_invoices", sa.Column("motivo", sa.String(300), nullable=True))
    op.add_column("electronic_invoices", sa.Column("cod_doc_modificado", sa.String(2), nullable=True))
    op.add_column("electronic_invoices", sa.Column("num_doc_modificado", sa.String(20), nullable=True))
    op.add_column("electronic_invoices", sa.Column("fecha_emision_doc_sustento", sa.DateTime(), nullable=True))
    op.create_index("ix_electronic_invoices_modificado", "electronic_invoices", ["invoice_modificado_id"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO sri_sequences (emission_point_id, tipo_comprobante, ultimo_numero)
            SELECT ep.id, 'NOTA_CREDITO', 0 FROM sri_emission_points ep
            WHERE NOT EXISTS (
                SELECT 1 FROM sri_sequences s
                WHERE s.emission_point_id = ep.id AND s.tipo_comprobante = 'NOTA_CREDITO'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_electronic_invoices_modificado", table_name="electronic_invoices")
    op.drop_column("electronic_invoices", "fecha_emision_doc_sustento")
    op.drop_column("electronic_invoices", "num_doc_modificado")
    op.drop_column("electronic_invoices", "cod_doc_modificado")
    op.drop_column("electronic_invoices", "motivo")
    op.drop_column("electronic_invoices", "invoice_modificado_id")
