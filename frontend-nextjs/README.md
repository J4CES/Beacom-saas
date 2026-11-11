# frontend-nextjs

Interface web de Beacom (Next.js 15, App Router, TypeScript, Tailwind CSS 4). Elle joue aussi le rôle d'**API Gateway** :
ses routes serveur `src/app/api/...` appellent les quatre services, dont les URLs ne sont jamais envoyées au navigateur.
Hébergée sur Azure App Service (Node 20), en mode `output: "standalone"`.

## Écrans

| Page | Accès | Contenu |
|---|---|---|
| `/inscription`, `/connexion` | public | Création de l'organisation et de son admin ; connexion |
| `/tableau-de-bord` | connecté | Répartition des sentiments, évolution par jour ou par semaine, thèmes des avis négatifs, alertes à traiter ; filtre par établissement |
| `/etablissements` | connecté | Liste, création (limite du plan affichée), lien public, QR code téléchargeable, régénération du lien (admin) |
| `/avis` | connecté | Liste avec statut et sentiment, saisie manuelle, import CSV (erreurs ligne par ligne) |
| `/utilisateurs` | admin | Comptes de l'équipe (rôle, désactivation) et plan de l'abonnement |
| `/avis/<jeton>` | **public** | Page mobile ouverte depuis le QR code : note de 1 à 5 étoiles et commentaire, sans compte |

Chaque écran gère ses états de chargement, d'erreur (avec « Réessayer ») et de liste vide.

## Passerelle (API Gateway)

| Route | Rôle |
|---|---|
| `POST /api/auth/inscription`, `POST /api/auth/connexion` | Relaient vers `service-utilisateurs` ; le jeton part dans un cookie, jamais dans le JSON |
| `POST /api/auth/deconnexion` | Efface le cookie |
| `/api/<service>/<chemin>` | Relais authentifié vers `utilisateurs`, `etablissements`, `collecte` ou `analyses` |
| `GET /api/public/etablissements/<jeton>`, `POST /api/public/avis/<jeton>` | Relais public de la page de dépôt d'avis |

Sécurité :

- **Cookie** `beacom_jeton` : `HttpOnly` (illisible par le JavaScript de la page), `Secure` en production, `SameSite=Lax`,
  durée de vie égale à celle du jeton. Une réponse 401 d'un service efface le cookie, et le navigateur est renvoyé vers
  `/connexion` ; le `middleware` y renvoie aussi les pages de l'espace client sans session.
- **Liste blanche** : seul le premier segment attendu pour chaque service est relayé (`me`, `organisations`, `utilisateurs`,
  `etablissements`, `avis`, `analyses`). Tout chemin contenant `interne` ou `public` répond 404 : les routes internes ne sont
  jamais joignables depuis le navigateur.
- **CSRF** : en plus de `SameSite=Lax`, toute requête qui modifie des données doit porter un en-tête `Origin` égal à l'hôte.
- **IP client** : `X-Forwarded-For` est transmis aux services, qui comptent alors `PROXIES_DE_CONFIANCE=2` (frontal App
  Service du frontend + passerelle) pour la limitation de débit.
- En-têtes `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`.
- Le QR code est généré dans le navigateur : aucun service tiers ne voit le lien public.

## Variables

Voir `.env.example` : `UTILISATEURS_API_URL`, `ETABLISSEMENTS_API_URL`, `COLLECTE_API_URL`, `ANALYSES_API_URL`.
Elles ne sont lues que côté serveur (aucune n'est préfixée `NEXT_PUBLIC_`). Sur Azure, ce sont des paramètres
d'application de `app-beacom-frontend` (voir `docs/05-deploiement.md`).

## Lancer en local (sans rien installer : Docker)

```bash
cd frontend-nextjs
cp .env.example .env.local   # URLs des services lancés en local
docker run --rm -it -p 3000:3000 -v "$PWD":/app -v beacom-node-modules:/app/node_modules -w /app \
  --add-host=host.docker.internal:host-gateway node:20-alpine sh -c "npm ci && npm run dev -- -H 0.0.0.0"
```

Depuis le conteneur, les services lancés sur la machine sont joignables à `http://host.docker.internal:<port>` :
adaptez `.env.local` en conséquence. Avec Node 20 installé localement : `npm ci && npm run dev`.

## Contrôles

```bash
npm run lint        # ESLint (règles Next.js et TypeScript)
npm run typecheck   # tsc --noEmit
npm run build       # build de production (.next/standalone)
```

La CI lance les trois sur chaque pull request (`.github/workflows/deploy.yml`).

## Dépendances et vulnérabilités connues

- `postcss` est forcé en `^8.5.23` (`overrides` du `package.json`) : la version embarquée par Next 15 était concernée par
  4 alertes (GHSA-qx2v-qp2m-jg93, GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849). La correction proposée
  par `npm audit` était le passage à Next 16, une version majeure ; la surcharge corrige sans changer de version de Next.
- **`npm audit --omit=dev` : 0 vulnérabilité** dans les dépendances de production (relevé du 11 novembre 2026).
- **6 alertes modérées restent dans les outils de développement** : `minimatch` (déni de service par amplification de motifs
  glob), tiré par `@typescript-eslint/*` via `eslint-config-next`. Elles ne concernent que l'analyse du code par ESLint
  sur nos propres fichiers : rien n'est livré en production ni exposé à une entrée extérieure. Elles disparaîtront avec une
  mise à jour d'`eslint-config-next` ; à revérifier avec `npm audit` à chaque mise à jour des dépendances.

## Déploiement

Le workflow construit l'application (`npm ci`, lint, types, build), assemble le paquet autonome
(`.next/standalone` + `.next/static` + `public`) et le publie sur `app-beacom-frontend`, dont la commande de démarrage
est `node server.js`. Voir `docs/05-deploiement.md`.
