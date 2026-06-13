# Auditoría de compatibilidad SQLite → MySQL

## Resumen

| Aspecto | Estado |
|---------|--------|
| Tablas | 16 — compatibles |
| Registros actuales (dev) | ~54 |
| Huérfanos FK detectados | 0 |
| Bloqueantes | Ninguno tras ajustes implementados |

## Incompatibilidades resueltas

| # | Problema | Solución implementada |
|---|----------|----------------------|
| 1 | `String` sin longitud en MySQL | Alembic `001_initial` usa `String(n)` / `Text` |
| 2 | `DATABASE_URL` hardcodeado | Variable de entorno en `settings.py` |
| 3 | Pool MySQL | `pool_pre_ping`, `pool_recycle`, `pool_size`, `max_overflow` |
| 4 | `create_all()` en MySQL | Solo activo con SQLite (`settings.is_sqlite`) |
| 5 | Migraciones ad-hoc SQLite | `db_migrations.py` + columnas en Alembic 001 |
| 6 | Preservación de IDs | Script migración con INSERT explícito + AUTO_INCREMENT |
| 7 | Índices FK | Alembic `002_indexes` |

## Mapa de tablas y FKs

```
clients ← quotations ← quotation_items → products
                ↓              ↓
         production_orders  (product_id nullable)
                ↓
            shipments

products ← inventory_movements

Independientes: users, company_config, activity_logs,
                product_categories, product_colors, product_materials,
                product_themes, product_thicknesses, measurement_units
```

## Orden de migración de datos

1. company_config
2. users
3. clients
4. Catálogos (6 tablas)
5. products
6. quotations
7. quotation_items
8. production_orders
9. shipments
10. inventory_movements
11. activity_logs

## Índices añadidos (002)

- `clients.name`
- `products.code`, `products.name`
- `quotations.client_id`, `quotations.status`
- `quotation_items.quotation_id`
- `production_orders.status`, `production_orders.quotation_id`
- `shipments.quotation_id`
- `inventory_movements.product_id`

## Archivos entregados

| Entregable | Ubicación |
|-----------|-----------|
| Config dual DB | `app/database.py`, `app/config/settings.py` |
| Alembic | `alembic.ini`, `alembic/env.py`, `alembic/versions/` |
| Backup | `scripts/backup_sqlite.py` |
| Migración | `scripts/migrate_sqlite_to_mysql.py` |
| Validación | `scripts/validate_migration.py` |
| MySQL setup | `docs/mysql_setup.sql` |
| Docker | `docker-compose.yml`, `Dockerfile` |
| Despliegue | `docs/MYSQL_DEPLOYMENT.md` |
| Rollback | `docs/MYSQL_ROLLBACK.md` |
| Checklist | `docs/MYSQL_MIGRATION_CHECKLIST.md` |

## Comportamiento por entorno

| Entorno | DATABASE_URL | Esquema |
|---------|--------------|---------|
| Dev local | sqlite:///... | `create_all()` + db_migrations |
| Staging/Prod | mysql+pymysql://... | Alembic `upgrade head` |

## Riesgos residuales

| Riesgo | Mitigación |
|--------|------------|
| Truncado VARCHAR(255) | Campos largos usan `Text` |
| Timezone DateTime | Documentado — fechas naive UTC/local |
| Re-migración parcial | `--force` en script de migración |
