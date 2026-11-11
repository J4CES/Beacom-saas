"use client";

import Link from "next/link";
import { useState } from "react";

import { Chargement, Erreur, Vide } from "@/components/etats";
import { FiltreEtablissement } from "@/components/filtre-etablissement";
import { Repartition, Tendance, Themes } from "@/components/graphiques";
import { useMoi } from "@/components/moi";
import { api, useDonnees } from "@/lib/api";
import type { Alerte, Etablissement, PointTendance, Sentiment } from "@/lib/types";

function Section({ titre, children, action }: { titre: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="carte">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{titre}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Indicateur({ libelle, valeur, detail }: { libelle: string; valeur: string; detail?: string }) {
  return (
    <div className="carte">
      <p className="text-sm text-encre-2">{libelle}</p>
      <p className="mt-1 text-3xl font-semibold">{valeur}</p>
      {detail && <p className="mt-1 text-xs text-muet">{detail}</p>}
    </div>
  );
}

export default function TableauDeBord() {
  const moi = useMoi();
  const [etab, setEtab] = useState<number | null>(null);
  const [periode, setPeriode] = useState<"jour" | "semaine">("semaine");
  const filtre = etab ? `etablissement_id=${etab}` : "";
  const avec = (base: string, ...params: string[]) => {
    const q = [...params, filtre].filter(Boolean).join("&");
    return q ? `${base}?${q}` : base;
  };

  const etablissements = useDonnees<Etablissement[]>("/etablissements/etablissements");
  const resume = useDonnees<{ sentiment: Sentiment; total: number }[]>(avec("/analyses/analyses/resume"));
  const tendance = useDonnees<PointTendance[]>(
    avec("/analyses/analyses/tendance", `periode=${periode}`, `depuis_jours=${periode === "jour" ? 30 : 90}`),
  );
  const themes = useDonnees<{ mot_cle: string; total: number }[]>(avec("/analyses/analyses/themes", "sentiment=negative"));
  const alertes = useDonnees<Alerte[]>(avec("/analyses/analyses/alertes"));

  const valeurs = Object.fromEntries((resume.donnees ?? []).map((r) => [r.sentiment, r.total])) as Partial<Record<Sentiment, number>>;
  const total = Object.values(valeurs).reduce((s, n) => s + (n ?? 0), 0);
  const part = (s: Sentiment) => (total ? `${Math.round(((valeurs[s] ?? 0) / total) * 100)} %` : "–");
  const nomEtab = (id: number | null) => etablissements.donnees?.find((e) => e.id === id)?.nom ?? "Établissement";

  async function traiter(id: number) {
    await api(`/analyses/analyses/alertes/${id}`, { method: "PATCH", json: { traitee: true } });
    alertes.recharger();
  }

  if (etablissements.donnees?.length === 0) {
    return (
      <div className="carte text-center">
        <h1 className="mb-2 text-xl font-semibold">Bienvenue sur Beacom</h1>
        <p className="mb-4 text-sm text-encre-2">Ajoutez votre premier établissement pour commencer à recevoir des avis.</p>
        <Link className="bouton" href="/etablissements">Ajouter un établissement</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Tableau de bord</h1>
        <FiltreEtablissement etablissements={etablissements.donnees ?? []} valeur={etab} onChange={setEtab} />
      </div>

      {resume.erreur ? (
        <Erreur message={resume.erreur} onReessayer={resume.recharger} />
      ) : resume.chargement ? (
        <Chargement />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Indicateur libelle="Avis analysés" valeur={String(total)} />
            <Indicateur libelle="Positifs" valeur={part("positive")} detail={`${valeurs.positive ?? 0} avis`} />
            <Indicateur libelle="Négatifs" valeur={part("negative")} detail={`${valeurs.negative ?? 0} avis`} />
          </div>
          <Section titre="Répartition des sentiments">
            {total ? <Repartition valeurs={valeurs} /> : <Vide>Aucun avis analysé pour l&apos;instant.</Vide>}
          </Section>
        </>
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Section
          titre="Évolution"
          action={
            <div className="flex gap-1" role="group" aria-label="Période">
              {(["semaine", "jour"] as const).map((p) => (
                <button key={p} className={`bouton-discret text-xs ${periode === p ? "bg-grille text-encre" : ""}`} aria-pressed={periode === p} onClick={() => setPeriode(p)}>
                  {p === "semaine" ? "Par semaine (90 j)" : "Par jour (30 j)"}
                </button>
              ))}
            </div>
          }
        >
          {tendance.erreur ? (
            <Erreur message={tendance.erreur} onReessayer={tendance.recharger} />
          ) : tendance.chargement ? (
            <Chargement />
          ) : tendance.donnees?.length ? (
            <Tendance points={tendance.donnees} periode={periode} />
          ) : (
            <Vide>Pas encore assez d&apos;avis sur la période.</Vide>
          )}
        </Section>

        <Section titre="Ce qui revient dans les avis négatifs">
          {themes.erreur ? (
            <Erreur message={themes.erreur} onReessayer={themes.recharger} />
          ) : themes.chargement ? (
            <Chargement />
          ) : themes.donnees?.length ? (
            <Themes themes={themes.donnees} />
          ) : (
            <Vide>Aucun thème négatif : bonne nouvelle.</Vide>
          )}
        </Section>
      </div>

      <Section titre={`Alertes à traiter${alertes.donnees?.length ? ` (${alertes.donnees.length})` : ""}`}>
        {alertes.erreur ? (
          <Erreur message={alertes.erreur} onReessayer={alertes.recharger} />
        ) : alertes.chargement ? (
          <Chargement />
        ) : alertes.donnees?.length ? (
          <ul className="divide-y divide-grille">
            {alertes.donnees.map((a) => (
              <li key={a.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm">
                    <span className="mr-2 inline-flex items-center gap-1 rounded-full bg-critique/15 px-2 py-0.5 text-xs font-medium text-critique">
                      <span aria-hidden>⚠</span> Très négatif · {Math.round(a.score_negatif * 100)} %
                    </span>
                    <span className="text-encre-2">{nomEtab(a.etablissement_id)} · {new Date(a.creee_le).toLocaleString("fr-FR")}</span>
                  </p>
                  <p className="mt-1 text-sm">« {a.extrait} »</p>
                </div>
                {moi.role !== "lecteur" && (
                  <button className="bouton-discret" onClick={() => traiter(a.id)}>Marquer comme traitée</button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Vide>Aucune alerte en attente.</Vide>
        )}
      </Section>
    </div>
  );
}
