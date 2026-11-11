"use client";

import { useCallback, useEffect, useState } from "react";

/** Erreur d'API avec un message lisible (le `detail` renvoyé par les services FastAPI). */
export class ErreurApi extends Error {
  constructor(
    message: string,
    public statut: number,
    public details?: unknown,
  ) {
    super(message);
  }
}

function messageDe(corps: unknown, statut: number): string {
  const detail = (corps as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Erreurs de validation FastAPI : [{loc, msg}, ...]
    return detail.map((e: { msg?: string }) => e.msg).filter(Boolean).join(" ; ") || "Données invalides";
  }
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: string }).message);
  if (statut === 429) return "Trop de tentatives : patientez quelques minutes";
  if (statut >= 500) return "Le service rencontre un problème, réessayez dans un instant";
  return `Erreur ${statut}`;
}

/** Appelle la passerelle /api/... Une réponse 401 renvoie vers la page de connexion. */
export async function api<T>(chemin: string, options: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...init } = options;
  const reponse = await fetch(`/api${chemin}`, {
    ...init,
    headers: json !== undefined ? { "content-type": "application/json", ...init.headers } : init.headers,
    body: json !== undefined ? JSON.stringify(json) : init.body,
  });
  if (reponse.status === 401 && !chemin.startsWith("/auth/") && !chemin.startsWith("/public/")) {
    window.location.href = `/connexion?suite=${encodeURIComponent(window.location.pathname)}`;
    throw new ErreurApi("Session expirée", 401);
  }
  const corps = reponse.status === 204 ? null : await reponse.json().catch(() => null);
  if (!reponse.ok) {
    const detail = (corps as { detail?: unknown } | null)?.detail;
    throw new ErreurApi(messageDe(corps, reponse.status), reponse.status, detail);
  }
  return corps as T;
}

/** Charge une ressource et expose les états de chargement et d'erreur. `chemin = null` : rien à charger. */
export function useDonnees<T>(chemin: string | null) {
  const [donnees, setDonnees] = useState<T | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(chemin !== null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (chemin === null) return;
    let annule = false;
    setChargement(true);
    setErreur(null);
    api<T>(chemin)
      .then((d) => !annule && setDonnees(d))
      .catch((e: Error) => !annule && setErreur(e.message))
      .finally(() => !annule && setChargement(false));
    return () => {
      annule = true;
    };
  }, [chemin, version]);

  const recharger = useCallback(() => setVersion((v) => v + 1), []);
  return { donnees, erreur, chargement, recharger };
}
