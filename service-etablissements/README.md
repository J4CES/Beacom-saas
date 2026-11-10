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
| `POST /etablissements` | admin, gestionnaire |
| `GET /etablissements?ville=&limit=&offset=` | tout utilisateur connecté |
| `GET /etablissements/{id}` | tout utilisateur connecté |
| `DELETE /etablissements/{id}` | admin |
| `GET /health` | public |
