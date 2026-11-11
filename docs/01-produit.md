# 1. Produit : pitch, besoin, backlog

> Document à relire et à adapter par l'équipe : le positionnement ci-dessous est déduit de l'architecture du projet
> (établissements, avis, analyse de sentiment). Les chiffres de tarification sont des hypothèses à valider.

## Pitch

**Beacom** est un SaaS d'e-réputation pour les établissements (restaurants, hôtels, cliniques, centres de formation...).
Il centralise les avis clients, en analyse automatiquement le sentiment et présente un tableau de bord qui montre
ce que les clients apprécient et ce qui les déçoit, établissement par établissement.

## Expression du besoin

| Question du TP | Réponse |
|---|---|
| Problème identifié | Les avis sont dispersés et lus à la main : on voit tard les problèmes récurrents, et on ne mesure pas l'évolution de la satisfaction |
| Utilisateurs concernés | Gérants et responsables qualité d'établissements, groupes multi-sites |
| Solution proposée | Collecte centralisée des avis, analyse de sentiment automatique, tableau de bord par établissement |
| Valeur ajoutée | Gain de temps, détection rapide des avis négatifs, vue consolidée multi-établissements |
| Concurrents / existant | Outils d'e-réputation généralistes et tableurs. À compléter par l'équipe avec 2 ou 3 concurrents nommés et leurs limites |
| Modèle économique (hypothèse) | Abonnement mensuel par établissement, avec paliers selon le volume d'avis analysés |

## Fonctionnalités minimales exigées par le TP

| # | Exigence | Où dans le projet |
|---|---|---|
| 1 | Authentification | `service-utilisateurs` : `POST /auth/login`, jeton JWT |
| 2 | Gestion des utilisateurs | `service-utilisateurs` : création, rôles, désactivation (admin) |
| 3 | Fonctionnalité métier principale | Collecte d'avis et analyse de sentiment (`service-collecte`, `function-nlp`) |
| 4 | Tableau de bord | `GET /analyses/resume` + `frontend-nextjs` (à développer) |
| 5 | Gestion des données | Une base PostgreSQL par service |
| 6 | API backend | 4 API REST FastAPI |
| 7 | Traitement automatique | `function-nlp`, déclenchée par la file `avis-a-analyser` |

## Backlog fonctionnel

Priorités MoSCoW : **M** = indispensable pour la démonstration, **S** = souhaitable, **C** = si le temps le permet.

| Id | En tant que... | Je veux... | Priorité | État |
|---|---|---|---|---|
| U0 | nouveau client | créer mon organisation et mon compte en libre-service | M | API faite |
| U1 | utilisateur | me connecter avec e-mail et mot de passe | M | API faite |
| U2 | admin | créer des comptes et leur donner un rôle | M | API faite |
| U3 | admin | désactiver un compte | S | API faite |
| U4 | client | ne jamais voir les données d'un autre client | M | API faite, testée |
| U5 | admin | changer le plan de mon organisation (gratuit, pro, entreprise) | S | API faite (sans paiement) |
| E1 | gestionnaire | créer et consulter des établissements | M | API faite |
| E2 | admin | supprimer un établissement | S | API faite |
| A1 | gestionnaire | enregistrer un avis pour un établissement | M | API faite |
| A0 | client d'un café | laisser un avis en scannant un QR code, sans créer de compte | M | API faite (page à faire) |
| A2 | système | analyser chaque avis automatiquement | M | Function faite |
| A3 | admin | renvoyer les avis dont l'envoi a échoué | S | API faite |
| D1 | lecteur | voir la répartition des sentiments | M | API faite, écran à faire |
| D2 | lecteur | filtrer les avis et analyses par établissement | S | API faite (écran à faire) |
| D3 | gérant | être alerté d'un avis très négatif (tableau de bord + e-mail) | S | Function et API faites |
| D4 | gérant | voir l'évolution des sentiments par jour ou par semaine | S | API faite (écran à faire) |
| D5 | gérant | savoir de quoi se plaignent les clients (mots-clés des avis négatifs) | S | Function et API faites |
| D6 | gérant | recevoir chaque lundi un rapport de la semaine | S | Function planifiée et API faites |
| F1 | utilisateur | une interface web pour tout cela | M | À faire (`frontend-nextjs`) |
| I1 | gestionnaire | importer des avis depuis un fichier CSV | C | API faite |
