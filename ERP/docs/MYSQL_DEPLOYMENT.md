# Guía de despliegue — ERP (MySQL)

Esta guía cubre el despliegue completo del ERP: creación de la base de datos MySQL, configuración del archivo `.env`, migraciones y puesta en marcha en desarrollo y producción.

---

## Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.10+ |
| MySQL o MariaDB | 8.0+ / 10.6+ |
| Sistema operativo | Windows, Linux o VPS |

**Dependencias Python:**

```bash
cd ERP
pip install -r requirements.txt
```

**Verificación automática** (Python, dependencias, MySQL):

```bash
python scripts/verify_startup.py
```

---

## Inicio rápido en Windows (sin instalar nada)

En un equipo **nuevo**, copie la carpeta `ERP` y ejecute:

```
iniciar_servidor.bat
```

El script descarga e instala automáticamente (solo la primera vez, requiere internet):

| Paso | Qué hace |
|---|---|
| 1 | **Python 3.12** en `tools/python312/` (si no hay Python en el PC) |
| 2 | Entorno virtual `venv/` + `pip install -r requirements.txt` |
| 3 | Crea `.env` desde `.env.example` si no existe |
| 4 | **MariaDB portable** en `tools/mariadb/` (puerto 3307) |
| 5 | Migraciones Alembic + inicia el servidor |

No necesita permisos de administrador. La primera ejecución puede tardar **10–15 minutos** (descargas). Las siguientes arrancan en segundos.

Acceso: `http://127.0.0.1:8000` — usuario `admin` / clave `123456`

---

```
1. Instalar Python + dependencias
2. Crear base de datos MySQL (usuario, contraseña, base "erp")
3. Copiar y editar .env
4. Ejecutar migraciones (alembic upgrade head)
5. Iniciar la aplicación
```

---

## 1. Crear la base de datos MySQL

El ERP usa una base llamada **`erp`** con codificación **utf8mb4**.

### Opción A — Servidor / VPS (MySQL instalado)

1. Edite `docs/mysql_setup.sql` y cambie la contraseña:

```sql
CREATE USER IF NOT EXISTS 'erp_user'@'%' IDENTIFIED BY 'SU_PASSWORD_FUERTE';
```

2. Ejecute el script como root:

```bash
mysql -u root -p < docs/mysql_setup.sql
```

3. Compruebe la conexión:

```bash
mysql -u erp_user -p -h 127.0.0.1 erp -e "SELECT 1"
```

> **Nota:** Si la app y MySQL están en el mismo servidor, el host puede ser `127.0.0.1`. Si MySQL está en otro equipo, use la IP del servidor y asegúrese de que el firewall permita el puerto **3306**.

### Opción B — Docker (solo MySQL)

```bash
cd ERP
copy .env.example .env    # Windows
# cp .env.example .env  # Linux

# Edite .env: MYSQL_PASSWORD y ERP_SECRET_KEY

docker compose up -d mysql
docker compose ps        # debe mostrar mysql "healthy"
```

Docker crea automáticamente la base `erp` y el usuario `erp_user` según las variables del `.env`.

### Opción C — Desarrollo local en Windows (sin instalar MySQL)

El proyecto incluye MariaDB portable (puerto **3307**):

```bash
python scripts/setup_local_mysql.py
```

Credenciales por defecto:

| Campo | Valor |
|---|---|
| Host | `127.0.0.1` |
| Puerto | `3307` |
| Base | `erp` |
| Usuario | `erp_user` |
| Contraseña | `erppassword` |

---

## 2. Configurar el archivo `.env`

El archivo `.env` **no se sube a Git**. Contiene secretos y la conexión a la base de datos.

### Crear el archivo

```bash
cd ERP
copy .env.example .env    # Windows
# cp .env.example .env    # Linux / Mac
```

### Variables obligatorias

Edite `.env` con un editor de texto. Ejemplo para **producción** (servidor con MySQL en puerto 3306):

