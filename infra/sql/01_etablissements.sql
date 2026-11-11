-- Base db_etablissements
--   sudo -u postgres psql -d db_etablissements -f 01_etablissements.sql
-- organisation_id est une référence logique vers db_utilisateurs (pas de clé étrangère entre bases) :
-- il vient du jeton JWT et chaque requête filtre dessus.
CREATE TABLE IF NOT EXISTS etablissements (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  nom VARCHAR(255) NOT NULL,
  categorie VARCHAR(100),
  adresse TEXT,
  ville VARCHAR(100),
  source_id VARCHAR(255),
  -- Jeton du lien public / QR code de collecte : 32 caractères hexadécimaux aléatoires (122 bits), non devinable.
  jeton_public VARCHAR(64) NOT NULL UNIQUE DEFAULT replace(gen_random_uuid()::text, '-', ''),
  created_at TIMESTAMPTZ DEFAULT now(),
  -- Unicité par organisation : un 409 ne doit rien révéler des données d'un autre client.
  CONSTRAINT etablissements_organisation_source_id_key UNIQUE (organisation_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_etablissements_organisation ON etablissements (organisation_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
