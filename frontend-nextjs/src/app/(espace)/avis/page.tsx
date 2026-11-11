"use client";

import { useState } from "react";

import { Chargement, Erreur, Succes, Vide } from "@/components/etats";
import { FiltreEtablissement } from "@/components/filtre-etablissement";
import { useMoi } from "@/components/moi";
import { api, useDonnees } from "@/lib/api";
import { LIBELLES_SENTIMENT, type Analyse, type Avis, type Etablissement, type Sentiment } from "@/lib/types";

const STATUTS: Record<Avis["statut"], string> = { nouveau: "Reçu", en_file: "En analyse", analyse: "Analysé" };
const TEINTE: Record<Sentiment, string> = {
  positive: "var(--positif)",
  neutral: "var(--neutre)",
  mixed: "var(--mitige)",
  negative: "var(--negatif)",
};

function Pastille({ sentiment }: { sentiment?: Sentiment }) {
  if (!sentiment) return <span className="text-xs text-muet">—</span>;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: TEINTE[sentiment] }} aria-hidden />
      {LIBELLES_SENTIMENT[sentiment]}
    </span>
  );
}

function Saisie({ etablissements, onAjout }: { etablissements: Etablissement[]; onAjout: () => void }) {
  const [onglet, setOnglet] = useState<"manuel" | "csv">("manuel");
  const [erreur, setErreur] = useState<string | null>(null);
  const [lignes, setLignes] = useState<{ ligne: number; erreur: string }[]>([]);
  const [succes, setSucces] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function envoyer(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const formulaire = ev.currentTarget;
    const donnees = new FormData(formulaire);
    setErreur(null);
    setLignes([]);
    setSucces(null);
    setEnvoi(true);
    try {
      if (onglet === "manuel") {
        const corps = Object.fromEntries([...donnees].filter(([, v]) => v !== ""));
        await api("/collecte/avis", {
          method: "POST",
          json: { ...corps, etablissement_id: Number(corps.etablissement_id), note: corps.note ? Number(corps.note) : undefined },
        });
        setSucces("Avis enregistré : son analyse arrive dans quelques secondes.");
      } else {
        const etab = donnees.get("etablissement_id");
        const envoiCsv = new FormData();
        envoiCsv.set("fichier", donnees.get("fichier") as File);
        const r = await api<{ importes: number }>(`/collecte/avis/import?etablissement_id=${etab}`, {
          method: "POST",
          body: envoiCsv,
        });
        setSucces(`${r.importes} avis importés.`);
      }
      formulaire.reset();
      onAjout();
    } catch (err) {
      const e = err as Error & { details?: { erreurs?: { ligne: number; erreur: string }[] } };
      setErreur(e.message);
      setLignes(e.details?.erreurs ?? []);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <section className="carte space-y-4">
      <div className="flex gap-1" role="tablist">
        {(["manuel", "csv"] as const).map((o) => (
          <button key={o} role="tab" aria-selected={onglet === o} className={`bouton-discret ${onglet === o ? "bg-grille text-encre" : ""}`} onClick={() => setOnglet(o)}>
            {o === "manuel" ? "Saisir un avis" : "Importer un CSV"}
          </button>
        ))}
      </div>
      <form onSubmit={envoyer} className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="etiquette" htmlFor="etablissement_id">Établissement</label>
          <select id="etablissement_id" name="etablissement_id" className="champ" required>
            {etablissements.map((e) => (
              <option key={e.id} value={e.id}>{e.nom}</option>
            ))}
          </select>
        </div>
        {onglet === "manuel" ? (
          <>
            <div>
              <label className="etiquette" htmlFor="note">Note (facultative)</label>
              <select id="note" name="note" className="champ" defaultValue="">
                <option value="">—</option>
                {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} / 5</option>)}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="etiquette" htmlFor="texte">Avis</label>
              <textarea id="texte" name="texte" className="champ min-h-24" required maxLength={5000} />
            </div>
            <div>
              <label className="etiquette" htmlFor="auteur">Auteur (facultatif)</label>
              <input id="auteur" name="auteur" className="champ" maxLength={255} />
            </div>
            <div>
              <label className="etiquette" htmlFor="source">Source (facultative)</label>
              <input id="source" name="source" className="champ" maxLength={100} placeholder="Google, Instagram, cahier…" />
            </div>
          </>
        ) : (
          <div>
            <label className="etiquette" htmlFor="fichier">Fichier CSV</label>
            <input id="fichier" name="fichier" type="file" accept=".csv,text/csv" className="champ" required />
            <p className="mt-1 text-xs text-muet">
              Colonnes : texte (obligatoire), note, auteur, langue, date_avis, source. Séparateur « , » ou « ; ». 1 000 lignes au plus.
            </p>
          </div>
        )}
        <div className="sm:col-span-2 space-y-2">
          <button className="bouton" disabled={envoi || !etablissements.length}>{envoi ? "Envoi…" : onglet === "manuel" ? "Enregistrer" : "Importer"}</button>
          {succes && <Succes>{succes}</Succes>}
          {erreur && <Erreur message={erreur} />}
          {lignes.length > 0 && (
            <ul className="text-sm text-encre-2">
              {lignes.map((l) => <li key={l.ligne}>Ligne {l.ligne} : {l.erreur}</li>)}
            </ul>
          )}
        </div>
      </form>
    </section>
  );
}