```env
# ── Entorno ───────────────────────────────────────────────────
ERP_ENV=production

# ── Seguridad (CAMBIAR en producción) ─────────────────────────
# Generar clave: python -c "import secrets; print(secrets.token_hex(32))"
ERP_SECRET_KEY=a1b2c3d4e5f6...64_caracteres_hex
ERP_SECRETADMIN_PASSWORD=password_panel_admin_seguro

# Cookies seguras solo con HTTPS (true detrás de nginx/SSL)
ERP_COOKIE_SECURE=true

# ── Base de datos MySQL ───────────────────────────────────────
DATABASE_URL=mysql+pymysql://erp_user:SU_PASSWORD@127.0.0.1:3306/erp?charset=utf8mb4

DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_RECYCLE=3600
```

### Formato de `DATABASE_URL`

```
mysql+pymysql://USUARIO:CONTRASEÑA@HOST:PUERTO/NOMBRE_BASE?charset=utf8mb4
```

| Escenario | HOST | PUERTO | Ejemplo |
|---|---|---|---|
| MySQL en el mismo servidor | `127.0.0.1` | `3306` | `...@127.0.0.1:3306/erp?...` |
| MariaDB portable (Windows dev) | `127.0.0.1` | `3307` | `...@127.0.0.1:3307/erp?...` |
| Docker Compose (app en contenedor) | `mysql` | `3306` | `...@mysql:3306/erp?...` |
| MySQL en otro servidor | IP o dominio | `3306` | `...@192.168.1.50:3306/erp?...` |

> Si la contraseña contiene caracteres especiales (`@`, `#`, `%`, etc.), codifíquelos en URL (ej. `@` → `%40`).

### Variables opcionales

| Variable | Default | Descripción |
|---|---|---|
| `ERP_SESSION_MAX_AGE` | `604800` (7 días) | Duración sesión de usuarios (segundos) |
| `ERP_ADMIN_SESSION_MAX_AGE` | `3600` (1 hora) | Duración sesión `/secretadmin` |
| `ERP_PER_PAGE` | `20` | Registros por página en listados |
| `MYSQL_ROOT_PASSWORD` | — | Solo Docker Compose (servicio mysql) |
| `MYSQL_PASSWORD` | — | Solo Docker Compose (usuario `erp_user`) |

### Ejemplo `.env` — desarrollo local (Windows)

```env
ERP_ENV=development
ERP_SECRET_KEY=erp-dev-secret-change-in-production
ERP_SECRETADMIN_PASSWORD=203211
ERP_COOKIE_SECURE=false

DATABASE_URL=mysql+pymysql://erp_user:erppassword@127.0.0.1:3307/erp?charset=utf8mb4
```

### Checklist antes de producción

- [ ] `ERP_ENV=production`
- [ ] `ERP_SECRET_KEY` generada aleatoriamente (32+ bytes hex)
- [ ] `ERP_SECRETADMIN_PASSWORD` distinta del valor por defecto
- [ ] `DATABASE_URL` con contraseña fuerte (no `erppassword`)
- [ ] `ERP_COOKIE_SECURE=true` si usa HTTPS
- [ ] Archivo `.env` con permisos restrictivos (`chmod 600 .env` en Linux)

---

## 3. Migraciones de base de datos

El esquema se gestiona con **Alembic**. Ejecútelo después de crear la base y configurar `.env`:

```bash
cd ERP
alembic upgrade head
```

Al arrancar la app (`app.main`), también se ejecutan migraciones pendientes automáticamente.

**Usuario administrador inicial** (solo si no existe):

| Usuario | Contraseña |
|---|---|
| `admin` | `123456` |

> Cambie la contraseña del admin inmediatamente después del primer acceso en producción.

---

## 4. Iniciar la aplicación

### Desarrollo (Windows)

Doble clic en `iniciar_servidor.bat` o:

```bash
python scripts/run_server.py
```

El script verifica Python, dependencias y MySQL antes de iniciar.

