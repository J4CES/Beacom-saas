-- Migration 001 (db_etablissements) : rattachement à une organisation. Idempotente.
BEGIN;

ALTER TABLE etablissements ADD COLUMN IF NOT EXISTS organisation_id INT;
UPDATE etablissements SET organisation_id = 1 WHERE organisation_id IS NULL;
ALTER TABLE etablissements ALTER COLUMN organisation_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_etablissements_organisation ON etablissements (organisation_id);

-- source_id devient unique par organisation (et non plus sur toute la base).
ALTER TABLE etablissements DROP CONSTRAINT IF EXISTS etablissements_source_id_key;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'etablissements_organisation_source_id_key') THEN
    ALTER TABLE etablissements ADD CONSTRAINT etablissements_organisation_source_id_key
      UNIQUE (organisation_id, source_id);
  END IF;
END $$;

COMMIT;
