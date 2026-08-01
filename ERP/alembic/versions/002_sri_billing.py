"""Integración facturación electrónica SRI

Revision ID: 002_sri_billing
Revises: 001_initial
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_sri_billing"
down_revision: Union[str, None] = "003_quotation_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company_config", sa.Column("sri_ruc", sa.String(13), nullable=True))
    op.add_column("company_config", sa.Column("sri_razon_social", sa.String(300), nullable=True))
    op.add_column("company_config", sa.Column("sri_nombre_comercial", sa.String(300), nullable=True))
    op.add_column("company_config", sa.Column("sri_direccion_matriz", sa.String(500), nullable=True))
    op.add_column("company_config", sa.Column("sri_obligado_contabilidad", sa.Boolean(), server_default="0", nullable=True))
    op.add_column("company_config", sa.Column("sri_contribuyente_especial", sa.String(20), nullable=True))
    op.add_column("company_config", sa.Column("sri_contribuyente_rimpe", sa.String(100), nullable=True))
    op.add_column("company_config", sa.Column("sri_ambiente", sa.String(20), server_default="PRUEBAS", nullable=True))
    op.add_column("company_config", sa.Column("sri_tipo_emision", sa.String(20), server_default="NORMAL", nullable=True))
    op.add_column("company_config", sa.Column("sri_email_notificacion", sa.String(255), nullable=True))
    op.add_column("company_config", sa.Column("sri_default_establishment", sa.String(3), nullable=True))
    op.add_column("company_config", sa.Column("sri_default_emission_point", sa.String(3), nullable=True))
    op.add_column("company_config", sa.Column("sri_active", sa.Boolean(), server_default="0", nullable=True))

    op.add_column("clients", sa.Column("tipo_identificacion", sa.String(30), server_default="CEDULA", nullable=True))

    op.add_column("products", sa.Column("codigo_auxiliar", sa.String(50), nullable=True))
    op.add_column("products", sa.Column("codigo_iva", sa.String(5), server_default="4", nullable=True))
    op.add_column("products", sa.Column("tarifa_iva", sa.Float(), server_default="15", nullable=True))

    op.create_table(
        "sri_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encrypted_p12", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_password", sa.String(512), nullable=False),
        sa.Column("subject_common_name", sa.String(255), nullable=True),
        sa.Column("issuer", sa.String(255), nullable=True),
        sa.Column("serial_number", sa.String(128), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sri_establishments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(3), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=True),
        sa.Column("direccion", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )

    op.create_table(
        "sri_emission_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("establishment_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["establishment_id"], ["sri_establishments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sri_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("emission_point_id", sa.Integer(), nullable=False),
        sa.Column("tipo_comprobante", sa.String(30), server_default="FACTURA", nullable=False),
        sa.Column("ultimo_numero", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["emission_point_id"], ["sri_emission_points.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "electronic_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("tipo_comprobante", sa.String(20), server_default="FACTURA", nullable=False),
        sa.Column("clave_acceso", sa.String(49), nullable=False),
        sa.Column("secuencial", sa.String(9), nullable=False),
        sa.Column("codigo_establecimiento", sa.String(3), nullable=False),
        sa.Column("codigo_punto_emision", sa.String(3), nullable=False),
        sa.Column("fecha_emision", sa.DateTime(), nullable=False),
        sa.Column("subtotal_sin_impuestos", sa.Float(), server_default="0", nullable=True),
        sa.Column("subtotal_iva", sa.Float(), server_default="0", nullable=True),
        sa.Column("descuento", sa.Float(), server_default="0", nullable=True),
        sa.Column("propina", sa.Float(), server_default="0", nullable=True),
        sa.Column("importe_total", sa.Float(), server_default="0", nullable=True),
        sa.Column("moneda", sa.String(10), server_default="DOLAR", nullable=True),
        sa.Column("pagos_json", sa.Text(), nullable=True),
        sa.Column("info_adicional_json", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(30), server_default="BORRADOR", nullable=False),
        sa.Column("xml_generado", sa.Text(), nullable=True),
        sa.Column("xml_firmado", sa.Text(), nullable=True),
        sa.Column("xml_autorizado", sa.Text(), nullable=True),
        sa.Column("numero_autorizacion", sa.String(64), nullable=True),
        sa.Column("fecha_autorizacion", sa.DateTime(), nullable=True),
        sa.Column("mensajes_sri_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clave_acceso"),
        sa.UniqueConstraint("quotation_id"),
    )

    op.create_table(
        "electronic_invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("quotation_item_id", sa.Integer(), nullable=True),
        sa.Column("codigo_principal", sa.String(50), nullable=False),
        sa.Column("codigo_auxiliar", sa.String(50), nullable=True),
        sa.Column("descripcion", sa.String(500), nullable=False),
        sa.Column("cantidad", sa.Float(), server_default="1", nullable=True),
        sa.Column("precio_unitario", sa.Float(), server_default="0", nullable=True),
        sa.Column("descuento", sa.Float(), server_default="0", nullable=True),
        sa.Column("precio_total_sin_impuesto", sa.Float(), server_default="0", nullable=True),
        sa.Column("codigo_iva", sa.String(5), server_default="4", nullable=True),
        sa.Column("tarifa_iva", sa.Float(), server_default="15", nullable=True),
        sa.Column("valor_iva", sa.Float(), server_default="0", nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["electronic_invoices.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["quotation_item_id"], ["quotation_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("electronic_invoice_lines")
    op.drop_table("electronic_invoices")
    op.drop_table("sri_sequences")
    op.drop_table("sri_emission_points")
    op.drop_table("sri_establishments")
    op.drop_table("sri_certificates")
    op.drop_column("products", "tarifa_iva")
    op.drop_column("products", "codigo_iva")
    op.drop_column("products", "codigo_auxiliar")
    op.drop_column("clients", "tipo_identificacion")
    op.drop_column("company_config", "sri_active")
    op.drop_column("company_config", "sri_default_emission_point")
    op.drop_column("company_config", "sri_default_establishment")
    op.drop_column("company_config", "sri_email_notificacion")
    op.drop_column("company_config", "sri_tipo_emision")
    op.drop_column("company_config", "sri_ambiente")
    op.drop_column("company_config", "sri_contribuyente_rimpe")
    op.drop_column("company_config", "sri_contribuyente_especial")
    op.drop_column("company_config", "sri_obligado_contabilidad")
    op.drop_column("company_config", "sri_direccion_matriz")
    op.drop_column("company_config", "sri_nombre_comercial")
    op.drop_column("company_config", "sri_razon_social")
    op.drop_column("company_config", "sri_ruc")
