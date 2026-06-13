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
    if not inspector.has_table("production_orders"):
        return

    additions = {
        "production_orders": {
            "assigned_to": "VARCHAR",
            "started_at": "DATETIME",
            "completed_at": "DATETIME",
            "notes": "VARCHAR",
        }
    }

    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = _sqlite_columns(conn, table)
            for column, col_type in columns.items():
                if column not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                        )
                    )
