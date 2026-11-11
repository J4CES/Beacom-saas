-- Base db_utilisateurs
--   sudo -u postgres createdb db_utilisateurs
--   sudo -u postgres psql -d db_utilisateurs -f 04_utilisateurs.sql
CREATE TABLE IF NOT EXISTS utilisateurs (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  nom VARCHAR(255),
  mot_de_passe_hash TEXT NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'lecteur' CHECK (role IN ('admin', 'gestionnaire', 'lecteur')),
  actif BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
