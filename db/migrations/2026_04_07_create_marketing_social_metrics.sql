-- Migration: create marketing_social_metrics table
-- Separada por negocio (Orbes, Lovol, etc.) con referencia FK a negocios.id

CREATE TABLE IF NOT EXISTS marketing_social_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    negocio_id INT NOT NULL,
    snapshot_date DATE NOT NULL,
    fb_page_id VARCHAR(80) DEFAULT NULL,
    ig_account_id VARCHAR(80) DEFAULT NULL,
    fb_followers INT DEFAULT NULL,
    ig_followers INT DEFAULT NULL,
    total_followers INT DEFAULT NULL,
    fb_target_followers INT DEFAULT NULL,
    ig_target_followers INT DEFAULT NULL,
    total_target_followers INT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ux_marketing_social_metrics_snapshot (negocio_id, snapshot_date),
    FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
);
