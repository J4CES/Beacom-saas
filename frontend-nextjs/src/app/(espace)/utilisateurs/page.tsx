"use client";

import { useState } from "react";

import { Chargement, Erreur, Succes, Vide } from "@/components/etats";
import { useMoi } from "@/components/moi";
import { api, useDonnees } from "@/lib/api";
import type { Organisation, Plan, Role, Utilisateur } from "@/lib/types";

const ROLES: Record<Role, string> = { admin: "Administrateur", gestionnaire: "Gestionnaire", lecteur: "Lecteur" };
const PLANS: Record<Plan, string> = {
  gratuit: "Gratuit : 1 établissement, 100 avis par mois",
  pro: "Pro : jusqu'à 5 établissements",
  entreprise: "Entreprise : illimité",
};

export default function Equipe() {
  const moi = useMoi();
  const liste = useDonnees<Utilisateur[]>(moi.role === "admin" ? "/utilisateurs/utilisateurs" : null);
  const org = useDonnees<Organisation>("/utilisateurs/organisations/moi");
  const [erreur, setErreur] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (moi.role !== "admin") return <Erreur message="Cette page est réservée aux administrateurs." />;

  async function executer(fn: () => Promise<unknown>, succes: string, apres: () => void) {
    setErreur(null);
    setMessage(null);
    try {
      await fn();
      setMessage(succes);
      apres();
    } catch (err) {
      setErreur((err as Error).message);
    }
  }

  function creer(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const formulaire = ev.currentTarget;
    const donnees = Object.fromEntries([...new FormData(formulaire)].filter(([, v]) => v !== ""));
    executer(() => api("/utilisateurs/utilisateurs", { method: "POST", json: donnees }), "Compte créé", () => {
      formulaire.reset();
      liste.recharger();
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Équipe et abonnement</h1>
      {message && <Succes>{message}</Succes>}
      {erreur && <Erreur message={erreur} />}

      <section className="carte space-y-3">
        <h2 className="font-semibold">Abonnement</h2>
        {org.erreur ? (
          <Erreur message={org.erreur} onReessayer={org.recharger} />
        ) : !org.donnees ? (
          <Chargement />
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex-1">
              <span className="etiquette">Plan de {org.donnees.nom}</span>
              <select
                className="champ"
                value={org.donnees.plan}
                onChange={(e) =>
                  executer(
                    () => api("/utilisateurs/organisations/moi", { method: "PATCH", json: { plan: e.target.value } }),
                    "Plan modifié : reconnectez-vous pour l'appliquer à votre session.",
                    org.recharger,
                  )
                }
              >
                {(Object.keys(PLANS) as Plan[]).map((p) => <option key={p} value={p}>{PLANS[p]}</option>)}
              </select>
            </label>
            <p className="text-xs text-muet">Prototype : le changement de plan simule l&apos;abonnement, sans paiement.</p>
          </div>
        )}
      </section>

      <form onSubmit={creer} className="carte grid gap-3 sm:grid-cols-[2fr_2fr_1fr_auto] sm:items-end">
        <div>
          <label className="etiquette" htmlFor="email">E-mail</label>
          <input id="email" name="email" type="email" className="champ" required />
        </div>
        <div>
          <label className="etiquette" htmlFor="mot_de_passe">Mot de passe provisoire</label>
          <input id="mot_de_passe" name="mot_de_passe" type="password" className="champ" required minLength={10} autoComplete="new-password" />
        </div>
        <div>
          <label className="etiquette" htmlFor="role">Rôle</label>
          <select id="role" name="role" className="champ" defaultValue="gestionnaire">
            {(Object.keys(ROLES) as Role[]).map((r) => <option key={r} value={r}>{ROLES[r]}</option>)}
          </select>
        </div>
        <button className="bouton">Ajouter</button>
      </form>

      {liste.erreur ? (
        <Erreur message={liste.erreur} onReessayer={liste.recharger} />
      ) : liste.chargement ? (
        <Chargement />
      ) : liste.donnees?.length ? (
        <ul className="carte divide-y divide-grille p-0">
          {liste.donnees.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <div>
                <p className="font-medium">{u.email}{u.id === moi.id && <span className="ml-2 text-xs text-muet">(vous)</span>}</p>
                <p className="text-sm text-encre-2">{u.actif ? "Actif" : "Désactivé"}</p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  className="champ w-auto"
                  value={u.role}
                  disabled={u.id === moi.id}
                  aria-label={`Rôle de ${u.email}`}
                  onChange={(e) =>
                    executer(() => api(`/utilisateurs/utilisateurs/${u.id}`, { method: "PATCH", json: { role: e.target.value } }), "Rôle modifié", liste.recharger)
                  }
                >
                  {(Object.keys(ROLES) as Role[]).map((r) => <option key={r} value={r}>{ROLES[r]}</option>)}
                </select>
                {u.id !== moi.id && (
                  <button
                    className="bouton-discret"
                    onClick={() =>
                      executer(
                        () => api(`/utilisateurs/utilisateurs/${u.id}`, { method: "PATCH", json: { actif: !u.actif } }),
                        u.actif ? "Compte désactivé" : "Compte réactivé",
                        liste.recharger,
                      )
                    }
                  >
                    {u.actif ? "Désactiver" : "Réactiver"}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <Vide>Aucun compte.</Vide>
      )}
    </div>
  );
}
