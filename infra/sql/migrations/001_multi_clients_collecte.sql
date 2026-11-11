-- Migration 001 (db_collecte) : rattachement à une organisation. Idempotente.
BEGIN;

ALTER TABLE avis ADD COLUMN IF NOT EXISTS organisation_id INT;
UPDATE avis SET organisation_id = 1 WHERE organisation_id IS NULL;
ALTER TABLE avis ALTER COLUMN organisation_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_avis_organisation ON avis (organisation_id, collecte_le);

COMMIT;
