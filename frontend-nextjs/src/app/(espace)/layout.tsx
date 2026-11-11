"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Chargement, Erreur } from "@/components/etats";
import { ContexteMoi } from "@/components/moi";
import { api, useDonnees } from "@/lib/api";
import type { Moi } from "@/lib/types";

const LIENS = [
  { href: "/tableau-de-bord", libelle: "Tableau de bord" },
  { href: "/etablissements", libelle: "Établissements" },
  { href: "/avis", libelle: "Avis" },
  { href: "/utilisateurs", libelle: "Équipe", admin: true },
];

export default function EspaceLayout({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const { donnees: moi, erreur, recharger } = useDonnees<Moi>("/utilisateurs/me");

  async function deconnecter() {
    await api("/auth/deconnexion", { method: "POST" }).catch(() => null);
    window.location.href = "/connexion";
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-bord bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href="/tableau-de-bord" className="text-lg font-semibold">
            Beacom
          </Link>
          <nav className="flex flex-1 flex-wrap gap-1 text-sm" aria-label="Navigation principale">
            {LIENS.filter((l) => !l.admin || moi?.role === "admin").map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={chemin === l.href ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 ${chemin === l.href ? "bg-grille font-medium text-encre" : "text-encre-2 hover:bg-grille/60"}`}
              >
                {l.libelle}
              </Link>
            ))}
          </nav>
          {moi && (
            <div className="flex items-center gap-3 text-sm text-encre-2">
              <span className="hidden sm:inline">{moi.email}</span>
              <span className="rounded-full border border-bord px-2 py-0.5 text-xs">Plan {moi.plan}</span>
              <button className="bouton-discret" onClick={deconnecter}>
                Se déconnecter
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        {erreur ? (
          <Erreur message={erreur} onReessayer={recharger} />
        ) : !moi ? (
          <Chargement />
        ) : (
          <ContexteMoi.Provider value={moi}>{children}</ContexteMoi.Provider>
        )}
      </main>
    </div>
  );
}
