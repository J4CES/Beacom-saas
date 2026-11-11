# function-nlp

Azure Functions (Python, plan Consommation) : le traitement automatique et événementiel de la solution.

### `analyser_avis` : analyse de chaque avis

| Point demandé par le TP | Réponse |
|---|---|
| **Trigger** | Message dans la file Azure Storage `avis-a-analyser` |
| **Données d'entrée** | JSON `{avis_id, organisation_id, etablissement_id, texte, langue, date_avis}` envoyé par `service-collecte` |
| **Traitement** | Détection de langue si absente, analyse de sentiment et extraction des mots-clés (Azure AI Language). Si l'avis est négatif avec un score négatif ≥ `SEUIL_ALERTE` (0,8 par défaut) : alerte |
| **Résultat** | `POST service-analyses /analyses/interne` (sentiment, scores, mots-clés) ; en cas d'alerte, `POST /analyses/interne/alertes` puis e-mail aux admins de l'organisation (Azure Communication Services, sinon simple journal) ; enfin `PATCH service-collecte /avis/{id}/statut` -> `analyse` |
| **Pourquoi serverless** | Charge irrégulière par rafales (le midi, le soir, après un import), tâche courte et sans état : on ne paie que l'exécution et la Function monte en charge toute seule |

### Alertes et e-mails

- Une alerte au plus par avis : `service-analyses` répond `creee: false` pour un message rejoué, et aucun second e-mail ne part.
- Destinataires : les admins actifs de l'organisation (`GET service-utilisateurs /interne/organisations/{id}/admins`).
- Sans `ACS_CONNECTION_STRING` / `ACS_EXPEDITEUR`, l'alerte est enregistrée et journalisée, sans e-mail.
- Un échec d'e-mail est journalisé sans relancer le message : l'alerte reste visible au tableau de bord.
- Un échec de l'extraction des mots-clés n'empêche pas l'analyse : l'avis est enregistré sans mots-clés.

## Propriété des données

La Function **n'accède à aucune base**. Elle passe par les API des services propriétaires, authentifiée par une clé interne
(`X-API-Key`). Conséquence pratique : elle n'a pas besoin de joindre le port 5432 de la VM.

## Fiabilité

- Appels idempotents (`ON CONFLICT (avis_id)`) : rejouer un message est sans danger.
- En cas d'erreur, le message est réessayé 5 fois (`maxDequeueCount`), puis part dans `avis-a-analyser-poison`.
- Le niveau F0 d'Azure AI Language est limité en volume : gardez un `batchSize` modeste.

Un message sans `organisation_id` (antérieur au multi-clients) est refusé : il part en poison queue au bout de 5 essais.

## Tests

`./scripts/lancer-tests.sh function` depuis la racine du dépôt : Azure AI Language et les API sont simulés.

## Lancer en local

Prérequis : Azure Functions Core Tools v4 et Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.example local.settings.json   # puis éditer (fichier ignoré par Git)
func start
```

## Variables

| Variable | Rôle |
|---|---|
| `AzureWebJobsStorage` | Compte de stockage de la Function et de la file |
| `LANGUAGE_ENDPOINT`, `LANGUAGE_KEY` | Azure AI Language |
| `ANALYSES_API_URL`, `COLLECTE_API_URL`, `UTILISATEURS_API_URL` | API des services |
| `INTERNAL_API_KEY` | Clé interne partagée avec les services |
| `SEUIL_ALERTE` | Score négatif déclenchant une alerte (0,8 par défaut) |
| `ACS_CONNECTION_STRING`, `ACS_EXPEDITEUR` | Facultatifs : e-mails par Azure Communication Services |
| `FRONTEND_URL` | Facultatif : lien vers le tableau de bord dans les e-mails |
En production, ce sont des paramètres d'application de la Function App (jamais dans le dépôt).
