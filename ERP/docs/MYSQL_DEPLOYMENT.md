# Guía de despliegue — MySQL

Documentación completa: **[DATABASE.md](DATABASE.md)**

## Producción rápida (Docker)

```bash
docker compose up -d --build
```

## Producción (VPS)

```bash
mysql -u root -p < docs/mysql_setup.sql
alembic upgrade head
python scripts/init_database.py --skip-portable
```

## Backup

```bash
python scripts/backup_mysql.py
```
