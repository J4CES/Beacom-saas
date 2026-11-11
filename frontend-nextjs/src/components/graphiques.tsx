"use client";

import { useState } from "react";

import { LIBELLES_SENTIMENT, SENTIMENTS, type PointTendance, type Sentiment } from "@/lib/types";

const COULEUR: Record<Sentiment, string> = {
  positive: "var(--positif)",
  neutral: "var(--neutre)",
  mixed: "var(--mitige)",
  negative: "var(--negatif)",
};

const pourcent = (n: number, total: number) => (total ? `${Math.round((n / total) * 100)} %` : "–");

/** Légende : toujours présente (plusieurs séries) ; l'identité ne repose jamais sur la seule couleur. */
export function Legende({ valeurs }: { valeurs?: Partial<Record<Sentiment, number>> }) {
  const total = valeurs ? SENTIMENTS.reduce((s, k) => s + (valeurs[k] ?? 0), 0) : 0;
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-encre-2">
      {SENTIMENTS.map((s) => (
        <li key={s} className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: COULEUR[s] }} aria-hidden />
          {LIBELLES_SENTIMENT[s]}
          {valeurs && (
            <span className="tabular-nums text-encre">
              {valeurs[s] ?? 0} <span className="text-muet">({pourcent(valeurs[s] ?? 0, total)})</span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Répartition des sentiments : une barre à 100 %, segments séparés de 2 px, valeurs en légende. */
export function Repartition({ valeurs }: { valeurs: Partial<Record<Sentiment, number>> }) {
  const total = SENTIMENTS.reduce((s, k) => s + (valeurs[k] ?? 0), 0);
  const [survol, setSurvol] = useState<Sentiment | null>(null);
  if (!total) return null;
  const presents = SENTIMENTS.filter((s) => valeurs[s]);
  return (
    <div className="space-y-3">
      <div className="relative">
        <div className="flex h-4 gap-[2px]" role="img" aria-label={presents.map((s) => `${LIBELLES_SENTIMENT[s]} ${valeurs[s]}`).join(", ")}>
          {presents.map((s, i) => (
            <div
              key={s}
              onMouseEnter={() => setSurvol(s)}
              onMouseLeave={() => setSurvol(null)}
              className={`${i === 0 ? "rounded-l" : ""} ${i === presents.length - 1 ? "rounded-r" : ""} transition-opacity`}
              style={{
                width: `${((valeurs[s] ?? 0) / total) * 100}%`,
                background: COULEUR[s],
                opacity: survol && survol !== s ? 0.45 : 1,
              }}
            />
          ))}
        </div>
        {survol && (
          <div className="pointer-events-none absolute -top-9 left-0 rounded-md border border-bord bg-surface px-2 py-1 text-xs shadow-sm">
            {LIBELLES_SENTIMENT[survol]} : <span className="tabular-nums">{valeurs[survol]}</span> ({pourcent(valeurs[survol] ?? 0, total)})
          </div>
        )}
      </div>
      <Legende valeurs={valeurs} />
    </div>
  );
}

function formatPeriode(iso: string, periode: "jour" | "semaine") {
  const d = new Date(iso + "T00:00:00");
  const court = d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  return periode === "semaine" ? `sem. du ${court}` : court;
}

/** Évolution par période : barres empilées, infobulle au survol, vue tableau à la demande. */
export function Tendance({ points, periode }: { points: PointTendance[]; periode: "jour" | "semaine" }) {
  const [survol, setSurvol] = useState<number | null>(null);
  const [tableau, setTableau] = useState(false);
  const max = Math.max(1, ...points.map((p) => p.total));
  const hauteur = 180;
  const graduations = [0, Math.ceil(max / 2), max];
  const pasEtiquette = Math.max(1, Math.ceil(points.length / 8));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Legende />
        <button className="bouton-discret text-xs" onClick={() => setTableau((t) => !t)} aria-pressed={tableau}>
          {tableau ? "Voir le graphique" : "Voir le tableau"}
        </button>
      </div>

      {tableau ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-left text-muet">
              <tr>
                <th className="py-1 pr-4 font-medium">Période</th>
                {SENTIMENTS.map((s) => (
                  <th key={s} className="py-1 pr-4 font-medium">{LIBELLES_SENTIMENT[s]}</th>
                ))}
                <th className="py-1 font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.periode} className="border-t border-grille">
                  <td className="py-1 pr-4">{formatPeriode(p.periode, periode)}</td>
                  {SENTIMENTS.map((s) => (
                    <td key={s} className="py-1 pr-4">{p[s]}</td>
                  ))}
                  <td className="py-1 font-medium">{p.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <div className="flex">
            {/* Axe vertical : graduations discrètes */}
            <div className="relative mr-2 w-6 text-right text-xs text-muet tabular-nums" style={{ height: hauteur }}>
              {graduations.map((g) => (
                <span key={g} className="absolute right-0 -translate-y-1/2" style={{ top: hauteur - (g / max) * hauteur }}>
                  {g}
                </span>
              ))}
            </div>
            <div className="relative flex-1">
              {graduations.map((g) => (
                <div key={g} className="absolute inset-x-0 border-t border-grille" style={{ top: hauteur - (g / max) * hauteur }} />
              ))}
              <div className="relative flex items-end gap-1" style={{ height: hauteur }}>
                {points.map((p, i) => (
                  <div
                    key={p.periode}
                    className="flex h-full flex-1 cursor-default flex-col-reverse"
                    onMouseEnter={() => setSurvol(i)}
                    onMouseLeave={() => setSurvol(null)}
                    aria-label={`${formatPeriode(p.periode, periode)} : ${p.total} avis`}
                  >
                    <div
                      className="mx-auto flex w-full max-w-10 flex-col-reverse gap-[2px] transition-opacity"
                      style={{ height: `${(p.total / max) * 100}%`, opacity: survol !== null && survol !== i ? 0.5 : 1 }}
                    >
                      {SENTIMENTS.filter((s) => p[s]).map((s, j, liste) => (
                        <div
                          key={s}
                          className={j === liste.length - 1 ? "rounded-t" : ""}
                          style={{ flexGrow: p[s], flexBasis: 0, background: COULEUR[s] }}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-1 flex gap-1 text-xs text-muet">
                {points.map((p, i) => (
                  <span key={p.periode} className="flex-1 truncate text-center">
                    {i % pasEtiquette === 0 ? formatPeriode(p.periode, periode) : ""}
                  </span>
                ))}
              </div>
              {survol !== null && (
                <div
                  className="pointer-events-none absolute top-0 z-10 min-w-40 rounded-md border border-bord bg-surface px-3 py-2 text-xs shadow-md"
                  style={{
                    left: `${((survol + 0.5) / points.length) * 100}%`,
                    transform: survol > points.length / 2 ? "translateX(-105%)" : "translateX(5%)",
                  }}
                >
                  <p className="mb-1 font-medium">{formatPeriode(points[survol].periode, periode)}</p>
                  {SENTIMENTS.map((s) => (
                    <p key={s} className="flex items-center justify-between gap-4">
                      <span className="flex items-center gap-1.5 text-encre-2">
                        <span className="h-2 w-2 rounded-sm" style={{ background: COULEUR[s] }} aria-hidden />
                        {LIBELLES_SENTIMENT[s]}
                      </span>
                      <span className="tabular-nums">{points[survol][s]}</span>
                    </p>
                  ))}
                  <p className="mt-1 flex justify-between border-t border-grille pt-1 font-medium">
                    <span>Total</span>
                    <span className="tabular-nums">{points[survol].total}</span>
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Thèmes : une seule série (les avis négatifs), barres horizontales avec la valeur en clair. */
export function Themes({ themes }: { themes: { mot_cle: string; total: number }[] }) {
  const max = Math.max(1, ...themes.map((t) => t.total));
  return (
    <ul className="space-y-2">
      {themes.map((t) => (
        <li key={t.mot_cle} className="grid grid-cols-[minmax(6rem,10rem)_1fr_2rem] items-center gap-3 text-sm">
          <span className="truncate text-encre-2" title={t.mot_cle}>{t.mot_cle}</span>
          <span className="h-2.5 rounded-r" style={{ width: `${(t.total / max) * 100}%`, background: "var(--negatif)" }} title={`${t.total} avis`} />
          <span className="text-right tabular-nums">{t.total}</span>
        </li>
      ))}
    </ul>
  );
}
