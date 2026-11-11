-- Migration 002 (db_etablissements) : jeton public de collecte. Idempotente.
-- Le défaut est volatil : chaque établissement existant reçoit un jeton différent.
BEGIN;

ALTER TABLE etablissements
  ADD COLUMN IF NOT EXISTS jeton_public VARCHAR(64) NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', '');

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'etablissements_jeton_public_key') THEN
    ALTER TABLE etablissements ADD CONSTRAINT etablissements_jeton_public_key UNIQUE (jeton_public);
  END IF;
END $$;

COMMIT;
