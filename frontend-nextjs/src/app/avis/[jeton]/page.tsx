import type { Metadata } from "next";

import { FormulaireAvisPublic } from "./formulaire";

export const metadata: Metadata = { title: "Votre avis", robots: { index: false, follow: false } };

/** Page publique, ouverte depuis le QR code posé sur la table : aucun compte nécessaire. */
export default async function AvisPublic({ params }: { params: Promise<{ jeton: string }> }) {
  const { jeton } = await params;
  return <FormulaireAvisPublic jeton={jeton} />;
}
