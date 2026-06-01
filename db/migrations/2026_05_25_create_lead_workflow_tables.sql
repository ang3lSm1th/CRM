-- ============================================================
-- Workflow multiagente de leads (diagrama TO-BE)
-- Fecha: 2026-05-25
-- Ejecutar después de tener la tabla `leads` creada.
-- ============================================================

CREATE TABLE IF NOT EXISTS lead_agent_state (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    lead_id INT NOT NULL,
    current_node VARCHAR(50) NOT NULL DEFAULT 'scoring',
    score INT NOT NULL DEFAULT 0,
    priority_label VARCHAR(20) NULL,
    recommendation TEXT NULL,
    assigned_to INT NULL,
    attempts INT NOT NULL DEFAULT 0,
    last_action DATETIME NULL,
    next_action_date DATETIME NULL,
    data JSON NULL,
    workflow_status ENUM('active', 'paused', 'completed', 'dead') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_las_lead (lead_id),
    INDEX idx_las_node (current_node),
    INDEX idx_las_status (workflow_status),
    INDEX idx_las_score (score),
    CONSTRAINT fk_las_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_interactions (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    lead_id INT NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    interaction_type VARCHAR(50) NOT NULL DEFAULT 'system',
    direction ENUM('outbound', 'inbound') NOT NULL DEFAULT 'outbound',
    content TEXT NULL,
    response_received TINYINT(1) NOT NULL DEFAULT 0,
    response_content TEXT NULL,
    metadata JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_ai_lead (lead_id),
    INDEX idx_ai_agent (agent_name),
    INDEX idx_ai_created (created_at),
    CONSTRAINT fk_ai_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lead_workflow_kpi_snapshots (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    snapshot_date DATE NOT NULL,
    cac_promedio DECIMAL(12, 2) NULL,
    tasa_adquisicion DECIMAL(6, 2) NULL,
    score_promedio DECIMAL(6, 2) NULL,
    tasa_retencion DECIMAL(6, 2) NULL,
    tasa_abandono DECIMAL(6, 2) NULL,
    leads_activos INT UNSIGNED NOT NULL DEFAULT 0,
    leads_cerrados INT UNSIGNED NOT NULL DEFAULT 0,
    leads_muertos INT UNSIGNED NOT NULL DEFAULT 0,
    metadata JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_lwkpi_date (snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
