import { NextRequest } from "next/server";

import { relayer } from "@/lib/passerelle";

/** Page publique de dépôt d'avis : nom de l'établissement, sans authentification. */
export async function GET(req: NextRequest, { params }: { params: Promise<{ jeton: string }> }) {
  const { jeton } = await params;
  return relayer(req, "etablissements", `/public/etablissements/${encodeURIComponent(jeton)}`, { avecJeton: false });
}
