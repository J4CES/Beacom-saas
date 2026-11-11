# 4. Estimation des coûts (FinOps)

**Source des prix** : API publique [Azure Retail Prices](https://prices.azure.com/api/retail/prices), `currencyCode=USD`,
`armRegionName=francecentral`, prix publics à l'usage (`Consumption`), sans remise ni réservation.
**Date du relevé : 11 novembre 2026.** Les prix évoluent : relancez les requêtes de la fin de ce document avant toute décision.
Convention : un mois compte **730 heures**.

## 1. Démonstration : configuration par défaut

C'est ce que créent les commandes de `05-deploiement.md` sans optimisation : VM allumée en permanence, disque système
Premium SSD (choix par défaut de `az vm create`), IP publique sur la VM.

| Poste | Ressource | Prix unitaire relevé | Calcul | **USD / mois** |
|---|---|---|---|---|
| Machine virtuelle | `Standard_B1s` Linux, 24 h/24 | 0,0118 $/h | 0,0118 × 730 | **8,61** |
| Stockage de la VM | Disque Premium SSD P4 (32 Go, LRS) | 6,3879 $/mois | forfait | **6,39** |
| Réseau | IP publique IPv4 statique Standard | 0,005 $/h | 0,005 × 730 | **3,65** |
| Azure App Service | Plan Basic **B1 Linux**, partagé par les 4 API et le frontend | 0,018 $/h | 0,018 × 730 | **13,14** |
| Azure Functions | Plan Consommation | gratuit jusqu'à 400 000 Go-s et 1 million d'exécutions par mois ; au-delà, 0,000016 $/Go-s et 0,000002 $ par lot de 10 exécutions | volume de la démo bien en dessous | **0,00** |
| Base de données | PostgreSQL sur la VM | comprise dans la VM | - | **0,00** |
| File de messages | Storage Queues v2, Standard LRS | 0,045 $/Go/mois ; 0,004 $ pour 10 000 opérations | quelques milliers d'opérations | **< 0,05** |
| Azure AI Language | Niveau Free (F0) | 0 $ ; niveau payant : 1 $ pour 1 000 enregistrements de texte | dans le quota gratuit | **0,00** |
| Journaux et supervision | Log Analytics / Application Insights | 5 premiers Go ingérés par mois gratuits, puis 2,76 $/Go | moins de 1 Go/mois en démo | **0,00** |
| **Total** | | | | **≈ 31,79 $ / mois** |

Cohérent avec la présentation (**≈ 31 $/mois**) : l'écart tient à l'arrondi.

## 2. Réduire le coût de 30 % sans supprimer de fonctionnalité : trois leviers

| Levier | Avant | Après | Économie / mois |
|---|---|---|---|
| **1. Arrêt automatique de la VM de 22 h à 8 h** (arrêt planifié le soir, démarrage planifié le matin) : 14 h de marche par jour, soit 425,8 h/mois | 8,61 $ | 0,0118 × 425,8 = **5,02 $** | 3,59 $ |
| **2. Disque Standard SSD E4** (32 Go) au lieu du Premium SSD P4 : largement suffisant pour une base de démonstration | 6,39 $ | **2,64 $** | 3,75 $ |
| **3. Plus d'IP publique sur la VM** : administration par `az vm run-command invoke`, sans port SSH ouvert ; les App Service joignent PostgreSQL par son adresse privée (intégration au réseau virtuel) | 3,65 $ | **0,00 $** | 3,65 $ |
| Reste (App Service, Functions, file, AI Language, journaux) | 13,19 $ | 13,19 $ | - |
| **Total** | **31,79 $** | **≈ 20,80 $** | **10,99 $, soit −34,6 %** |

Cohérent avec la présentation (**≈ 21 $/mois**) : l'objectif de −30 % est dépassé.

Conséquences assumées :
- **Levier 1** : le service est coupé la nuit, ce qui convient à une démonstration. Pendant l'arrêt, les API répondent
  503 (base injoignable) ; un avis déjà en file attend la Function, qui réessaie.
- **Levier 3** : il renforce aussi la sécurité, car la VM n'expose plus rien sur Internet (voir `03-securite.md`).

Autres leviers, non chiffrés ici :
- plan App Service F1 (gratuit) pour les tests ;
- suppression du groupe de ressources après la soutenance (`az group delete -n rg-beacom-prod`), qui ramène la facture à 0 ;
- étiquettes de coût et alerte à 80 % d'un budget de **25 $/mois** (alerte 4 de `06-observabilite.md`).

## 3. Production (plus fiable)

| Poste | Choix | Prix unitaire relevé | **USD / mois** |
|---|---|---|---|
| App Service | 2 instances **P1 v3 Linux** (haute disponibilité, mise à l'échelle) | 0,174 $/h par instance | 2 × 0,174 × 730 = **254,04** |
| Base de données | **Azure Database for PostgreSQL Flexible Server**, qui remplace la VM (sauvegardes et haute disponibilité gérées) | calcul : **TODO**, l'API n'a pas renvoyé ce prix lors du relevé, à compléter avec le [calculateur Azure](https://azure.microsoft.com/pricing/calculator/) ; stockage : 0,133 $/Go/mois | 32 Go × 0,133 = **4,26** + calcul **TODO** |
| Azure Functions | Consommation | voir § 1 | quelques dollars selon le volume |
| Azure AI Language | Standard, à l'usage | 1 $ pour 1 000 enregistrements (sentiment et mots-clés comptent chacun) | 10 000 avis/mois ≈ **20,00** |
| Journaux | Log Analytics au-delà de 5 Go | 2,76 $/Go ingéré | 10 Go ≈ **13,80** |
| Stockage géo-redondant, Key Vault, Front Door | - | **TODO** | - |
| **Sous-total connu** | | | **≈ 292 $ + PostgreSQL + TODO** |

## 4. Coût par client et prix de l'abonnement

Les prix d'abonnement sont des **hypothèses** (voir `01-produit.md`).

| Clients payants | Coût de la plateforme (démo optimisée) | Coût par client et par mois |
|---|---|---|
| 10 | 20,80 $ | 2,08 $ |
| 50 | 20,80 $ | 0,42 $ |

Avec l'hypothèse d'un plan Pro à **149 MAD par établissement et par mois** (`01-produit.md`), le coût d'infrastructure
d'un client reste une petite fraction de son abonnement.

Le coût qui varie avec l'usage est **Azure AI Language** au-delà du quota gratuit : environ 0,002 $ par avis (sentiment
et mots-clés). Un client qui reçoit 1 000 avis par mois coûte donc environ 2 $, très en dessous de son abonnement.

La rentabilité se joue surtout au passage à l'architecture de production, à environ 300 $/mois et plus : il faut alors
quelques dizaines de clients payants pour la couvrir.

## Requêtes utilisées (rejouables)

```bash
P="https://prices.azure.com/api/retail/prices"
q() { curl -s -G "$P" --data-urlencode "currencyCode=USD" --data-urlencode "\$filter=$1"; }
q "armRegionName eq 'francecentral' and armSkuName eq 'Standard_B1s' and priceType eq 'Consumption' and serviceName eq 'Virtual Machines'"
q "armRegionName eq 'francecentral' and serviceName eq 'Storage' and (meterName eq 'P4 LRS Disk' or meterName eq 'E4 LRS Disk')"
q "armRegionName eq 'francecentral' and serviceName eq 'Virtual Network' and productName eq 'IP Addresses' and priceType eq 'Consumption'"
q "armRegionName eq 'francecentral' and serviceName eq 'Azure App Service' and skuName eq 'B1' and priceType eq 'Consumption'"
q "armRegionName eq 'francecentral' and serviceName eq 'Functions' and priceType eq 'Consumption' and skuName eq 'Standard'"
q "armRegionName eq 'francecentral' and serviceName eq 'Log Analytics' and priceType eq 'Consumption'"
q "armRegionName eq 'francecentral' and contains(productName,'Language') and contains(meterName,'Text Records') and priceType eq 'Consumption'"
q "armRegionName eq 'francecentral' and serviceName eq 'Storage' and productName eq 'Queues v2' and skuName eq 'Standard LRS'"
q "armRegionName eq 'francecentral' and serviceName eq 'Azure App Service' and skuName eq 'P1 v3' and contains(productName,'Linux') and priceType eq 'Consumption'"
```