### Producción (Linux / VPS)

Sin recarga automática:

```bash
cd ERP
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

**Servicio systemd** (ejemplo `/etc/systemd/system/erp.service`):

```ini
[Unit]
Description=ERP FastAPI
After=network.target mysql.service

[Service]
User=www-data
WorkingDirectory=/opt/erp/ERP
EnvironmentFile=/opt/erp/ERP/.env
ExecStart=/opt/erp/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable erp
sudo systemctl start erp
```

### Reverse proxy (nginx + HTTPS)

Exponga la app detrás de nginx y active SSL (Let's Encrypt). Con HTTPS, use `ERP_COOKIE_SECURE=true` en `.env`.

---

## 5. Despliegue con Docker (app + MySQL)

```bash
cd ERP
copy .env.example .env
# Editar: MYSQL_PASSWORD, ERP_SECRET_KEY, ERP_SECRETADMIN_PASSWORD

docker compose up -d --build
```

La app queda en `http://localhost:8000`. El contenedor ejecuta `alembic upgrade head` al arrancar.

Variables relevantes en `.env` para Docker:

```env
MYSQL_ROOT_PASSWORD=rootpassword_seguro
MYSQL_PASSWORD=password_erp_user_seguro
ERP_SECRET_KEY=clave_aleatoria_64_hex
ERP_SECRETADMIN_PASSWORD=password_admin
```

---

## 6. Carpetas persistentes

| Carpeta | Contenido | Backup |
|---|---|---|
| `uploads/` | Logos, imágenes de productos, diseños | Sí |
| `tools/mariadb/data/` | Datos MariaDB portable (solo dev) | Opcional |

MySQL en servidor o Docker usa su propio volumen/datadir; haga backup con `mysqldump`.

---

## 7. Backups MySQL

**Manual:**

```bash
mysqldump -u erp_user -p erp > backup_erp_$(date +%Y%m%d).sql
```

**Restaurar:**

```bash
mysql -u erp_user -p erp < backup_erp_20260613.sql
```

**Cron diario (Linux):**

```cron
0 2 * * * mysqldump -u erp_user -p'SU_PASSWORD' erp > /backups/erp_$(date +\%Y\%m\%d).sql
```

---

## 8. Solución de problemas

| Error | Causa probable | Solución |
|---|---|---|
| `Access denied for user 'erp_user'` | Contraseña incorrecta en `.env` | Verifique `DATABASE_URL` y usuario en MySQL |
| `Can't connect to MySQL server` | Servicio detenido o puerto incorrecto | Inicie MySQL; revise host/puerto en `.env` |
| `Unknown database 'erp'` | Base no creada | Ejecute `docs/mysql_setup.sql` |
| `Faltan paquetes` | Dependencias no instaladas | `pip install -r requirements.txt` |
| MariaDB no responde (dev) | Puerto 3307 apagado | `python scripts/setup_local_mysql.py` |
| `ERP_SECRET_KEY` por defecto | `.env` no configurado | Genere clave y reinicie la app |

**Diagnóstico completo:**

```bash
python scripts/verify_startup.py
```

---

## 9. Referencia rápida de comandos

```bash
# Verificar requisitos
python scripts/verify_startup.py

# MariaDB local (Windows, puerto 3307)
python scripts/setup_local_mysql.py

# Migraciones
alembic upgrade head
alembic current

# Desarrollo
python scripts/run_server.py

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

# Docker
docker compose up -d --build
docker compose logs -f app
```

---

## Archivos relacionados

| Archivo | Uso |
|---|---|
| `.env.example` | Plantilla para crear `.env` |
| `docs/mysql_setup.sql` | Crear base y usuario en MySQL manual |
| `docker-compose.yml` | MySQL + app en contenedores |
| `scripts/verify_startup.py` | Verificación pre-arranque |
| `scripts/setup_local_mysql.py` | MariaDB portable (desarrollo Windows) |
| `alembic/versions/` | Historial de migraciones de esquema |
