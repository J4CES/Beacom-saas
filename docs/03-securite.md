# 3. Analyse de sécurité

Légende : **Code** = déjà dans le dépôt ; **Azure** = à configurer sur Azure (commandes dans `05-deploiement.md`).

| # | Socle minimal du TP | Mesure | Où | Limite connue |
|---|---|---|---|---|
| 1 | HTTPS | `--https-only` sur les App Service ; HTTPS natif de la Function | Azure | Le trafic App Service -> VM (5432) reste en clair dans le réseau virtuel privé : activer SSL PostgreSQL en production |
| 2 | Authentification | Connexion e-mail + mot de passe, jeton JWT signé (HS256) d'une heure ; mots de passe hachés avec scrypt et sel | Code | Pas de limitation du nombre d'essais, ni de double authentification, ni de jeton de rafraîchissement |
| 3 | Autorisation par rôles | `admin`, `gestionnaire`, `lecteur` vérifiés par chaque service (`exiger_roles`), **dans l'organisation du jeton** : chaque requête SQL filtre sur `organisation_id`, testé dans chaque service | Code | Les rôles et le plan sont dans le jeton : un rôle retiré ou un plan changé ne s'applique qu'à son expiration (1 h maximum) |
| 4 | Protection des secrets | Paramètres d'application Azure, secrets GitHub, `.env` et `local.settings.json` ignorés par Git | Code + Azure | En production : Key Vault et identités managées. Le `JWT_SECRET` partagé entre services est un compromis : une clé asymétrique évite que chaque service puisse signer |
| 5 | Ports limités sur la VM | SSH limité à une IP ; 5432 ouvert uniquement au sous-réseau des App Service | Azure | L'IP personnelle change : mettre la règle à jour |
| 6 | Protection de la base | Pas d'exposition Internet, rôle applicatif sans droits superutilisateur, `scram-sha-256`, droits limités à SELECT/INSERT/UPDATE/DELETE | Azure + SQL | Pas de chiffrement des disques géré par nous (chiffrement Azure par défaut uniquement) |
| 7 | Journalisation des accès | Journal d'accès de chaque service (méthode, chemin, statut, durée, IP) sur la sortie standard, collecté par App Service | Code | À envoyer vers Log Analytics pour conserver et interroger |
| 8 | Aucun mot de passe dans GitHub | `.gitignore` strict, fichiers `.env.example` sans valeur réelle, déploiement par secrets GitHub | Code | Si un secret a déjà été commité, il faut le **renouveler**, pas seulement le supprimer |

## Autres mesures en place

- Isolation des clients : une ressource d'une autre organisation répond 404, comme une ressource inexistante.
  `source_id` est unique par organisation, pour qu'un 409 ne révèle rien d'un autre client.

- Service à service : la Function s'authentifie par une clé interne comparée en temps constant ; les routes internes sont distinctes des routes publiques.
- Le message d'erreur de connexion est identique pour un e-mail inconnu et un mauvais mot de passe, et le temps de réponse est équivalent.
- Entrées validées (taille, format, bornes) et requêtes SQL paramétrées (pas d'injection SQL).
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` créent un compte de démonstration au démarrage : à retirer après usage.
- `POST /auth/inscription` est public et sans limitation de débit pour l'instant : une limite par IP arrive avec le canal de collecte public.

## Points à traiter avant une mise en production réelle

1. Limiter les tentatives de connexion (anti-force brute) et ajouter une authentification multifacteur.
2. Passer à Microsoft Entra ID ou à des jetons signés par clé asymétrique.
3. Déplacer les secrets dans Key Vault, avec identités managées.
4. Base managée, chiffrement TLS de bout en bout, Private Endpoints.
5. Envoyer les journaux vers Log Analytics, avec alertes sur les échecs d'authentification.
