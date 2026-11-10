# service-utilisateurs

Authentification et gestion des utilisateurs (base `db_utilisateurs`). C'est le seul service qui connaît les mots de passe
et qui émet des jetons JWT. Les autres services vérifient ces jetons avec le même `JWT_SECRET`.

- Mots de passe hachés avec scrypt (jamais stockés en clair)
- Rôles : `admin`, `gestionnaire`, `lecteur`
- L'administrateur initial est créé au démarrage depuis `ADMIN_EMAIL` / `ADMIN_PASSWORD`

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
| `POST /auth/login` | public : `{email, mot_de_passe}` -> `{access_token, role, expires_in}` |
| `GET /me` | utilisateur connecté |
| `POST /utilisateurs` | admin |
| `GET /utilisateurs` | admin |
| `PATCH /utilisateurs/{id}` | admin : changer le rôle ou désactiver un compte |
| `GET /health` | public |

## Tests

```bash
pip install pytest
pytest tests
```

## Note

`auth.py` est volontairement dupliqué dans les 4 services pour qu'ils restent déployables indépendamment.
En production, préférez une signature asymétrique ou Microsoft Entra ID (voir `docs/03-securite.md`).
