export function Chargement({ texte = "Chargement…" }: { texte?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-8 text-sm text-muet">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-grille border-t-accent" aria-hidden />
      {texte}
    </div>
  );
}

export function Erreur({ message, onReessayer }: { message: string; onReessayer?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-critique/40 bg-critique/10 px-4 py-3 text-sm">
      <span>
        <strong className="text-critique">Erreur : </strong>
        {message}
      </span>
      {onReessayer && (
        <button className="bouton-discret" onClick={onReessayer}>
          Réessayer
        </button>
      )}
    </div>
  );
}

export function Vide({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-sm text-muet">{children}</p>;
}

export function Succes({ children }: { children: React.ReactNode }) {
  return (
    <p role="status" className="rounded-lg border border-succes/40 bg-succes/10 px-4 py-2 text-sm text-succes">
      {children}
    </p>
  );
}
