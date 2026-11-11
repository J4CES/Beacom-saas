import type { NextResponse } from "next/server";

/** Cookie du jeton JWT : HttpOnly (illisible par le JavaScript de la page), Secure, SameSite=Lax. */
export const COOKIE_JETON = "beacom_jeton";

export function poserJeton(reponse: NextResponse, jeton: string, dureeSecondes: number): void {
  reponse.cookies.set(COOKIE_JETON, jeton, {
    httpOnly: true,
    // Secure partout sauf en développement local (http://localhost), où Safari refuserait le cookie.
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: dureeSecondes,
  });
}

export function effacerJeton(reponse: NextResponse): void {
  reponse.cookies.set(COOKIE_JETON, "", { httpOnly: true, path: "/", maxAge: 0 });
}
