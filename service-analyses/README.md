# service-analyses

API FastAPI sur `db_analyses`. Seul propriétaire de cette base : l'Azure Function lui envoie ses résultats
par API, elle n'écrit jamais directement en base. Hébergé sur Azure App Service.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload --port 8003
```

## Routes

| Route | Accès |
|---|---|
| `POST /analyses/interne` | clé interne `X-API-Key` (Azure Function), idempotente ; `organisation_id` obligatoire |
| `GET /analyses?sentiment=&limit=&offset=` | tout utilisateur connecté |
| `GET /analyses/avis/{avis_id}` | tout utilisateur connecté |
| `GET /analyses/resume` | tout utilisateur connecté : nombre d'avis par sentiment (tableau de bord) |
| `GET /health` | public |

Les routes de lecture ne renvoient que les analyses de l'organisation du jeton (404 pour celle d'un autre client).

Tests : `./scripts/lancer-tests.sh analyses` depuis la racine du dépôt.
