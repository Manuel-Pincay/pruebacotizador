-- =============================================================================
-- MySQL 8+ / MariaDB 10.6+ — Creación de base de datos ERP
-- =============================================================================
-- Uso:
--   1. Edite la contraseña en CREATE USER (línea ~15)
--   2. Ejecute:  mysql -u root -p < docs/mysql_setup.sql
--   3. Configure DATABASE_URL en .env con la misma contraseña
-- Guía: docs/MYSQL_DEPLOYMENT.md
-- =============================================================================

CREATE DATABASE IF NOT EXISTS erp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- [CAMBIAR] Use una contraseña fuerte (mínimo 16 caracteres, letras+números+símbolos)
CREATE USER IF NOT EXISTS 'erp_user'@'localhost' IDENTIFIED BY 'CAMBIAR_PASSWORD_FUERTE';
CREATE USER IF NOT EXISTS 'erp_user'@'127.0.0.1' IDENTIFIED BY 'CAMBIAR_PASSWORD_FUERTE';
CREATE USER IF NOT EXISTS 'erp_user'@'%' IDENTIFIED BY 'CAMBIAR_PASSWORD_FUERTE';

GRANT ALL PRIVILEGES ON erp.* TO 'erp_user'@'localhost';
GRANT ALL PRIVILEGES ON erp.* TO 'erp_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON erp.* TO 'erp_user'@'%';

FLUSH PRIVILEGES;

-- Verificación
SELECT 'Base erp creada correctamente' AS resultado;
SHOW DATABASES LIKE 'erp';

-- Ejemplo DATABASE_URL para .env:
-- DATABASE_URL=mysql+pymysql://erp_user:CAMBIAR_PASSWORD_FUERTE@127.0.0.1:3306/erp?charset=utf8mb4
