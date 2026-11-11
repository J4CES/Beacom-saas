-- Base db_etablissements
--   sudo -u postgres psql -d db_etablissements -f 01_etablissements.sql
CREATE TABLE IF NOT EXISTS etablissements (
  id SERIAL PRIMARY KEY,
  nom VARCHAR(255) NOT NULL,
  categorie VARCHAR(100),
  adresse TEXT,
  ville VARCHAR(100),
  source_id VARCHAR(255) UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