export default function PageAvis() {
  const moi = useMoi();
  const [etab, setEtab] = useState<number | null>(null);
  const etablissements = useDonnees<Etablissement[]>("/etablissements/etablissements");
  const filtre = etab ? `&etablissement_id=${etab}` : "";
  const avis = useDonnees<Avis[]>(`/collecte/avis?limit=200${filtre}`);
  const analyses = useDonnees<Analyse[]>(`/analyses/analyses?limit=500${filtre}`);
  const sentimentDe = new Map((analyses.donnees ?? []).map((a) => [a.avis_id, a.sentiment]));
  const nomEtab = (id: number) => etablissements.donnees?.find((e) => e.id === id)?.nom ?? `n° ${id}`;
  const recharger = () => {
    avis.recharger();
    analyses.recharger();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Avis</h1>
        <div className="flex items-center gap-2">
          <FiltreEtablissement etablissements={etablissements.donnees ?? []} valeur={etab} onChange={setEtab} />
          <button className="bouton-discret" onClick={recharger}>Actualiser</button>
        </div>
      </div>

      {moi.role !== "lecteur" && etablissements.donnees && <Saisie etablissements={etablissements.donnees} onAjout={recharger} />}

      {avis.erreur ? (
        <Erreur message={avis.erreur} onReessayer={avis.recharger} />
      ) : avis.chargement ? (
        <Chargement />
      ) : avis.donnees?.length ? (
        <div className="carte overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="text-left text-muet">
              <tr>
                <th className="px-4 py-2 font-medium">Avis</th>
                <th className="px-4 py-2 font-medium">Établissement</th>
                <th className="px-4 py-2 font-medium">Note</th>
                <th className="px-4 py-2 font-medium">Sentiment</th>
                <th className="px-4 py-2 font-medium">Statut</th>
                <th className="px-4 py-2 font-medium">Reçu le</th>
              </tr>
            </thead>
            <tbody>
              {avis.donnees.map((a) => (
                <tr key={a.id} className="border-t border-grille align-top">
                  <td className="max-w-md px-4 py-2">
                    <p className="line-clamp-3">{a.texte}</p>
                    {(a.auteur || a.source) && <p className="mt-0.5 text-xs text-muet">{[a.auteur, a.source].filter(Boolean).join(" · ")}</p>}
                  </td>
                  <td className="px-4 py-2 text-encre-2">{nomEtab(a.etablissement_id)}</td>
                  <td className="px-4 py-2 tabular-nums">{a.note ? `${a.note}/5` : "—"}</td>
                  <td className="px-4 py-2"><Pastille sentiment={sentimentDe.get(a.id)} /></td>
                  <td className="px-4 py-2 text-encre-2">{STATUTS[a.statut]}</td>
                  <td className="px-4 py-2 whitespace-nowrap text-encre-2">{new Date(a.collecte_le).toLocaleDateString("fr-FR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Vide>Aucun avis pour l&apos;instant : partagez le lien ou le QR code de vos établissements.</Vide>
      )}
    </div>
  );
}
