-- Índices para acelerar reportes y KPIs (ejecutar una vez en MySQL).

ALTER TABLE leads
    ADD INDEX idx_leads_fecha (fecha),
    ADD INDEX idx_leads_negocio_fecha (negocio_id, fecha);

ALTER TABLE seguimientos
    ADD INDEX idx_seg_proceso_fecha (proceso_id, fecha_guardado),
    ADD INDEX idx_seg_lead_id_desc (lead_id, id);
