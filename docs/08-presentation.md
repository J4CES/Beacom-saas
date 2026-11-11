# 8. Présentation finale et démonstration

La présentation de l'équipe est déjà faite ; ce document sert de fil conducteur et de référence pour la démonstration.
Les chiffres sont ceux de `04-finops.md` (≈ 31 $ puis ≈ 21 $ par mois).

## Plan (≈ 12 diapositives)

| # | Diapositive | Contenu |
|---|---|---|
| 1 | Beacom | Nom, promesse en une phrase, équipe et rôles |
| 2 | Le problème | Le gérant de café apprend trop tard ce qui déçoit : avis rares, dispersés, lus à la main |
| 3 | La solution | QR code sur la table -> avis en 30 s -> analyse automatique -> alerte et rapport du lundi |
| 4 | Marché et concurrents | Restaurants et cafés au Maroc ; Partoo, Guest Suite, ReviewTrackers, Birdeye et leurs limites pour un indépendant |
| 5 | Modèle économique | Plans gratuit / pro / entreprise, abonnement par établissement (hypothèses) |
| 6 | Architecture | Diagramme Cloud (`diagrams/architecture_azure.png`) : passerelle, 4 microservices, file, Function, VM |
| 7 | IaaS / PaaS / FaaS | Pourquoi chacun : moteur PostgreSQL maîtrisé ; runtime géré ; traitement événementiel et planifié |
| 8 | Données et multi-clients | Une base par service ; isolation par organisation (404 sur la ressource d'un autre client) |
| 9 | Sécurité | Socle des 8 points, cookie HttpOnly, liste blanche de la passerelle, VM sans IP publique |
| 10 | Coûts | 31,79 $ -> 20,80 $ par mois (−34,6 %) avec les 3 leviers ; coût par client |
| 11 | Exploitation | CI/CD (tests sur chaque PR, déploiement sur `main`), Application Insights, 4 alertes |
| 12 | Limites et suite | Point de défaillance unique, passage à 100 000 utilisateurs, mise en production réelle |

## Scénario de démonstration (≈ 6 min)

Préparation la veille : VM démarrée, Function déployée, un établissement avec quelques avis déjà analysés, un
téléphone prêt à scanner le QR code. Onglets ouverts : l'application, le portail Azure (groupe de ressources, Function,
Application Insights).

1. **Connexion** : `/inscription` (ou `/connexion`) : création de l'organisation « Café Atlas ». Montrer que le
   jeton est dans un cookie HttpOnly (outils du navigateur), pas dans le JavaScript.
2. **Scénario métier** : créer l'établissement, afficher son QR code. Scanner avec le téléphone : page `/avis/<jeton>`,
   donner 1 étoile et « Une heure d'attente et le café était froid ».
3. **Appel d'un microservice** : outils du navigateur, onglet Réseau : l'appel part vers `/api/...` de la passerelle,
   jamais vers l'URL d'un service ; montrer l'en-tête `X-Request-ID` renvoyé.
4. **Lecture et écriture en base** : la page Avis montre le nouvel avis (« En analyse » puis « Analysé ») ; au besoin,
   `GET /health/db` du service et une requête `SELECT` via `az vm run-command`.
5. **Exécution de l'Azure Function** : portail, Function App, *Monitor* : l'exécution `analyser_avis` ; retour au
   tableau de bord : l'avis est négatif, l'**alerte** apparaît, « attente » remonte dans les thèmes. Lancer
   `rapport_hebdomadaire` à la demande (commande de `05-deploiement.md` § 4) et montrer le rapport.
6. **Ressources Azure** : groupe `rg-beacom-prod` : VM (sans IP publique), plan App Service et ses 5 applications,
   Function App, compte de stockage et sa file, AI Language, Application Insights.
7. **Logs et traces** : Application Insights, *Cartographie d'application*, puis la requête KQL 5 de
   `06-observabilite.md` avec le `X-Request-ID` relevé à l'étape 3 : on suit l'avis de la passerelle à la Function.

## Plan B

- **Captures d'écran** de chaque étape, prises la veille, dans l'ordre du scénario, et la même séquence en **vidéo**
  (2 à 3 min, sans son, sous-titrée), sur l'ordinateur et sur une clé USB.
- Si Azure est indisponible : démonstration locale (services, frontend et PostgreSQL dans Docker, voir le README), puis
  captures des écrans Azure (Function *Monitor*, Application Insights, groupe de ressources).
- Si seule l'analyse tarde (quota d'AI Language) : montrer un avis déjà analysé et l'alerte existante, puis expliquer la
  reprise automatique (file, 5 tentatives, poison queue, `renvoyer-nouveaux`).
