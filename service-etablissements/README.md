# service-etablissements

API FastAPI pour gérer les établissements (base `db_etablissements`). Hébergé sur Azure App Service.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload --port 8001
```

Documentation interactive : http://localhost:8001/docs

## Routes

| Route | Accès (jeton JWT `Authorization: Bearer ...`) |
|---|---|
| `POST /etablissements` | admin, gestionnaire ; 402 si la limite du plan est atteinte |
| `GET /etablissements?ville=&limit=&offset=` | tout utilisateur connecté |
| `GET /etablissements/{id}` | tout utilisateur connecté |
| `DELETE /etablissements/{id}` | admin |
| `POST /etablissements/{id}/jeton-public` | admin : nouveau jeton, l'ancien lien et l'ancien QR code cessent de fonctionner |
| `GET /public/etablissements/{jeton}` | **public** (60 requêtes/min par IP) : `{nom, categorie, ville}` pour la page de dépôt d'avis |
| `GET /interne/etablissements/par-jeton/{jeton}` | clé interne `X-API-Key` (service-collecte) : `{id, organisation_id, nom}` |

Toutes les routes sont limitées à l'organisation du jeton : un établissement d'un autre client répond 404.
Limites : plan `gratuit` 1 établissement, `pro` 5, `entreprise` illimité (`LIMITES_PLANS` dans `auth.py`).
`source_id` est unique par organisation. Chaque établissement a un `jeton_public` de 32 caractères hexadécimaux
aléatoires (122 bits, généré par PostgreSQL) : c'est lui que contiennent le lien public et le QR code.

Tests : `./scripts/lancer-tests.sh etablissements` depuis la racine du dépôt.
| `GET /health` | public |
