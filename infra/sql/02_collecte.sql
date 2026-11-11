-- Base db_collecte
--   sudo -u postgres psql -d db_collecte -f 02_collecte.sql
-- etablissement_id est une référence logique vers db_etablissements (pas de clé étrangère entre bases) :
-- service-collecte vérifie l'existence via l'API de service-etablissements.
-- organisation_id : référence logique vers db_utilisateurs, issue du jeton JWT.
CREATE TABLE IF NOT EXISTS avis (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  etablissement_id INT NOT NULL,
  auteur VARCHAR(255),
  note SMALLINT CHECK (note BETWEEN 1 AND 5),
  texte TEXT NOT NULL,
  langue VARCHAR(10),
  date_avis TIMESTAMPTZ,
  source VARCHAR(100),
  collecte_le TIMESTAMPTZ DEFAULT now(),
  statut VARCHAR(20) NOT NULL DEFAULT 'nouveau' CHECK (statut IN ('nouveau', 'en_file', 'analyse'))
);
CREATE INDEX IF NOT EXISTS idx_avis_etablissement ON avis (etablissement_id);
CREATE INDEX IF NOT EXISTS idx_avis_statut ON avis (statut);
CREATE INDEX IF NOT EXISTS idx_avis_organisation ON avis (organisation_id, collecte_le);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO beacom;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO beacom;
