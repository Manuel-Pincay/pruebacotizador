from sqlalchemy import inspect, text

from app.database import engine


def _sqlite_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def run_sqlite_migrations():
    """Añade columnas faltantes sin alterar datos existentes (SQLite)."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)

    additions = {
        "production_orders": {
            "assigned_to": "VARCHAR",
            "started_at": "DATETIME",
            "completed_at": "DATETIME",
            "notes": "VARCHAR",
            "design_file_name": "VARCHAR",
            "design_material": "VARCHAR",
            "design_size": "VARCHAR",
            "design_usb_reference": "VARCHAR",
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
            "customer_id_number": "VARCHAR",
        },
        "company_config": {
            "guide_sender_name": "VARCHAR",
            "guide_sender_city": "VARCHAR",
            "guide_sender_region": "VARCHAR",
            "guide_sender_phone": "VARCHAR",
            "guide_sender_address": "VARCHAR",
        },
    }

    status_map = {
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

    with engine.begin() as conn:
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = _sqlite_columns(conn, table)
            for column, col_type in columns.items():
                if column not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                        )
                    )

        if inspector.has_table("production_orders"):
            for old, new in status_map.items():
                conn.execute(
                    text("UPDATE production_orders SET status = :new WHERE lower(status) = :old"),
                    {"old": old, "new": new},
                )
