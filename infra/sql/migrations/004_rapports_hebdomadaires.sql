-- Migration 004 (db_analyses) : rapports hebdomadaires. Idempotente.
BEGIN;

-- Rapports hebdomadaires, calculés chaque lundi par la Function planifiée. Un rapport par organisation et par semaine.
CREATE TABLE IF NOT EXISTS rapports (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  semaine_debut DATE NOT NULL,
  contenu JSONB NOT NULL,
  cree_le TIMESTAMPTZ DEFAULT now(),
  UNIQUE (organisation_id, semaine_debut)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;

COMMIT;
