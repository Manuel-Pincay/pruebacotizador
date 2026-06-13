# Guía de despliegue — MySQL

## Requisitos

- Python 3.11+
- MySQL 8.0+ (local, VPS o Docker)
- Base SQLite existente en `database/innova.db`

## 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2. Crear base MySQL

### Opción A — VPS / servidor manual

```bash
mysql -u root -p < docs/mysql_setup.sql
```

Edita la contraseña en `docs/mysql_setup.sql` antes de ejecutar.

### Opción B — Docker

```bash
cp .env.example .env
# Editar MYSQL_PASSWORD y ERP_SECRET_KEY en .env

docker compose up -d mysql
# Esperar healthcheck OK
```

## 3. Backup obligatorio

```bash
python scripts/backup_sqlite.py
```

Verifica el SHA256 en `backups/innova_*.db.sha256`.

## 4. Dry-run (conteo sin escribir)

```bash
python scripts/migrate_sqlite_to_mysql.py \
  --mysql-url "mysql+pymysql://erp_user:PASSWORD@127.0.0.1:3306/erp?charset=utf8mb4" \
  --dry-run
```

## 5. Migración completa

```bash
python scripts/migrate_sqlite_to_mysql.py \
  --mysql-url "mysql+pymysql://erp_user:PASSWORD@127.0.0.1:3306/erp?charset=utf8mb4"
```

El script:

1. Crea backup SQLite
2. Ejecuta `alembic upgrade head` en MySQL
3. Copia datos preservando IDs
4. Valida conteos y FKs

## 6. Validación manual

```bash
python scripts/validate_migration.py \
  --mysql-url "mysql+pymysql://erp_user:PASSWORD@127.0.0.1:3306/erp?charset=utf8mb4"
```

## 7. Cambiar la aplicación a MySQL

En `.env`:

```env
ERP_ENV=production
DATABASE_URL=mysql+pymysql://erp_user:PASSWORD@127.0.0.1:3306/erp?charset=utf8mb4
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_RECYCLE=3600
ERP_COOKIE_SECURE=true
```

Reinicia:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 8. Docker completo (app + MySQL)

```bash
docker compose up -d --build
```

La app ejecuta `alembic upgrade head` al arrancar.

## 9. Backup MySQL en producción

Cron diario recomendado:

```bash
mysqldump -u erp_user -p erp > /backups/erp_$(date +%Y%m%d).sql
```

## Notas

- **Desarrollo local** puede seguir usando SQLite (`DATABASE_URL=sqlite:///./database/innova.db`).
- Con SQLite, `create_all()` sigue creando el esquema automáticamente.
- Con MySQL, el esquema se gestiona **solo con Alembic**.
- No elimines `database/innova.db` hasta validar MySQL en producción.
