-- Base db_analyses
--   sudo -u postgres psql -d db_analyses -f 03_analyses.sql
-- avis_id est une référence logique vers db_collecte. UNIQUE : une analyse par avis (écriture idempotente).
-- organisation_id : transmis par le message de file (service-collecte -> Function -> service-analyses).
CREATE TABLE IF NOT EXISTS analyses_sentiment (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  avis_id INT NOT NULL UNIQUE,
  sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
  score_positif NUMERIC(4,3),
  score_neutre NUMERIC(4,3),
  score_negatif NUMERIC(4,3),
  analyse_le TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_analyses_organisation ON analyses_sentiment (organisation_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
