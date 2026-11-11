export type Role = "admin" | "gestionnaire" | "lecteur";
export type Plan = "gratuit" | "pro" | "entreprise";
export type Sentiment = "positive" | "neutral" | "mixed" | "negative";

export interface Moi {
  id: number;
  email: string;
  role: Role;
  organisation_id: number;
  plan: Plan;
}

export interface Organisation {
  id: number;
  nom: string;
  plan: Plan;
  limites: { etablissements: number | null; avis_par_mois: number | null };
}

export interface Utilisateur {
  id: number;
  email: string;
  nom: string | null;
  role: Role;
  actif: boolean;
}

export interface Etablissement {
  id: number;
  nom: string;
  categorie: string | null;
  adresse: string | null;
  ville: string | null;
  jeton_public: string;
}

export interface Avis {
  id: number;
  etablissement_id: number;
  auteur: string | null;
  note: number | null;
  texte: string;
  source: string | null;
  statut: "nouveau" | "en_file" | "analyse";
  collecte_le: string;
}

export interface Analyse {
  avis_id: number;
  sentiment: Sentiment;
  score_negatif: number;
}

export interface PointTendance {
  periode: string;
  positive: number;
  neutral: number;
  mixed: number;
  negative: number;
  total: number;
}

export interface Alerte {
  id: number;
  avis_id: number;
  etablissement_id: number | null;
  score_negatif: number;
  extrait: string;
  creee_le: string;
}

export const SENTIMENTS: Sentiment[] = ["positive", "neutral", "mixed", "negative"];
export const LIBELLES_SENTIMENT: Record<Sentiment, string> = {
  positive: "Positif",
  neutral: "Neutre",
  mixed: "Mitigé",
  negative: "Négatif",
};
