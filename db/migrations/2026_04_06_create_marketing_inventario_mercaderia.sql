-- Migration: create marketing_inventario_mercaderia table
-- Run this on the database used by the app (e.g., via mysql client or admin tool)

CREATE TABLE IF NOT EXISTS marketing_inventario_mercaderia (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATE NOT NULL,
  tipo ENUM('Merchadising','Comunicacion','Publicidad') NOT NULL,
  producto VARCHAR(150) NOT NULL,
  precio DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  cantidad INT NOT NULL,
  total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  created_by INT NULL,
  negocio_id INT NULL,
  brand VARCHAR(32) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_mim_fecha (fecha),
  KEY idx_mim_tipo (tipo),
  KEY idx_mim_negocio_id (negocio_id),
  KEY idx_mim_brand (brand),
  CONSTRAINT fk_mim_user_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_mim_negocio FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
