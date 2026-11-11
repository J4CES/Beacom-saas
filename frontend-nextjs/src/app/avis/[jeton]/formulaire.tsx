"use client";

import { useState } from "react";

import { Chargement, Erreur } from "@/components/etats";
import { api, useDonnees } from "@/lib/api";

export function FormulaireAvisPublic({ jeton }: { jeton: string }) {
  const etab = useDonnees<{ nom: string; categorie: string | null; ville: string | null }>(
    `/public/etablissements/${encodeURIComponent(jeton)}`,
  );
  const [note, setNote] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [merci, setMerci] = useState(false);

  async function envoyer(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (!note) return setErreur("Choisissez une note de 1 à 5 étoiles.");
    const donnees = new FormData(ev.currentTarget);
    setErreur(null);
    setEnvoi(true);
    try {
      await api(`/public/avis/${encodeURIComponent(jeton)}`, {
        method: "POST",
        json: {
          texte: donnees.get("texte"),
          note,
          auteur: donnees.get("auteur") || undefined,
          // Champ piège : invisible pour une personne, rempli par les robots.
          site_web: donnees.get("site_web") || undefined,
        },
      });
      setMerci(true);
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      {etab.chargement ? (
        <Chargement />
      ) : etab.erreur || !etab.donnees ? (
        <div className="carte text-center">
          <h1 className="mb-2 text-lg font-semibold">Lien introuvable</h1>
          <p className="text-sm text-encre-2">Ce lien n&apos;est plus valide. Demandez le nouveau QR code à l&apos;établissement.</p>
        </div>
      ) : merci ? (
        <div className="carte text-center">
          <p className="mb-2 text-4xl" aria-hidden>🙏</p>
          <h1 className="mb-1 text-lg font-semibold">Merci pour votre avis !</h1>
          <p className="text-sm text-encre-2">{etab.donnees.nom} vous remercie : votre retour aide l&apos;équipe à s&apos;améliorer.</p>
        </div>
      ) : (
        <form onSubmit={envoyer} className="carte space-y-5">
          <div>
            <p className="text-sm text-encre-2">{[etab.donnees.categorie, etab.donnees.ville].filter(Boolean).join(" · ")}</p>
            <h1 className="text-xl font-semibold">Votre avis sur {etab.donnees.nom}</h1>
          </div>
          <fieldset>
            <legend className="etiquette">Votre note</legend>
            <div className="flex gap-1" role="radiogroup">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={note === n}
                  aria-label={`${n} étoile${n > 1 ? "s" : ""}`}
                  onClick={() => setNote(n)}
                  className={`h-12 w-12 rounded-lg border text-2xl transition ${n <= note ? "border-accent bg-accent/15 text-accent" : "border-bord text-muet"}`}
                >
                  ★
                </button>
              ))}
            </div>
          </fieldset>
          <div>
            <label className="etiquette" htmlFor="texte">Qu&apos;avez-vous pensé de votre visite ?</label>
            <textarea id="texte" name="texte" className="champ min-h-32 text-base" required minLength={5} maxLength={2000} placeholder="Accueil, service, plats, ambiance…" />
          </div>
          <div>
            <label className="etiquette" htmlFor="auteur">Votre prénom (facultatif)</label>
            <input id="auteur" name="auteur" className="champ text-base" maxLength={100} autoComplete="given-name" />
          </div>
          <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
            <label htmlFor="site_web">Ne pas remplir</label>
            <input id="site_web" name="site_web" tabIndex={-1} autoComplete="off" />
          </div>
          {erreur && <Erreur message={erreur} />}
          <button className="bouton w-full py-3 text-base" disabled={envoi}>{envoi ? "Envoi…" : "Envoyer mon avis"}</button>
          <p className="text-center text-xs text-muet">Avis anonyme si vous ne donnez pas de prénom. Propulsé par Beacom.</p>
        </form>
      )}
    </main>
  );
}
