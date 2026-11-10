# frontend-nextjs

Interface web de Beacom (à développer). Elle joue aussi le rôle d'**API Gateway** : ses routes serveur (`app/api/...`) appellent
les quatre services, ce qui cache leurs URLs et centralise la gestion des jetons.

## Écrans minimaux pour la démonstration

1. Connexion (`POST /auth/login` sur `service-utilisateurs`), jeton conservé dans un cookie `HttpOnly`
2. Liste et création d'établissements
3. Saisie d'un avis pour un établissement
4. Tableau de bord : répartition des sentiments (`GET /analyses/resume`) et liste des avis avec leur statut
5. (admin) Gestion des utilisateurs

## Variables prévues

`UTILISATEURS_API_URL`, `ETABLISSEMENTS_API_URL`, `COLLECTE_API_URL`, `ANALYSES_API_URL`
(et l'URL du frontend dans `ALLOWED_ORIGINS` de chaque service, pour le CORS).
