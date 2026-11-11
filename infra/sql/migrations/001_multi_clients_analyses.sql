-- Migration 001 (db_analyses) : rattachement à une organisation. Idempotente.
BEGIN;

ALTER TABLE analyses_sentiment ADD COLUMN IF NOT EXISTS organisation_id INT;
UPDATE analyses_sentiment SET organisation_id = 1 WHERE organisation_id IS NULL;
ALTER TABLE analyses_sentiment ALTER COLUMN organisation_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analyses_organisation ON analyses_sentiment (organisation_id);

COMMIT;
