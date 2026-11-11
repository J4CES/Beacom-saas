import "server-only";

import { NextRequest, NextResponse } from "next/server";

import { COOKIE_JETON, effacerJeton } from "./session";

/**
 * API Gateway : les routes app/api/... appellent les 4 services côté serveur.
 * Leurs URLs restent dans les variables d'environnement du serveur et ne sont jamais envoyées au navigateur.
 */
export const SERVICES = {
  utilisateurs: "UTILISATEURS_API_URL",
  etablissements: "ETABLISSEMENTS_API_URL",
  collecte: "COLLECTE_API_URL",
  analyses: "ANALYSES_API_URL",
} as const;

export type NomService = keyof typeof SERVICES;

/** Premier segment de chemin autorisé pour chaque service. Les routes /interne/... ne sont jamais relayées. */
const ROUTES_AUTORISEES: Record<NomService, string[]> = {
  utilisateurs: ["me", "organisations", "utilisateurs"],
  etablissements: ["etablissements"],
  collecte: ["avis"],
  analyses: ["analyses"],
};

export function cheminAutorise(service: string, chemin: string[]): service is NomService {
  if (!(service in ROUTES_AUTORISEES)) return false;
  if (chemin.length === 0 || chemin.some((s) => s === "interne" || s === "public" || s === ".." || s === "")) {
    return false;
  }
  return ROUTES_AUTORISEES[service as NomService].includes(chemin[0]);
}

export function urlService(service: NomService, chemin: string): string {
  const base = process.env[SERVICES[service]];
  if (!base) throw new Error(`${SERVICES[service]} n'est pas défini`);
  return base.replace(/\/$/, "") + chemin;
}

/** Une requête qui modifie des données doit venir de notre propre origine (protection CSRF, en plus de SameSite=Lax). */
export function origineValide(req: NextRequest): boolean {
  if (["GET", "HEAD"].includes(req.method)) return true;
  const origine = req.headers.get("origin");
  if (!origine) return false;
  try {
    return new URL(origine).host === (req.headers.get("x-forwarded-host") ?? req.headers.get("host"));
  } catch {
    return false;
  }
}

export function erreur(statut: number, detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: statut });
}

/**
 * Relaie la requête vers un service. Transmet le jeton du cookie (en-tête Authorization) et l'IP du client
 * (X-Forwarded-For, pour la limitation de débit : les services comptent alors 2 proxys de confiance).
 */
export async function relayer(
  req: NextRequest,
  service: NomService,
  chemin: string,
  options: { avecJeton?: boolean; corps?: BodyInit | null } = {},
): Promise<NextResponse> {
  const { avecJeton = true } = options;
  const entetes = new Headers();
  const type = req.headers.get("content-type");
  if (type) entetes.set("content-type", type);
  const xff = req.headers.get("x-forwarded-for");
  if (xff) entetes.set("x-forwarded-for", xff);
  // Corrélation : un identifiant par requête, suivi par les services, la file et la Function (voir docs/06-observabilite.md).
  const idRequete = /^[A-Za-z0-9._-]{8,64}$/.test(req.headers.get("x-request-id") ?? "")
    ? req.headers.get("x-request-id")!
    : crypto.randomUUID();
  entetes.set("x-request-id", idRequete);
  if (avecJeton) {
    const jeton = req.cookies.get(COOKIE_JETON)?.value;
    if (!jeton) return erreur(401, "Authentification requise");
    entetes.set("authorization", `Bearer ${jeton}`);
  }

  const corps =
    options.corps !== undefined ? options.corps : ["GET", "HEAD"].includes(req.method) ? null : await req.arrayBuffer();

  let reponse: Response;
  try {
    reponse = await fetch(urlService(service, chemin + req.nextUrl.search), {
      method: req.method,
      headers: entetes,
      body: corps,
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    console.error(`[${idRequete}] ${service} injoignable`);
    const indisponible = erreur(503, "Service momentanément indisponible, réessayez dans un instant");
    indisponible.headers.set("x-request-id", idRequete);
    return indisponible;
  }

  const contenu = reponse.status === 204 ? null : await reponse.arrayBuffer();
  const sortie = new NextResponse(contenu, {
    status: reponse.status,
    headers: { "content-type": reponse.headers.get("content-type") ?? "application/json" },
  });
  sortie.headers.set("x-request-id", idRequete);
  const attente = reponse.headers.get("retry-after");
  if (attente) sortie.headers.set("retry-after", attente);
  // Jeton expiré ou invalide : on l'efface, le navigateur sera renvoyé vers la connexion.
  if (reponse.status === 401 && avecJeton) effacerJeton(sortie);
  return sortie;
}
