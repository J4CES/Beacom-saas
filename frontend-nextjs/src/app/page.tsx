import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Barre de navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center">
              <span className="text-2xl font-bold text-blue-600">Beacom</span>
              <span className="ml-2 text-sm text-gray-500">SaaS</span>
            </div>
            <div className="flex space-x-4">
              <Link href="/login" className="text-gray-600 hover:text-blue-600 px-3 py-2 rounded-md font-medium">
                Connexion
              </Link>
              <Link href="/inscription" className="bg-blue-600 text-white hover:bg-blue-700 px-4 py-2 rounded-md font-medium transition-colors">
                Créer un compte
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Section Héro */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl font-extrabold text-gray-900 tracking-tight">
            Gérez l'e-réputation de vos <span className="text-blue-600">établissements</span>
          </h1>
          <p className="mt-6 text-xl text-gray-500 max-w-2xl mx-auto">
            Collectez les avis, analysez les sentiments automatiquement et prenez les bonnes décisions grâce à notre tableau de bord intelligent.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link href="/inscription" className="bg-blue-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-blue-700 shadow-lg transition-all">
              Commencer gratuitement
            </Link>
            <Link href="/login" className="bg-white text-gray-700 border border-gray-300 px-8 py-3 rounded-lg text-lg font-semibold hover:bg-gray-50 transition-all">
              Se connecter
            </Link>
          </div>
        </div>

        {/* Section Fonctionnalités */}
        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-100">
            <div className="text-blue-600 text-3xl mb-4">📊</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Analyse de sentiment</h3>
            <p className="text-gray-500">Notre IA analyse chaque avis pour vous dire s'il est positif, négatif ou neutre.</p>
          </div>
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-100">
            <div className="text-blue-600 text-3xl mb-4">⚡</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Temps réel</h3>
            <p className="text-gray-500">Recevez les nouveaux avis instantanément grâce à notre architecture microservices.</p>
          </div>
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-100">
            <div className="text-blue-600 text-3xl mb-4">🔒</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Sécurisé</h3>
            <p className="text-gray-500">Vos données sont isolées et protégées par une authentification JWT stricte.</p>
          </div>
        </div>
      </main>
    </div>
  );
}