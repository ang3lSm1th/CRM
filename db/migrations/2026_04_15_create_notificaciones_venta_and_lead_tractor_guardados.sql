-- Persistencia de series/equipos guardados desde Seguimiento
CREATE TABLE IF NOT EXISTS lead_tractor_guardados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lead_id INT NOT NULL,
    codigo_lead VARCHAR(30) NOT NULL,
    serie VARCHAR(80) NOT NULL,
    equipo VARCHAR(180) NULL,
    modelo VARCHAR(220) NULL,
    estado VARCHAR(80) NULL,
    proceso VARCHAR(60) NULL,
    guardado_por INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ltg_lead (lead_id),
    INDEX idx_ltg_serie (serie),
    UNIQUE KEY uq_ltg_lead_proceso (lead_id, proceso)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
