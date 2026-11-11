import Link from "next/link";

export default function Inscription() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      {/* La carte blanche au centre */}
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 border border-slate-100">
        
        {/* En-tête */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Créer un compte</h1>
          <p className="text-slate-500 mt-2">Rejoignez Beacom et gérez votre e-réputation.</p>
        </div>

        {/* Formulaire */}
        <form className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nom de l'organisation</label>
            <input 
              type="text" 
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors outline-none"
              placeholder="Ex: Hôtel de Paris"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Adresse e-mail</label>
            <input 
              type="email" 
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors outline-none"
              placeholder="vous@exemple.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Mot de passe</label>
            <input 
              type="password" 
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors outline-none"
              placeholder="••••••••"
            />
          </div>

          <button 
            type="button"
            className="w-full bg-blue-600 text-white font-semibold py-3 rounded-lg hover:bg-blue-700 transition-colors shadow-md mt-2"
          >
            S'inscrire
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-6">
          Déjà un compte ?{" "}
          <Link href="/login" className="text-blue-600 font-medium hover:underline">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  );
}