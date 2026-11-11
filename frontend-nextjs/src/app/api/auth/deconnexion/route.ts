import { NextResponse } from "next/server";

import { effacerJeton } from "@/lib/session";

export async function POST() {
  const sortie = new NextResponse(null, { status: 204 });
  effacerJeton(sortie);
  return sortie;
}
