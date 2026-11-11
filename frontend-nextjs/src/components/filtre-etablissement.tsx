"use client";

import type { Etablissement } from "@/lib/types";

export function FiltreEtablissement({
  etablissements,
  valeur,
  onChange,
}: {
  etablissements: Etablissement[];
  valeur: number | null;
  onChange: (id: number | null) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-encre-2">
      Établissement
      <select
        className="champ w-auto"
        value={valeur ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Tous</option>
        {etablissements.map((e) => (
          <option key={e.id} value={e.id}>
            {e.nom}
          </option>
        ))}
      </select>
    </label>
  );
}
