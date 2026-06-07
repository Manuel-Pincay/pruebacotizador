# Guía de rollback — SQLite

Si tras migrar a MySQL algo falla, puedes volver a SQLite en minutos.

## Cuándo hacer rollback

- Validación de conteos fallida
- Errores críticos en módulos (cotizaciones, PDF, login)
- MySQL inaccesible en producción

## Pasos

### 1. Detener la aplicación

```bash
# uvicorn / systemd / docker compose stop app
docker compose stop app
```

### 2. Restaurar DATABASE_URL a SQLite

En `.env`:

```env
ERP_ENV=development
DATABASE_URL=sqlite:///./database/innova.db
```

### 3. Restaurar backup SQLite (si fue modificado)

```bash
cp backups/innova_YYYYMMDD_HHMMSS.db database/innova.db
```

Verificar checksum:

```bash
# Linux/macOS
sha256sum -c backups/innova_YYYYMMDD_HHMMSS.db.sha256
```

### 4. Reiniciar aplicación

```bash
uvicorn app.main:app --reload
```

### 5. Verificar funcionalidad

- [ ] Login admin
- [ ] Listado clientes
- [ ] Cotizaciones
- [ ] PDF

## Rollback parcial (seguir en MySQL)

Si solo quieres conservar SQLite como respaldo:

1. No borres `database/innova.db`
2. No borres `backups/`
3. MySQL puede quedar como copia secundaria

## Reintentar migración

```bash
python scripts/migrate_sqlite_to_mysql.py \
  --mysql-url "mysql+pymysql://..." \
  --force
```

`--force` elimina tablas MySQL y repite la migración desde cero.

## Tiempo estimado

| Paso | Tiempo |
|------|--------|
| Cambiar .env | 1 min |
| Restaurar backup | 1 min |
| Reiniciar app | 1 min |
| **Total** | **< 5 min** |
