# 6. Observabilité

Outils : **Application Insights** (télémétrie des 4 API, du frontend et de la Function), adossé à un espace **Log Analytics**
(requêtes KQL), et **Azure Monitor** (tests de disponibilité, alertes, budget). Les commandes de création sont dans
`05-deploiement.md` (§ 7).

## Ce qui est en place dans le code

| Élément | Où | Détail |
|---|---|---|
| Télémétrie Application Insights | `auth.py` (4 services) | `azure-monitor-opentelemetry`, activé **seulement si** `APPLICATIONINSIGHTS_CONNECTION_STRING` est défini : requêtes HTTP (durée, code), dépendances sortantes, exceptions, journaux. Nom du rôle = nom du service |
| Télémétrie de la Function | hôte Azure Functions | Activée par le même paramètre sur la Function App : exécutions, durées, échecs, journaux ; échantillonnage qui garde toujours les requêtes et les exceptions (`host.json`) |
| Identifiant de corrélation | passerelle, `auth.py`, file, Function | `X-Request-ID` créé par la passerelle Next.js (ou par le service s'il manque), renvoyé dans chaque réponse, écrit dans chaque ligne de journal (`[request_id]`), transmis aux appels entre services, placé dans le message de file (`request_id`), puis renvoyé par la Function aux services qu'elle appelle |
| Journal d'accès | `auth.py` | Méthode, chemin, code, durée, IP client, identifiant de corrélation |
| `/health` | chaque service | Réponse immédiate, sans dépendance : utilisée par la CI et le test de disponibilité |
| `/health/db` | chaque service | Connexion à sa base et `SELECT 1` en 3 s maximum : 200 avec la durée, ou 503 |

Une requête se suit donc de bout en bout : navigateur -> passerelle -> `service-collecte` -> file -> Function ->
`service-analyses` / `service-collecte`, avec le même identifiant.

## Journaux applicatifs et suivi des erreurs

- Les journaux des services (sortie standard) arrivent dans Application Insights (`traces`) quand la chaîne de connexion
  est définie ; sinon ils restent consultables par le *Log stream* d'App Service.
- Les exceptions non gérées sont dans `exceptions`, reliées à la requête (`operation_Id`) qui les a provoquées.
- Les échecs de la Function (un message réessayé) sont dans `requests` (`success == false`) et `exceptions` ; après
  5 tentatives, le message part dans la file `avis-a-analyser-poison`.
- Rétention : 30 jours dans Log Analytics (coût maîtrisé, voir `04-finops.md`).

## Disponibilité

- **Test de disponibilité standard** sur `GET /health` de chacune des 4 API et sur `/connexion` du frontend : toutes les
  5 minutes, depuis 2 emplacements (France Central, Europe de l'Ouest), réponse 200 attendue en moins de 30 s.
- `/health` ne touche pas la base : il dit si l'application tourne. `/health/db` dit si elle joint sa base ; on
  l'appelle pendant un diagnostic, et on peut l'ajouter comme second test si le budget le permet.
- Indicateur suivi : pourcentage de disponibilité sur 24 h et sur 30 jours (onglet *Disponibilité*).

## Performance

| Indicateur | Source | Lecture |
|---|---|---|
| Latence des API (médiane, p95) par route | `requests` | p95 habituel attendu sous 300 ms ; une route lente pointe souvent vers la base |
| Durée des appels entre services | `dependencies` | l'appel collecte -> établissements est synchrone : il pèse sur `POST /avis` |
| Durée de la Function | `requests` (rôle `func-beacom-nlp`) | quelques centaines de ms, dominées par Azure AI Language |
| Longueur de la file | métrique `QueueMessageCount` du compte de stockage, ou `az storage message peek` | une file qui grossit = Function en panne ou quota F0 d'AI Language atteint |
| Poison queue | file `avis-a-analyser-poison` | doit rester vide |
| CPU et mémoire du plan App Service | métriques du plan | 5 applications sur un B1 (1,75 Go) |

## Stratégie d'alerte

Les 4 alertes envoient un e-mail au groupe d'actions `ag-beacom` (l'équipe).

| # | Alerte | Condition et seuil | Gravité | Pourquoi |
|---|---|---|---|---|
| 1 | Service indisponible | Le test de disponibilité de `/health` échoue **2 fois de suite** (2 échecs sur une fenêtre de 10 min pour un test toutes les 5 min) | 1 (critique) | Un échec isolé peut être un aléa réseau ; deux de suite signalent une vraie panne |
| 2 | Erreurs serveur | **Plus de 5 % de réponses 5xx sur 10 minutes** (sur au moins 20 requêtes, pour ne pas alerter sur 1 erreur sur 3 requêtes) | 2 | Base injoignable, bug, service dépendant en panne |
| 3 | Messages en échec | **Au moins 1 message** déplacé dans la poison queue `avis-a-analyser-poison` | 2 | Un avis ne sera jamais analysé sans intervention |
| 4 | Budget | **80 % du budget mensuel** atteint (coût réel), budget du groupe de ressources | 3 | Réagir avant le dépassement (voir `04-finops.md`) |

## Procédure de diagnostic, pas à pas

1. **Identifier le périmètre.** Quel test ou quelle alerte s'est déclenché ? Ouvrir la *cartographie d'application*
   d'Application Insights : le service en rouge et la flèche (dépendance) en échec désignent le maillon fautif.
2. **Le service tourne-t-il ?** `curl https://app-beacom-<service>.azurewebsites.net/health`. Pas de réponse : *Log stream*
   de l'App Service (erreur au démarrage, variable manquante), puis redémarrage (`az webapp restart`).
3. **Joint-il sa base ?** `curl .../health/db`. Un 503 : vérifier que la VM tourne (arrêt planifié à 22 h !), que
   PostgreSQL écoute (`az vm run-command invoke ... --scripts "systemctl status postgresql"`), la règle NSG du port 5432
   et l'intégration au réseau virtuel.
4. **Quelles erreurs ?** Requête 2 ci-dessous : les routes et codes en échec ; requête 3 : les exceptions.
5. **Suivre une requête précise.** Le `X-Request-ID` d'une réponse en erreur (renvoyé au navigateur) se retrouve dans
   les journaux de tous les services traversés : requête 5.
6. **Avis bloqués « en analyse » ?** Longueur de la file et de la poison queue (requête 6 et commande `peek`), journaux de
   la Function (requête 4). Cause fréquente : quota F0 d'Azure AI Language atteint. Une fois la cause corrigée,
   remettre les avis concernés au statut `nouveau` et appeler `POST /avis/renvoyer-nouveaux`.
7. **Clore** : noter la cause et la correction ; si une alerte n'a pas sonné alors qu'elle aurait dû, ajuster son seuil.

## Requêtes KQL

```kusto
// 1. Disponibilité : échecs du test sur 24 h
availabilityResults
| where timestamp > ago(24h)
| summarize essais = count(), echecs = countif(success == false) by name, location
| order by echecs desc

// 2. Taux de 5xx par service sur les 10 dernières minutes (base de l'alerte 2)
requests
| where timestamp > ago(10m)
| summarize total = count(), erreurs = countif(toint(resultCode) >= 500) by cloud_RoleName
| extend taux = round(100.0 * erreurs / total, 1)
| order by taux desc

// 3. Exceptions de la dernière heure, regroupées
exceptions
| where timestamp > ago(1h)
| summarize nombre = count(), exemple = any(outerMessage) by cloud_RoleName, type
| order by nombre desc

// 4. Exécutions de la Function : volume, échecs, durée
requests
| where timestamp > ago(24h) and cloud_RoleName =~ "func-beacom-nlp"
| summarize executions = count(), echecs = countif(success == false), p95_ms = percentile(duration, 95) by name

// 5. Tous les journaux d'une requête, tous services confondus (identifiant renvoyé dans X-Request-ID)
union traces, requests, exceptions
| where timestamp > ago(24h)
| where message has "<X-Request-ID>" or customDimensions has "<X-Request-ID>"
| project timestamp, cloud_RoleName, itemType, message, resultCode
| order by timestamp asc

// 6. Messages envoyés en poison queue (base de l'alerte 3)
traces
| where timestamp > ago(1h)
| where message has "avis-a-analyser-poison"
| project timestamp, message

// 7. Latence p95 par route sur 24 h
requests
| where timestamp > ago(24h) and cloud_RoleName startswith "service-"
| summarize p50 = percentile(duration, 50), p95 = percentile(duration, 95), n = count() by cloud_RoleName, name
| order by p95 desc
```

> **TODO (à vérifier au déploiement)** : la requête 6 repose sur le message que l'hôte Azure Functions journalise quand il
> déplace un message vers la poison queue (il cite le nom de cette file). Vérifier son libellé exact sur la Function
> déployée, en envoyant volontairement un message invalide, avant de considérer l'alerte 3 comme validée.
