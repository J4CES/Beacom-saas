import { NextRequest } from "next/server";

import { erreur, origineValide, relayer } from "@/lib/passerelle";

/** Dépôt d'un avis par un client final, sans authentification (limitation de débit côté service-collecte). */
export async function POST(req: NextRequest, { params }: { params: Promise<{ jeton: string }> }) {
  if (!origineValide(req)) return erreur(403, "Origine non autorisée");
  const { jeton } = await params;
  return relayer(req, "collecte", `/public/avis/${encodeURIComponent(jeton)}`, { avecJeton: false });
}
