-- ============================================================
-- Seguimiento -> Cerrado + ventas_concretadas (demo ene-mar 2026)
-- Ejecutar en MySQL. Respaldo incluido para revertir.
-- ============================================================

USE u349183440_crm_orbes;

START TRANSACTION;

CREATE TABLE IF NOT EXISTS seguimientos_backup_cerrado_demo (
    id INT NOT NULL PRIMARY KEY,
    lead_id INT NOT NULL,
    proceso_id INT NULL,
    cotizacion VARCHAR(10) NULL,
    monto DECIMAL(10,2) NULL,
    moneda_id INT NULL,
    fecha_guardado DATE NOT NULL,
    backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads_fecha_backup_cerrado_demo (
    lead_id INT NOT NULL PRIMARY KEY,
    fecha_original DATE NOT NULL,
    backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO seguimientos_backup_cerrado_demo
    (id, lead_id, proceso_id, cotizacion, monto, moneda_id, fecha_guardado)
SELECT s.id, s.lead_id, s.proceso_id, s.cotizacion, s.monto, s.moneda_id, s.fecha_guardado
FROM seguimientos s
JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls ON ls.last_id = s.id
JOIN proceso p ON p.id = s.proceso_id
WHERE LOWER(TRIM(p.nombre_proceso)) = 'seguimiento';

DROP TEMPORARY TABLE IF EXISTS tmp_leads_seguimiento;
CREATE TEMPORARY TABLE tmp_leads_seguimiento AS
SELECT
    l.id AS lead_id,
    COALESCE(l.asignado_a, 1) AS usuario_id,
    l.fecha AS fecha_lead,
    l.cliente_id,
    l.bien_servicio_id,
    (@rn := @rn + 1) AS rn
FROM leads l
CROSS JOIN (SELECT @rn := 0) init
JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls ON ls.lead_id = l.id
JOIN seguimientos s ON s.id = ls.last_id
JOIN proceso p ON p.id = s.proceso_id
WHERE LOWER(TRIM(p.nombre_proceso)) = 'seguimiento'
ORDER BY l.id;

INSERT IGNORE INTO leads_fecha_backup_cerrado_demo (lead_id, fecha_original)
SELECT lead_id, fecha_lead FROM tmp_leads_seguimiento;

DROP TEMPORARY TABLE IF EXISTS tmp_leads_demo;
CREATE TEMPORARY TABLE tmp_leads_demo AS
SELECT
    t.lead_id, t.usuario_id, t.cliente_id, t.bien_servicio_id,
    CASE MOD(t.lead_id, 3)
        WHEN 0 THEN DATE(CONCAT('2026-01-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
        WHEN 1 THEN DATE(CONCAT('2026-02-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
        ELSE DATE(CONCAT('2026-03-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
    END AS nueva_fecha,
    CONCAT('V', LPAD(260000 + t.rn, 6, '0')) AS cod_cotizacion,
    CASE WHEN MOD(t.rn, 2) = 0 THEN 1 ELSE 2 END AS moneda_id,
    ROUND(500 + (MOD(t.lead_id, 50) * 137.50), 2) AS monto_demo
FROM tmp_leads_seguimiento t;

UPDATE leads l
JOIN tmp_leads_demo d ON d.lead_id = l.id
SET l.fecha = d.nueva_fecha;

INSERT INTO seguimientos (
    lead_id, usuario_id, fecha_seguimiento, proceso_id,
    cotizacion, monto, moneda_id, comentario, fecha_guardado
)
SELECT
    d.lead_id, d.usuario_id, d.nueva_fecha, 5,
    d.cod_cotizacion, d.monto_demo, d.moneda_id,
    'Demo clase: cierre automático', d.nueva_fecha
FROM tmp_leads_demo d
WHERE NOT EXISTS (SELECT 1 FROM seguimientos sx WHERE sx.cotizacion = d.cod_cotizacion);

INSERT INTO ventas_concretadas (cliente_id, lead_id, bien_servicio_id, monto, fecha_venta)
SELECT d.cliente_id, d.lead_id, d.bien_servicio_id, d.monto_demo, d.nueva_fecha
FROM tmp_leads_demo d
WHERE NOT EXISTS (SELECT 1 FROM ventas_concretadas vc WHERE vc.lead_id = d.lead_id);

COMMIT;

-- REVERTIR:
-- DELETE s FROM seguimientos s
-- WHERE s.comentario = 'Demo clase: cierre automático';
-- UPDATE leads l JOIN leads_fecha_backup_cerrado_demo b ON b.lead_id = l.id SET l.fecha = b.fecha_original;
