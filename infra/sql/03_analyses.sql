-- Base db_analyses
--   sudo -u postgres psql -d db_analyses -f 03_analyses.sql
-- avis_id est une référence logique vers db_collecte. UNIQUE : une analyse par avis (écriture idempotente).
-- organisation_id et etablissement_id : transmis par le message de file (service-collecte -> Function -> service-analyses).
-- etablissement_id est NULL pour les analyses antérieures à la migration 003 (non retrouvable depuis cette base).
CREATE TABLE IF NOT EXISTS analyses_sentiment (
  id SERIAL PRIMARY KEY,
  organisation_id INT NOT NULL,
  etablissement_id INT,
  avis_id INT NOT NULL UNIQUE,
  sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
  score_positif NUMERIC(4,3),
  score_neutre NUMERIC(4,3),
  score_negatif NUMERIC(4,3),
  -- Date de l'avis si elle est connue (avis importé), sinon celle de l'analyse : base des tendances.
  date_avis TIMESTAMPTZ,
  analyse_le TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_analyses_organisation ON analyses_sentiment (organisation_id);
CREATE INDEX IF NOT EXISTS idx_analyses_etablissement ON analyses_sentiment (organisation_id, etablissement_id);

-- Mots-clés extraits par Azure AI Language (extract_key_phrases) : base des « thèmes » du tableau de bord.
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

-- Alertes : avis très négatifs signalés par la Function. Une alerte au plus par avis.
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
