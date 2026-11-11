import { NextRequest } from "next/server";

import { obtenirJeton } from "../jeton";

export async function POST(req: NextRequest) {
  return obtenirJeton(req, "/auth/login");
}
