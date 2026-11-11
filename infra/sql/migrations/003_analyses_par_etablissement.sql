-- Migration 003 (db_analyses) : établissement, date de l'avis, mots-clés et alertes. Idempotente.
-- Les analyses existantes gardent etablissement_id NULL : elles comptent dans les totaux de l'organisation,
-- pas dans les filtres par établissement.
BEGIN;

ALTER TABLE analyses_sentiment ADD COLUMN IF NOT EXISTS etablissement_id INT;
ALTER TABLE analyses_sentiment ADD COLUMN IF NOT EXISTS date_avis TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_analyses_etablissement ON analyses_sentiment (organisation_id, etablissement_id);

CREATE TABLE IF NOT EXISTS mots_cles (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  etablissement_id INT,
  avis_id INT NOT NULL,
  sentiment VARCHAR(20) NOT NULL,
  mot_cle VARCHAR(200) NOT NULL,
  UNIQUE (avis_id, mot_cle)
);
CREATE INDEX IF NOT EXISTS idx_mots_cles_organisation ON mots_cles (organisation_id, sentiment);

CREATE TABLE IF NOT EXISTS alertes (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  etablissement_id INT,
  avis_id INT NOT NULL UNIQUE,
  score_negatif NUMERIC(4,3) NOT NULL,
  extrait VARCHAR(300) NOT NULL,
  traitee BOOLEAN NOT NULL DEFAULT false,
  creee_le TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alertes_organisation ON alertes (organisation_id, traitee);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;

COMMIT;
