-- ============================================================
-- FIX DEMO: sincronizar fechas de leads cerrados con ventas
-- duplicadas (ene/feb/mar 2026) para que aparezcan en /cerrados
-- ============================================================
-- IMPORTANTE: La vista "Cerrados" filtra por leads.fecha, NO por
-- ventas_concretadas.fecha_venta. Este script alinea ambos.

USE u349183440_crm_orbes;

START TRANSACTION;

-- Respaldo de fechas originales (ejecutar una sola vez)
CREATE TABLE IF NOT EXISTS leads_fecha_backup_demo (
    lead_id INT NOT NULL PRIMARY KEY,
    fecha_original DATE NOT NULL,
    backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO leads_fecha_backup_demo (lead_id, fecha_original)
SELECT l.id, l.fecha
FROM leads l
JOIN (
    SELECT lead_id, MAX(id) AS last_id
    FROM seguimientos
    GROUP BY lead_id
) ls ON ls.lead_id = l.id
JOIN seguimientos s ON s.id = ls.last_id
JOIN proceso p ON p.id = s.proceso_id
JOIN ventas_concretadas vc ON vc.lead_id = l.id
WHERE LOWER(TRIM(p.nombre_proceso)) = 'cerrado'
  AND vc.fecha_venta >= '2026-01-01'
  AND vc.fecha_venta < '2026-04-01';

-- Actualizar fecha del lead = fecha de la venta duplicada (ene-mar 2026)
UPDATE leads l
INNER JOIN (
    SELECT lead_id, MIN(fecha_venta) AS nueva_fecha
    FROM ventas_concretadas
    WHERE fecha_venta >= '2026-01-01'
      AND fecha_venta < '2026-04-01'
    GROUP BY lead_id
) vc ON vc.lead_id = l.id
INNER JOIN (
    SELECT lead_id, MAX(id) AS last_id
    FROM seguimientos
    GROUP BY lead_id
) ls ON ls.lead_id = l.id
INNER JOIN seguimientos s ON s.id = ls.last_id
INNER JOIN proceso p ON p.id = s.proceso_id
SET l.fecha = vc.nueva_fecha
WHERE LOWER(TRIM(p.nombre_proceso)) = 'cerrado';

-- Verificación
SELECT
    MONTH(l.fecha) AS mes,
    COUNT(*) AS cerrados
FROM leads l
JOIN (
    SELECT lead_id, MAX(id) AS last_id FROM seguimientos GROUP BY lead_id
) ls ON ls.lead_id = l.id
JOIN seguimientos s ON s.id = ls.last_id
JOIN proceso p ON p.id = s.proceso_id
WHERE LOWER(TRIM(p.nombre_proceso)) = 'cerrado'
  AND l.fecha >= '2026-01-01'
  AND l.fecha < '2026-04-01'
GROUP BY MONTH(l.fecha)
ORDER BY mes;

COMMIT;

-- ============================================================
-- REVERTIR (cuando termine la presentación)
-- ============================================================
-- START TRANSACTION;
-- UPDATE leads l
-- INNER JOIN leads_fecha_backup_demo b ON b.lead_id = l.id
-- SET l.fecha = b.fecha_original;
-- COMMIT;
