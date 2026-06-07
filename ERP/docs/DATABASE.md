# Base de datos ERP

## Resumen

| Entorno | Motor | Puerto | Cómo se levanta |
|---------|-------|--------|-----------------|
| **Desarrollo** | MariaDB portable | 3307 | `python run.py` (auto) o `python scripts/setup_local_mysql.py` |
| **Producción** | MySQL 8+ | 3306 | Docker, VPS o servicio Windows/Linux |

El esquema siempre se gestiona con **Alembic**. No uses `create_all()`.

---

## Desarrollo (Windows local)

### Primera vez

```powershell
pip install -r requirements.txt
python scripts/init_database.py
python run.py
```

`init_database.py` hace:
1. Inicia MariaDB portable (si aplica)
2. `alembic upgrade head`
3. Carga catálogos base (categorías, materiales, etc.)

### Día a día

```powershell
python run.py
```

Si MariaDB no está activo, `run.py` lo inicia solo.

### Reiniciar desde cero (borrar todos los datos)

```powershell
python scripts/reset_dev_database.py --yes
python run.py
```

Elimina y recrea la base `erp`, aplica migraciones y carga catálogos base.

Los datos de MariaDB portable viven en `tools/mariadb/data/` (no commitear).

---

## Producción

### Opción A — Docker (recomendada)

```bash
cp .env.example .env
# ERP_ENV=production
# DATABASE_URL=mysql+pymysql://erp_user:PASSWORD@mysql:3306/erp?charset=utf8mb4
# ERP_SECRET_KEY=<aleatoria>

docker compose up -d --build
```

La app ejecuta `alembic upgrade head` al arrancar.

### Opción B — VPS / MySQL instalado

```bash
mysql -u root -p < docs/mysql_setup.sql
# Editar contraseña en mysql_setup.sql antes

alembic upgrade head
python scripts/init_database.py --skip-portable
```

Variables obligatorias en `.env`:
- `ERP_ENV=production`
- `DATABASE_URL=...` (MySQL real, **no** puerto 3307)
- `ERP_SECRET_KEY` aleatoria
- `ERP_COOKIE_SECURE=true` si hay HTTPS

---

## Backups

```powershell
python scripts/backup_mysql.py
```

Genera `backups/erp_YYYYMMDD_HHMMSS.sql`.

En producción, programar diario con cron o Task Scheduler:

```bash
python scripts/backup_mysql.py
```

---

## Notas

- **3307** = solo desarrollo (MariaDB portable).
- **3306** = MySQL de producción o Docker.
- No uses MariaDB portable en producción.
- Tras cambiar modelos: `alembic revision --autogenerate -m "..."` y `alembic upgrade head`.
