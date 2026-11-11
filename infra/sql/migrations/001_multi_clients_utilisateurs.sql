-- Migration 001 (db_utilisateurs) : organisations. Idempotente.
BEGIN;

CREATE TABLE IF NOT EXISTS organisations (
  id SERIAL PRIMARY KEY,
  nom VARCHAR(255) NOT NULL,
  plan VARCHAR(20) NOT NULL DEFAULT 'gratuit' CHECK (plan IN ('gratuit', 'pro', 'entreprise')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Organisation 1 : reçoit les données antérieures au multi-clients.
INSERT INTO organisations (id, nom, plan) VALUES (1, 'Organisation par défaut', 'entreprise')
ON CONFLICT (id) DO NOTHING;
SELECT setval(pg_get_serial_sequence('organisations', 'id'), (SELECT MAX(id) FROM organisations));

ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS organisation_id INT;
UPDATE utilisateurs SET organisation_id = 1 WHERE organisation_id IS NULL;
ALTER TABLE utilisateurs ALTER COLUMN organisation_id SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'utilisateurs_organisation_id_fkey') THEN
    ALTER TABLE utilisateurs ADD CONSTRAINT utilisateurs_organisation_id_fkey
      FOREIGN KEY (organisation_id) REFERENCES organisations (id);
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_utilisateurs_organisation ON utilisateurs (organisation_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;

COMMIT;
