# 1. Produit : pitch, besoin, backlog

## Pitch

**Beacom** aide les **restaurants et cafés au Maroc**, de l'indépendant à la petite chaîne de quelques adresses, à
comprendre ce que pensent leurs clients. Un QR code sur la table, un avis laissé en 30 secondes, sans compte ; Beacom
l'analyse aussitôt (positif, négatif, de quoi on parle) et prévient le gérant quand un client repart très mécontent.
Chaque lundi matin, un rapport dit ce qui a progressé et ce qui coince, établissement par établissement.

## Expression du besoin

| Question du TP | Réponse |
|---|---|
| Problème identifié | Un gérant de café ou de restaurant apprend souvent trop tard qu'un problème se répète (attente, accueil, propreté) : les avis sont rares, dispersés (Google, réseaux sociaux, remarques orales) et lus à la main, et un client mécontent part sans rien dire |
| Utilisateurs concernés | Gérants de cafés et restaurants indépendants ; responsables de petites chaînes (2 à 10 adresses) qui veulent comparer leurs établissements ; leurs clients, qui donnent leur avis sans créer de compte |
| Solution proposée | Un SaaS qui collecte les avis (QR code et lien public, saisie, import CSV), les analyse automatiquement (sentiment et thèmes, Azure AI Language), alerte sur les avis très négatifs et produit un tableau de bord et un rapport hebdomadaire par établissement |
| Valeur ajoutée | Collecte directe sur place, sans compte ni application pour le client ; alerte immédiate qui permet de rattraper un client le jour même ; lecture par thèmes (« attente », « café froid ») plutôt qu'une note moyenne ; prix pensé pour un indépendant, avec un plan gratuit |
| Concurrents / existant | Voir ci-dessous |
| Modèle économique | Abonnement mensuel **par établissement**, avec un plan gratuit d'appel (voir ci-dessous) |

## Concurrents et solutions existantes

Recherche du 11 novembre 2026. Les prix publics sont rares ; les montants cités viennent d'annuaires de logiciels et sont
**indicatifs** (**TODO** : les confirmer par une demande de devis).

| Solution | Ce qu'elle propose | Limites pour notre cible | Ce qui distingue Beacom |
|---|---|---|---|
| **Partoo** (France) | Gestion des fiches locales (Google, etc.), des avis et des messages pour les enseignes multi-établissements ; prix sur devis, « à partir de 149 € » par mois facturés à l'année selon GetApp ([lafabriquedunet.fr](https://www.lafabriquedunet.fr/logiciels/comparateur/partoo-vs-guest-suite), [getapp.fr](https://www.getapp.fr/software/2059946/partoo)) | Pensé pour les réseaux et enseignes ; budget élevé pour un café indépendant ; centré sur la présence en ligne plutôt que sur la collecte en salle | Collecte sur place par QR code, analyse par thèmes, plan gratuit |
| **Guest Suite** (France) | Collecte d'avis certifiée NF Service (AFNOR), puis gestion des fiches ; tarifs dégressifs selon le nombre de points de vente, essai sur demande ([leptidigital.fr](https://www.leptidigital.fr/logiciels/guest-suite/), [capterra.fr](https://www.capterra.fr/software/196590/guest-suite)) | Prix non publiés ; outil complet mais calibré pour des structures plus grandes | Démarrage en libre-service en 2 minutes, sans devis |
| **ReviewTrackers** (États-Unis) | Suivi des avis multi-sites, campagnes de demande d'avis, **analyse de sentiment**, rapports comparatifs ; restauration et hôtellerie parmi ses premiers secteurs ; prix d'entrée relevés entre 89 $ et 299 $ par mois selon les sources ([capterra.com](https://www.capterra.com/p/140801/ReviewTrackers/), [g2.com](https://www.g2.com/compare/birdeye-vs-reviewtrackers)) | Interface et support en anglais, tarification en dollars, marché nord-américain | En français, prix en dirhams, alertes et rapport pensés pour un gérant |
| **Birdeye** (États-Unis) | Plateforme complète de réputation (avis, messagerie, enquêtes, analyses de sentiment) ; prix sur devis, essai de 30 jours ([softwareadvice.com](https://www.softwareadvice.com/survey/birdeye-profile/), [g2.com](https://www.g2.com/compare/reputation-vs-reviewtrackers-vs-birdeye)) | Très large, donc complexe et coûteux pour un petit établissement | Juste l'essentiel : collecter, comprendre, réagir |
| Existant gratuit : **fiche Google Business Profile**, cahier d'avis, réseaux sociaux | Avis publics gratuits | Peu d'avis spontanés, aucun regroupement par thème, aucune alerte, rien pour comparer plusieurs adresses | Avis privés collectés sur place, analysés et suivis dans le temps |

## Modèle économique (hypothèses)

Abonnement mensuel **par établissement**. Les limites des plans sont celles du prototype (`LIMITES_PLANS`).
**Hypothèses de prix, à valider auprès de gérants** ; les montants en euros sont des équivalents arrondis
(**TODO** : vérifier le cours MAD/EUR du jour ; calcul fait avec 1 € ≈ 10,8 MAD).

| Plan | Limites | Prix (hypothèse) | Pour qui |
|---|---|---|---|
| **Gratuit** | 1 établissement, 100 avis par mois | 0 MAD | Découvrir l'outil ; un petit café |
| **Pro** | jusqu'à 5 établissements, avis illimités | **149 MAD / établissement / mois** (≈ 14 €) | Indépendant ou petite chaîne |
| **Entreprise** | illimité | **119 MAD / établissement / mois** (≈ 11 €) à partir de 6 établissements, sur contrat annuel | Chaînes et groupes |

Comparaison avec le coût d'infrastructure : `04-finops.md` § 4.

## Fonctionnalités minimales exigées par le TP

| # | Exigence | Où dans le projet |
|---|---|---|
| 1 | Authentification | `service-utilisateurs` : `POST /auth/login`, jeton JWT |
| 2 | Gestion des utilisateurs | `service-utilisateurs` : création, rôles, désactivation (admin) |
| 3 | Fonctionnalité métier principale | Collecte d'avis et analyse de sentiment (`service-collecte`, `function-nlp`) |
| 4 | Tableau de bord | `frontend-nextjs` : répartition, évolution, thèmes négatifs, alertes, par établissement |
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
| A0 | client d'un café | laisser un avis en scannant un QR code, sans créer de compte | M | Fait (page mobile `/avis/<jeton>`) |
| A2 | système | analyser chaque avis automatiquement | M | Function faite |
| A3 | admin | renvoyer les avis dont l'envoi a échoué | S | API faite |
| D1 | lecteur | voir la répartition des sentiments | M | Fait |
| D2 | lecteur | filtrer les avis et analyses par établissement | S | Fait |
| D3 | gérant | être alerté d'un avis très négatif (tableau de bord + e-mail) | S | Function et API faites |
| D4 | gérant | voir l'évolution des sentiments par jour ou par semaine | S | Fait |
| D5 | gérant | savoir de quoi se plaignent les clients (mots-clés des avis négatifs) | S | Function et API faites |
| D6 | gérant | recevoir chaque lundi un rapport de la semaine | S | Function planifiée et API faites |
| F1 | utilisateur | une interface web pour tout cela | M | Fait (`frontend-nextjs`) |
| I1 | gestionnaire | importer des avis depuis un fichier CSV | C | API faite |
