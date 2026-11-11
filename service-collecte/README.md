# service-collecte

API FastAPI qui reçoit les avis, les enregistre dans `db_collecte` (statut `nouveau`), **valide la transaction**,
puis envoie un message JSON `{avis_id, organisation_id, texte, langue}` dans la file Azure `avis-a-analyser`
(statut `en_file`). L'avis est donc toujours en base quand la Function le reçoit.
Hébergé sur Azure App Service.

## Communications

- **REST sortant** : vérifie que l'établissement existe auprès de `service-etablissements` (jeton de l'utilisateur transmis).
- **Événement sortant** : message dans la file `avis-a-analyser` (base64, format attendu par le trigger Azure Functions).
- **Entrant** : l'Azure Function appelle `PATCH /avis/{id}/statut` avec la clé interne une fois l'analyse terminée.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload --port 8002
```

## Routes

| Route | Accès |
|---|---|
| `POST /avis` | admin, gestionnaire ; 402 au-delà de 100 avis par mois en plan `gratuit` |
| `GET /avis?etablissement_id=&limit=&offset=` | tout utilisateur connecté |
| `GET /avis/{id}` | tout utilisateur connecté |
| `POST /public/avis/{jeton}` | **public** (10 dépôts / 10 min par IP) : `{texte, note, auteur?, langue?}` déposé par un client final |
| `POST /avis/import?etablissement_id=` | admin, gestionnaire : fichier CSV (multipart, champ `fichier`), tout ou rien |
| `POST /avis/renvoyer-nouveaux` | admin : renvoie en file les avis de son organisation restés `nouveau` (un commit par avis) |
| `PATCH /avis/{id}/statut` | clé interne `X-API-Key` (Azure Function) |
| `GET /health` | public |

Toutes les routes utilisateur sont limitées à l'organisation du jeton (404 pour un avis d'un autre client).
Le passage à `en_file` ne se fait que depuis `nouveau` : si la Function a déjà marqué l'avis `analyse`, il le reste.

## Dépôt public (lien et QR code)

1. `service-collecte` résout le jeton par la route interne de `service-etablissements` (clé `X-API-Key`) :
   il obtient l'établissement **et son organisation**, sans jeton utilisateur.
2. Il demande le plan de l'organisation à `service-utilisateurs` (`/interne/organisations/{id}`) pour appliquer le quota.
3. L'avis est enregistré avec `source = lien_public`, puis suit le même chemin que les autres (file, Function).

Protections : validation stricte (champs inconnus refusés, texte de 5 à 2 000 caractères, note obligatoire), limitation de
débit par IP en mémoire, champ piège `site_web` (rempli = robot : réponse 201 mais rien n'est enregistré), réponse
sans identifiant interne. Limite assumée de la limitation de débit : compteur propre à chaque instance et remis à zéro au
redémarrage ; un même Wi-Fi partage une IP (d'où 10 dépôts par 10 minutes).

## Import CSV

UTF-8 (BOM accepté), séparateur `,` ou `;`. Colonnes : `texte` (obligatoire), `note`, `auteur`, `langue`, `date_avis`, `source`.
1 Mo et 1 000 lignes au plus. **Tout ou rien** : une ligne invalide refuse le fichier (422, avec les numéros de ligne),
et un fichier qui dépasserait le quota mensuel est refusé en entier (402).

```csv
texte;note;auteur
Très bon accueil, thé parfait;5;Sara
Attente trop longue en terrasse;2;
```

Tests : `./scripts/lancer-tests.sh collecte` depuis la racine du dépôt.
