-- Tabla para registrar historial de cambios de asignación, bien/servicio y canal de recepción en leads
CREATE TABLE IF NOT EXISTS lead_cambios (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    lead_id     INT          NOT NULL,
    campo       VARCHAR(50)  NOT NULL,          -- 'asignado_a' | 'bien_servicio_id' | 'canal_id'
    valor_anterior TEXT,
    valor_nuevo    TEXT,
    usuario_id  INT,
    usuario_nombre VARCHAR(150),
    fecha       DATETIME NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_lead_cambios_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
