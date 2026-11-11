import { NextRequest, NextResponse } from "next/server";

import { COOKIE_JETON } from "@/lib/session";

/** Pages de l'espace client : sans cookie de session, on renvoie vers la connexion. */
export function middleware(req: NextRequest) {
  if (!req.cookies.get(COOKIE_JETON)) {
    const url = new URL("/connexion", req.url);
    url.searchParams.set("suite", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

// La page publique /avis/<jeton> n'est pas protégée : seul /avis (la liste) l'est.
export const config = { matcher: ["/tableau-de-bord", "/etablissements", "/avis", "/utilisateurs"] };
