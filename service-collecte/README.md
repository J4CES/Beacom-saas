# service-collecte

API FastAPI qui reçoit les avis, les enregistre dans `db_collecte` (statut `nouveau`), puis envoie un message
JSON `{avis_id, texte, langue}` dans la file Azure `avis-a-analyser` (statut `en_file`).
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
| `POST /avis` | admin, gestionnaire |
| `GET /avis?etablissement_id=&limit=&offset=` | tout utilisateur connecté |
| `POST /avis/renvoyer-nouveaux` | admin : renvoie en file les avis restés `nouveau` |
| `PATCH /avis/{id}/statut` | clé interne `X-API-Key` (Azure Function) |
| `GET /health` | public |
