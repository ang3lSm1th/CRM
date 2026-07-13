-- Detalle de productos de cotización por lead/seguimiento
CREATE TABLE IF NOT EXISTS cotizacion_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lead_id INT NOT NULL,
  seguimiento_id INT NULL,
  producto_id INT NULL,
  codigo VARCHAR(40) NOT NULL,
  descripcion VARCHAR(255) NOT NULL,
  unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
  cantidad DECIMAL(12,2) NOT NULL DEFAULT 1.00,
  precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_ci_lead (lead_id),
  KEY idx_ci_seg (seguimiento_id),
  KEY idx_ci_prod (producto_id),
  CONSTRAINT fk_ci_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
  CONSTRAINT fk_ci_seg FOREIGN KEY (seguimiento_id) REFERENCES seguimientos(id) ON DELETE SET NULL,
  CONSTRAINT fk_ci_prod FOREIGN KEY (producto_id) REFERENCES inventario_productos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
