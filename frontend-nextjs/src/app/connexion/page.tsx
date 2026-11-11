import type { Metadata } from "next";

import { FormulaireAuth } from "@/components/formulaire-auth";

export const metadata: Metadata = { title: "Connexion" };

export default async function Connexion({ searchParams }: { searchParams: Promise<{ suite?: string }> }) {
  const { suite } = await searchParams;
  return <FormulaireAuth mode="connexion" suite={suite ?? "/tableau-de-bord"} />;
}
