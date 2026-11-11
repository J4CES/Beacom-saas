# service-utilisateurs

Authentification et gestion des utilisateurs (base `db_utilisateurs`). C'est le seul service qui connaît les mots de passe
et qui émet des jetons JWT. Les autres services vérifient ces jetons avec le même `JWT_SECRET`.

- Mots de passe hachés avec scrypt (jamais stockés en clair)
- Multi-clients : chaque utilisateur appartient à une **organisation** (un client de Beacom) qui a un **plan**
  (`gratuit`, `pro`, `entreprise`). Le jeton JWT porte `org` et `plan` ; les autres services filtrent dessus.
- Rôles : `admin`, `gestionnaire`, `lecteur`, valables dans l'organisation seulement
- Compte de démonstration facultatif créé au démarrage depuis `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_ORGANISATION`

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload --port 8000
```

## Routes

| Route | Accès |
|---|---|
| `POST /auth/inscription` | public : `{organisation, nom?, email, mot_de_passe}` -> crée l'organisation (plan gratuit) et son admin, renvoie un jeton |
| `POST /auth/login` | public : `{email, mot_de_passe}` -> `{access_token, role, organisation_id, plan, expires_in}` |
| `GET /me` | utilisateur connecté |
| `GET /organisations/moi` | utilisateur connecté : organisation, plan et limites |
| `PATCH /organisations/moi` | admin : renommer, changer de plan (simulation d'abonnement, sans paiement) |
| `POST /utilisateurs` | admin : crée un compte dans **son** organisation |
| `GET /utilisateurs` | admin : comptes de son organisation |
| `PATCH /utilisateurs/{id}` | admin : rôle ou désactivation, dans son organisation (404 sinon) |
| `GET /interne/organisations/{id}` | clé interne `X-API-Key` : `{id, plan}` (dépôt d'avis public) |

Limitation de débit par IP : 10 connexions / 5 min, 5 inscriptions / heure (réponse 429 avec `Retry-After`).
| `GET /health` | public |

## Tests

Depuis la racine du dépôt : `./scripts/lancer-tests.sh utilisateurs` (PostgreSQL et Python dans Docker).

## Note

`auth.py` est volontairement dupliqué dans les 4 services pour qu'ils restent déployables indépendamment.
En production, préférez une signature asymétrique ou Microsoft Entra ID (voir `docs/03-securite.md`).
