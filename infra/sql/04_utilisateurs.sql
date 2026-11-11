-- Base db_utilisateurs
--   sudo -u postgres createdb db_utilisateurs
--   sudo -u postgres psql -d db_utilisateurs -f 04_utilisateurs.sql
-- Une organisation = un client de Beacom (multi-clients). Son plan fixe les limites d'usage.
CREATE TABLE IF NOT EXISTS organisations (
  id SERIAL PRIMARY KEY,
  nom VARCHAR(255) NOT NULL,
  plan VARCHAR(20) NOT NULL DEFAULT 'gratuit' CHECK (plan IN ('gratuit', 'pro', 'entreprise')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS utilisateurs (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL REFERENCES organisations (id),
  email VARCHAR(255) NOT NULL UNIQUE,
  nom VARCHAR(255),
  mot_de_passe_hash TEXT NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'lecteur' CHECK (role IN ('admin', 'gestionnaire', 'lecteur')),
  actif BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_utilisateurs_organisation ON utilisateurs (organisation_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
