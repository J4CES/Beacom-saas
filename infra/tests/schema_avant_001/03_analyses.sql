-- Base db_analyses
--   sudo -u postgres psql -d db_analyses -f 03_analyses.sql
-- avis_id est une référence logique vers db_collecte. UNIQUE : une analyse par avis (écriture idempotente).
CREATE TABLE IF NOT EXISTS analyses_sentiment (
  id SERIAL PRIMARY KEY,
  avis_id INT NOT NULL UNIQUE,
  sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
  score_positif NUMERIC(4,3),
  score_neutre NUMERIC(4,3),
  score_negatif NUMERIC(4,3),
  analyse_le TIMESTAMPTZ DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
