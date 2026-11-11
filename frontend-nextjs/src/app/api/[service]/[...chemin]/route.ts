import { NextRequest } from "next/server";

import { cheminAutorise, erreur, origineValide, relayer } from "@/lib/passerelle";

type Contexte = { params: Promise<{ service: string; chemin: string[] }> };

/** Passerelle authentifiée : /api/<service>/<chemin> -> <URL du service>/<chemin>, avec le jeton du cookie. */
async function relais(req: NextRequest, { params }: Contexte) {
  const { service, chemin } = await params;
  if (!cheminAutorise(service, chemin)) return erreur(404, "Route inconnue");
  if (!origineValide(req)) return erreur(403, "Origine non autorisée");
  return relayer(req, service, "/" + chemin.map(encodeURIComponent).join("/"));
}

export { relais as GET, relais as POST, relais as PATCH, relais as DELETE };
