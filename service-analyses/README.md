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
| `POST /analyses/interne` | clé interne (Function) : analyse + mots-clés, idempotente ; `organisation_id` et `etablissement_id` obligatoires |
| `POST /analyses/interne/alertes` | clé interne (Function) : une alerte au plus par avis ; renvoie `creee` (false si elle existait) |
| `GET /analyses?sentiment=&etablissement_id=&limit=&offset=` | tout utilisateur connecté |
| `GET /analyses/avis/{avis_id}` | tout utilisateur connecté : analyse et mots-clés |
| `GET /analyses/resume?etablissement_id=` | tout utilisateur connecté : nombre d'avis par sentiment |
| `GET /analyses/tendance?periode=jour\|semaine&depuis_jours=90&etablissement_id=` | tout utilisateur connecté : une ligne par période avec `positive`, `neutral`, `negative`, `mixed`, `total` |
| `GET /analyses/themes?sentiment=negative&etablissement_id=&limit=10` | tout utilisateur connecté : mots-clés les plus fréquents |
| `GET /analyses/alertes?traitee=false&etablissement_id=` | tout utilisateur connecté |
| `PATCH /analyses/alertes/{id}` | admin, gestionnaire : `{traitee: true}` |
| `GET /health` | public |

Les routes de lecture ne renvoient que les analyses de l'organisation du jeton (404 pour celle d'un autre client).

Tables : `analyses_sentiment`, `mots_cles` (normalisés en minuscules, remplacés si le message est rejoué) et `alertes`.
La tendance date un avis par sa `date_avis` si elle est connue (import CSV), sinon par la date d'analyse.
Les analyses antérieures à la migration 003 n'ont pas d'établissement : elles comptent dans les totaux, pas dans les filtres.

Tests : `./scripts/lancer-tests.sh analyses` depuis la racine du dépôt.
