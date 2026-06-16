# Checklist — Migración SQLite → MySQL

## Pre-migración

- [ ] Leer `docs/MYSQL_DEPLOYMENT.md`
- [ ] MySQL 8+ instalado y accesible
- [ ] Usuario `erp_user` y base `erp` creados (`docs/mysql_setup.sql`)
- [ ] `pip install -r requirements.txt` (incluye pymysql, alembic)
- [ ] Backup: `python scripts/backup_sqlite.py`
- [ ] Checksum SHA256 del backup verificado
- [ ] Dry-run: `migrate_sqlite_to_mysql.py --dry-run`

## Migración

- [ ] `migrate_sqlite_to_mysql.py` ejecutado sin errores
- [ ] Log en `logs/migration_*.log` revisado
- [ ] `validate_migration.py` → RESULTADO: ÉXITO
- [ ] Reporte JSON generado (`migration_report_*.json`)

## Validación de datos

- [ ] 16 tablas con conteos iguales SQLite vs MySQL
- [ ] FKs sin huérfanos
- [ ] IDs preservados (spot-check cotizaciones, clientes)
- [ ] `company_config` intacto (logo, colores, IVA)

## Validación funcional

- [ ] Login usuarios (admin, ventas, producción)
- [ ] CRUD clientes
- [ ] CRUD productos + catálogos (product-settings)
- [ ] Crear / editar cotización
- [ ] PDF cotización
- [ ] Producción (kanban, estados)
- [ ] Inventario
- [ ] Despachos
- [ ] Configuración empresa
- [ ] Importación Excel
- [ ] Activity logs

## Switch a producción

- [ ] `.env` con `DATABASE_URL` MySQL
- [ ] `ERP_ENV=production`
- [ ] `ERP_SECRET_KEY` único generado
- [ ] `ERP_COOKIE_SECURE=true` (con HTTPS)
- [ ] Pool configurado (DB_POOL_SIZE=20)
- [ ] App reiniciada y estable 24h

## Post-producción

- [ ] Backup MySQL automatizado (`mysqldump` cron)
- [ ] SQLite original archivado (no borrado)
- [ ] Firewall: MySQL no expuesto públicamente innecesariamente
- [ ] Documentar credenciales en gestor seguro

## Rollback (si falla)

Ver `docs/MYSQL_ROLLBACK.md`

- [ ] Detener app
- [ ] Restaurar `DATABASE_URL` SQLite
- [ ] Restaurar backup `.db` si aplica
- [ ] Reiniciar y verificar login
