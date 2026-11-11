# function-nlp

Azure Function (Python, plan Consommation) : le traitement automatique et événementiel de la solution.

| Point demandé par le TP | Réponse |
|---|---|
| **Trigger** | Message dans la file Azure Storage `avis-a-analyser` |
| **Données d'entrée** | JSON `{avis_id, organisation_id, texte, langue}` envoyé par `service-collecte` |
| **Traitement** | Détection de langue si absente, puis analyse de sentiment (Azure AI Language) |
| **Résultat** | `POST service-analyses /analyses/interne` (organisation, sentiment, scores), puis `PATCH service-collecte /avis/{id}/statut` -> `analyse` |
| **Pourquoi serverless** | Charge irrégulière par rafales, tâche courte et sans état : on ne paie que l'exécution et la Function monte en charge toute seule |

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

`AzureWebJobsStorage`, `LANGUAGE_ENDPOINT`, `LANGUAGE_KEY`, `ANALYSES_API_URL`, `COLLECTE_API_URL`, `INTERNAL_API_KEY`.
En production, ce sont des paramètres d'application de la Function App (jamais dans le dépôt).
