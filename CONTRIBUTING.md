# Contribuer à Beacom

## Règles

1. **`main` est protégée** : on n'y pousse jamais directement. Tout passe par une pull request.
2. **Une branche par fonctionnalité**, créée depuis `main` : `feat/<sujet>`, `fix/<sujet>`, `docs/<sujet>`, `chore/<sujet>`.
3. **De petits commits explicites**, préfixés : `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`
   (portée facultative : `feat(collecte): ...`). Le message dit *quoi* et *pourquoi*.
4. **Chaque PR est relue** par au moins un autre membre de l'équipe et doit passer la CI avant la fusion.
5. **Aucun secret dans le dépôt** : `.env` et `local.settings.json` sont ignorés ; toute nouvelle variable va dans le
   `.env.example` du service et dans `docs/05-deploiement.md`. Un secret commité par erreur se **renouvelle**.
6. Le code, les commentaires et la documentation sont en français. `auth.py` reste **identique** dans les 4 services
   (vérifié par la CI).

## Avant d'ouvrir une PR

```bash
./scripts/lancer-tests.sh                                      # tests Python contre PostgreSQL (Docker)
docker run --rm -v "$PWD":/src -w /src python:3.11-slim \
  sh -c "pip install -q ruff && ruff check ."                  # lint Python
cd frontend-nextjs && npm run lint && npm run typecheck && npm run build   # si le frontend change
```

Mettez à jour les docs et les tests concernés dans la même PR.

## Ce que vérifie la CI (`.github/workflows/deploy.yml`)

| Job | Contenu |
|---|---|
| `Tests (PostgreSQL réel)` | syntaxe, ruff, `auth.py` identique, tests des 4 services, des migrations et de la Function |
| `Frontend (lint, types, build)` | ESLint, TypeScript, build Next.js, `npm audit` des dépendances de production |

Après fusion dans `main` : déploiement des 4 API, de la Function et du frontend, puis vérification de `/health`.

## Protection de `main` (à faire une fois, par un administrateur du dépôt)

Exige une PR relue par une personne, les deux contrôles de la CI à jour, et interdit les push forcés et la suppression :

```bash
gh api -X PUT repos/J4CES/Beacom-saas/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Tests (PostgreSQL réel)", "Frontend (lint, types, build)"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Les noms des contrôles n'existent pour GitHub qu'après une première exécution du workflow : lancez la commande après la
première PR. Équivalent dans l'interface : *Settings -> Branches -> Add branch protection rule*.
