# MySQL 8+ — configuración inicial ERP

CREATE DATABASE IF NOT EXISTS erp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'erp_user'@'%' IDENTIFIED BY 'CAMBIAR_PASSWORD_FUERTE';

GRANT ALL PRIVILEGES ON erp.* TO 'erp_user'@'%';

FLUSH PRIVILEGES;

-- Verificar
SHOW VARIABLES LIKE 'character_set_database';
SHOW VARIABLES LIKE 'collation_database';
