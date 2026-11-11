# 7. Soutenance : les 10 questions

Réponses courtes, avec le document qui les détaille.

**1. Pourquoi votre produit est-il un SaaS ?**
Beacom est une application en ligne, accessible par navigateur, sans rien installer. Plusieurs clients (des
organisations) partagent une seule installation, chacun ne voyant que ses données (isolation par `organisation_id`,
testée dans chaque service). Le client s'inscrit seul et paie un abonnement mensuel par établissement (plans gratuit,
pro, entreprise). Nous hébergeons, mettons à jour et faisons évoluer le service pour tous à la fois (déploiement continu).
-> `01-produit.md`, `02-architecture.md` § Multi-clients.

**2. Pourquoi ces microservices ?**
Un service par domaine métier, qui évolue et se déploie seul et possède sa base :
- identité (sensible, change peu) ;
- référentiel d'établissements (stable) ;
- collecte (écritures fréquentes, canal public) ;
- analyses (surtout lu, calculs du tableau de bord).

La Function fait le travail asynchrone. Aucun service n'existe seulement pour atteindre le nombre minimal.
-> `02-architecture.md` § Découpage.

**3. Pourquoi une VM ?**
Le TP impose de l'IaaS, et nous l'utilisons là où le contrôle complet a du sens : le moteur PostgreSQL, sa
configuration et ses bases. Nous assumons l'exploitation qui va avec (mises à jour, sauvegardes). La VM n'a pas d'IP
publique, elle est administrée par `az vm run-command` et éteinte la nuit. -> `02-architecture.md` § IaaS.

**4. Pourquoi App Service ?**
Nos API et le frontend n'ont besoin que d'un environnement d'exécution, Python ou Node. Azure gère le système, les
correctifs, le HTTPS et la mise à l'échelle. Un seul plan B1 porte les 5 applications, déployées par GitHub Actions.
-> `02-architecture.md` § PaaS.

**5. Pourquoi Azure Functions ?**
Les deux traitements sont courts, sans état et irréguliers :
- l'analyse de chaque avis, déclenchée par un message en file ;
- le rapport du lundi matin, planifié.

Le plan Consommation ne facture que l'exécution (0 $ à notre volume) et monte en charge seul lors d'un afflux d'avis.
-> `function-nlp/README.md`.

**6. Quelle est la principale faiblesse ?**
La VM unique porte les 4 bases : c'est un point de défaillance unique, sans haute disponibilité, avec des sauvegardes
que nous gérons nous-mêmes. Viennent ensuite :
- le secret JWT partagé entre les services ;
- une limitation de débit en mémoire, propre à chaque instance.

-> `02-architecture.md` § Limites, `03-securite.md`.

**7. Combien coûte votre solution ?**
Prix relevés le 11 novembre 2026, en USD, région francecentral, par l'API Azure Retail Prices :
- **≈ 31,79 $/mois** dans la configuration par défaut ;
- **≈ 20,80 $/mois** après trois leviers (VM arrêtée de 22 h à 8 h, disque Standard SSD, plus d'IP publique), soit **−34,6 %** ;
- environ 0,42 $ par client et par mois pour 50 clients.

Pour la production, comptez environ 300 $/mois et plus (2 instances P1 v3, PostgreSQL managé). -> `04-finops.md`.

**8. Comment passer de 100 à 100 000 utilisateurs ?**
- plusieurs instances App Service, avec une mise à l'échelle automatique ;
- PostgreSQL managé avec réplicas de lecture et pool de connexions (PgBouncer) ;
- un cache pour les lectures du tableau de bord ;
- une file plus Functions qui absorbent les pics d'avis ;
- Azure AI Language en niveau Standard ;
- Front Door ou API Management devant, pour la limitation de débit distribuée ;
- à terme, une base par gros client si l'isolation l'exige.

-> `02-architecture.md` § Limites.

**9. Pourriez-vous supprimer entièrement l'IaaS ?**
Oui. Azure Database for PostgreSQL Flexible Server remplace la VM, avec des sauvegardes, la haute disponibilité et les
correctifs gérés par Azure. Le code ne change pas, seules les chaînes de connexion changent. Nous gardons la VM parce
que le TP l'exige et pour la maîtrise du moteur.

**10. Que changeriez-vous pour une vraie mise en production ?**
- base managée et chiffrement TLS de bout en bout ;
- Key Vault et identités managées à la place des secrets en paramètres ;
- jetons signés par clé asymétrique, ou Microsoft Entra ID ;
- Private Endpoints, avec seuls la passerelle ou API Management pour joindre les services ;
- verrouillage de compte et authentification multifacteur ;
- environnements séparés (recette et production) ;
- paiement réel des abonnements ;
- alertes réglées sur un vrai trafic.

-> `03-securite.md` § Points à traiter.
