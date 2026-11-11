"use client";

import { useEffect, useState } from "react";

import { Chargement, Erreur, Succes, Vide } from "@/components/etats";
import { useMoi } from "@/components/moi";
import { QrCode } from "@/components/qr-code";
import { api, useDonnees } from "@/lib/api";
import type { Etablissement, Organisation } from "@/lib/types";

function CarteEtablissement({ e, onChange }: { e: Etablissement; onChange: () => void }) {
  const moi = useMoi();
  const [origine, setOrigine] = useState("");
  const [qr, setQr] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  useEffect(() => setOrigine(window.location.origin), []);
  const lien = `${origine}/avis/${e.jeton_public}`;

  async function action(fn: () => Promise<unknown>, succes: string) {
    setErreur(null);
    try {
      await fn();
      setMessage(succes);
      onChange();
    } catch (err) {
      setErreur((err as Error).message);
    }
  }

  return (
    <li className="carte space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{e.nom}</h2>
          <p className="text-sm text-encre-2">{[e.categorie, e.ville].filter(Boolean).join(" · ") || "—"}</p>
        </div>
        <button className="bouton-discret" onClick={() => setQr((v) => !v)} aria-expanded={qr}>
          {qr ? "Masquer le QR code" : "QR code"}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg border border-bord px-3 py-1.5 text-xs text-encre-2">{lien}</code>
        <button className="bouton-discret" onClick={() => navigator.clipboard.writeText(lien).then(() => setMessage("Lien copié"))}>
          Copier le lien
        </button>
      </div>
      {qr && origine && <QrCode texte={lien} nom={e.nom} />}
      {moi.role === "admin" && (
        <div className="flex flex-wrap gap-2 border-t border-grille pt-3">
          <button
            className="bouton-discret text-xs"
            onClick={() =>
              confirm("L'ancien lien et l'ancien QR code ne fonctionneront plus. Continuer ?") &&
              action(() => api(`/etablissements/etablissements/${e.id}/jeton-public`, { method: "POST" }), "Nouveau lien créé")
            }
          >
            Régénérer le lien
          </button>
          <button
            className="bouton-discret text-xs text-critique"
            onClick={() =>
              confirm(`Supprimer « ${e.nom} » ?`) &&
              action(() => api(`/etablissements/etablissements/${e.id}`, { method: "DELETE" }), "Établissement supprimé")
            }
          >
            Supprimer
          </button>
        </div>
      )}
      {message && <Succes>{message}</Succes>}
      {erreur && <Erreur message={erreur} />}
    </li>
  );
}

export default function Etablissements() {
  const moi = useMoi();
  const liste = useDonnees<Etablissement[]>("/etablissements/etablissements");
  const org = useDonnees<Organisation>("/utilisateurs/organisations/moi");
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function creer(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const formulaire = ev.currentTarget;
    const donnees = Object.fromEntries([...new FormData(formulaire)].filter(([, v]) => v !== ""));
    setErreur(null);
    setEnvoi(true);
    try {
      await api("/etablissements/etablissements", { method: "POST", json: donnees });
      formulaire.reset();
      liste.recharger();
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setEnvoi(false);
    }
  }

  const limite = org.donnees?.limites.etablissements;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Établissements</h1>
        {org.donnees && liste.donnees && (
          <p className="text-sm text-encre-2">
            {liste.donnees.length} sur {limite ?? "∞"} avec le plan {org.donnees.plan}
          </p>
        )}
      </div>

      {moi.role !== "lecteur" && (
        <form onSubmit={creer} className="carte grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
          <div>
            <label className="etiquette" htmlFor="nom">Nom</label>
            <input id="nom" name="nom" className="champ" required maxLength={255} placeholder="Café Atlas – Maârif" />
          </div>
          <div>
            <label className="etiquette" htmlFor="categorie">Catégorie</label>
            <input id="categorie" name="categorie" className="champ" maxLength={100} placeholder="café" />
          </div>
          <div>
            <label className="etiquette" htmlFor="ville">Ville</label>
            <input id="ville" name="ville" className="champ" maxLength={100} placeholder="Casablanca" />
          </div>
          <button className="bouton" disabled={envoi}>{envoi ? "Ajout…" : "Ajouter"}</button>
          {erreur && <div className="sm:col-span-4"><Erreur message={erreur} /></div>}
        </form>
      )}

      {liste.erreur ? (
        <Erreur message={liste.erreur} onReessayer={liste.recharger} />
      ) : liste.chargement ? (
        <Chargement />
      ) : liste.donnees?.length ? (
        <ul className="grid gap-4 md:grid-cols-2">
          {liste.donnees.map((e) => (
            <CarteEtablissement key={e.id + e.jeton_public} e={e} onChange={liste.recharger} />
          ))}
        </ul>
      ) : (
        <Vide>Aucun établissement pour l&apos;instant.</Vide>
      )}
    </div>
  );
}
