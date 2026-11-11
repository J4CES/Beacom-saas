import type { Metadata } from "next";

import { FormulaireAuth } from "@/components/formulaire-auth";

export const metadata: Metadata = { title: "Inscription" };

export default function Inscription() {
  return <FormulaireAuth mode="inscription" suite="/etablissements" />;
}
