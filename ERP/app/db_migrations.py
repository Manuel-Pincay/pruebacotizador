from sqlalchemy import inspect, text

from app.database import engine

SCHEMA_ADDITIONS = {
    "production_orders": {
        "assigned_to": "VARCHAR(255)",
        "started_at": "DATETIME",
        "completed_at": "DATETIME",
        "notes": "VARCHAR(255)",
        "design_file_name": "VARCHAR(255)",
        "design_material": "VARCHAR(255)",
        "design_size": "VARCHAR(255)",
        "design_usb_reference": "VARCHAR(255)",
        "design_notes": "TEXT",
        "design_copies": "INTEGER",
        "design_completed_at": "DATETIME",
        "design_completed_by": "INTEGER",
        "assigned_to_user_id": "INTEGER",
        "updated_at": "DATETIME",
    },
    "production_tracking": {
        "quotation_id": "INTEGER",
    },
    "shipments": {
        "customer_id_number": "VARCHAR(255)",
    },
    "quotations": {
        "shipping_cost": "FLOAT DEFAULT 0",
    },
    "quotation_items": {
        "product_image": "VARCHAR(255)",
        "logo_type": "VARCHAR(20) DEFAULT 'sin_logo'",
    },
    "company_config": {
        "guide_sender_name": "VARCHAR(255)",
        "guide_sender_city": "VARCHAR(255) DEFAULT 'Manta'",
        "guide_sender_region": "VARCHAR(255) DEFAULT 'Ecuador'",
        "guide_sender_phone": "VARCHAR(255)",
        "guide_sender_address": "VARCHAR(255)",
        "company_icon": "VARCHAR(255)",
    },
}

PRODUCTION_STATUS_MAP = {
    "pendiente_diseno": "pendiente",
    "en_diseno": "diseno",
    "diseno_aprobado": "diseno",
    "pendiente_produccion": "produccion",
    "en_produccion": "produccion",
    "empaque": "produccion",
    "listo_despacho": "envio",
    "despachado": "envio",
    "diseño": "diseno",
    "produccion": "produccion",
    "enviado": "envio",
    "empacado": "produccion",
}


def _existing_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def run_schema_migrations():
    """Añade columnas faltantes sin alterar datos existentes."""
    inspector = inspect(engine)

    with engine.begin() as conn:
        for table, columns in SCHEMA_ADDITIONS.items():
            if not inspector.has_table(table):
                continue
            existing = _existing_columns(inspector, table)
            for column, col_type in columns.items():
                if column in existing:
                    continue
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )

        if inspector.has_table("production_orders"):
            for old, new in PRODUCTION_STATUS_MAP.items():
                conn.execute(
                    text(
                        "UPDATE production_orders SET status = :new "
                        "WHERE lower(status) = :old"
                    ),
                    {"old": old, "new": new},
                )

        if inspector.has_table("quotation_items"):
            item_cols = _existing_columns(inspector, "quotation_items")
            if "logo_type" in item_cols and "logo" in item_cols:
                conn.execute(
                    text(
                        "UPDATE quotation_items SET logo_type = 'grabado' "
                        "WHERE (logo = 1 OR logo = TRUE) "
                        "AND (logo_type IS NULL OR logo_type = '' OR logo_type = 'sin_logo')"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE quotation_items SET logo_type = 'sin_logo' "
                        "WHERE logo_type IS NULL OR logo_type = ''"
                    )
                )


