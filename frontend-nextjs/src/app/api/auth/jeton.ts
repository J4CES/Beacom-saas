import { NextRequest, NextResponse } from "next/server";

import { erreur, origineValide, relayer } from "@/lib/passerelle";
import { poserJeton } from "@/lib/session";

/** Connexion ou inscription : le jeton renvoyé par service-utilisateurs part dans un cookie HttpOnly, jamais dans le JSON. */
export async function obtenirJeton(req: NextRequest, chemin: "/auth/login" | "/auth/inscription") {
  if (!origineValide(req)) return erreur(403, "Origine non autorisée");
  const reponse = await relayer(req, "utilisateurs", chemin, { avecJeton: false });
  if (!reponse.ok) return reponse;
  const { access_token, expires_in, ...reste } = await reponse.json();
  const sortie = NextResponse.json(reste, { status: reponse.status });
  poserJeton(sortie, access_token, expires_in);
  return sortie;
}
