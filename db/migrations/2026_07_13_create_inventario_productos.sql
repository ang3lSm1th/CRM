-- Inventario comercial para cotizaciones (SKU reales + precio + stock)
-- No confundir con marketing_inventario_mercaderia (promocional).

CREATE TABLE IF NOT EXISTS inventario_productos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo VARCHAR(40) NOT NULL,
  descripcion VARCHAR(255) NOT NULL,
  unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
  bien_servicio_id INT NOT NULL,
  linea_producto_id INT NULL,
  marca VARCHAR(80) NULL,
  especificacion VARCHAR(255) NULL,
  precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  incluye_igv TINYINT(1) NOT NULL DEFAULT 1,
  stock DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  stock_minimo DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_inventario_codigo (codigo),
  KEY idx_inv_bien (bien_servicio_id),
  KEY idx_inv_linea (linea_producto_id),
  KEY idx_inv_activo (activo),
  CONSTRAINT fk_inv_bien FOREIGN KEY (bien_servicio_id) REFERENCES bienes_servicios(id),
  CONSTRAINT fk_inv_linea_producto FOREIGN KEY (linea_producto_id) REFERENCES linea_producto(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
