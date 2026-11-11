"use client";

import Link from "next/link";
import { useState } from "react";

import { Erreur } from "@/components/etats";
import { api } from "@/lib/api";

type Mode = "connexion" | "inscription";

/** Formulaire commun à la connexion et à l'inscription. Le jeton est posé en cookie HttpOnly par la passerelle. */
export function FormulaireAuth({ mode, suite }: { mode: Mode; suite: string }) {
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function envoyer(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const donnees = Object.fromEntries(new FormData(e.currentTarget));
    setErreur(null);
    setEnvoi(true);
    try {
      await api(`/auth/${mode}`, { method: "POST", json: donnees });
      // Seuls les chemins internes sont acceptés comme destination (pas de redirection ouverte).
      window.location.href = suite.startsWith("/") && !suite.startsWith("//") ? suite : "/tableau-de-bord";
    } catch (err) {
      setErreur((err as Error).message);
      setEnvoi(false);
    }
  }

  const inscription = mode === "inscription";
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-2xl font-semibold">Beacom</h1>
        <p className="mb-6 text-sm text-encre-2">
          {inscription
            ? "Créez l'espace de votre café ou restaurant : gratuit pour un établissement."
            : "Connectez-vous à votre espace."}
        </p>
        <form onSubmit={envoyer} className="carte space-y-4">
          {inscription && (
            <>
              <div>
                <label className="etiquette" htmlFor="organisation">Nom de votre entreprise</label>
                <input id="organisation" name="organisation" className="champ" required minLength={2} maxLength={255} placeholder="Café Atlas" />
              </div>
              <div>
                <label className="etiquette" htmlFor="nom">Votre nom</label>
                <input id="nom" name="nom" className="champ" maxLength={255} autoComplete="name" />
              </div>
            </>
          )}
          <div>
            <label className="etiquette" htmlFor="email">E-mail</label>
            <input id="email" name="email" type="email" className="champ" required autoComplete="email" />
          </div>
          <div>
            <label className="etiquette" htmlFor="mot_de_passe">Mot de passe</label>
            <input
              id="mot_de_passe"
              name="mot_de_passe"
              type="password"
              className="champ"
              required
              minLength={inscription ? 10 : 1}
              autoComplete={inscription ? "new-password" : "current-password"}
            />
            {inscription && <p className="mt-1 text-xs text-muet">10 caractères au moins.</p>}
          </div>
          {erreur && <Erreur message={erreur} />}
          <button className="bouton w-full" disabled={envoi}>
            {envoi ? "Un instant…" : inscription ? "Créer mon espace" : "Se connecter"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-encre-2">
          {inscription ? (
            <>Déjà un compte ? <Link className="text-accent underline" href="/connexion">Se connecter</Link></>
          ) : (
            <>Pas encore de compte ? <Link className="text-accent underline" href="/inscription">Créer un espace</Link></>
          )}
        </p>
      </div>
    </main>
  );
}
