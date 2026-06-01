-- Tablas de soporte para prediccion y metricas de modelos ML

CREATE TABLE IF NOT EXISTS predicciones_compra (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    lead_id INT NOT NULL,
    probabilidad_compra DECIMAL(6,5) NOT NULL,
    modelo_version VARCHAR(50) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_pred_lead (lead_id),
    INDEX idx_pred_fecha (created_at),
    INDEX idx_pred_modelo (modelo_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS metricas_modelos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    modelo_nombre VARCHAR(80) NOT NULL,
    modelo_version VARCHAR(50) NOT NULL,
    metrica_nombre VARCHAR(50) NOT NULL,
    metrica_valor DECIMAL(10,6) NOT NULL,
    observacion VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_metricas_modelo (modelo_nombre, modelo_version),
    INDEX idx_metricas_fecha (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
