-- Migration: add detalle column to marketing_feria_gastos
-- Run this on the database used by the app (e.g., via mysql client or admin tool)

ALTER TABLE marketing_feria_gastos
  ADD COLUMN detalle VARCHAR(255) NULL AFTER factura;

-- Optional: if you want larger text, use TEXT instead of VARCHAR(255)
-- ALTER TABLE marketing_feria_gastos
--   ADD COLUMN detalle TEXT NULL AFTER factura;
