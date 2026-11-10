# 4. Estimation des coûts (FinOps)

> **À compléter.** Les prix Azure varient selon la région, la devise et le temps. Je n'ai pas pu relever de tarifs fiables ici :
> renseignez la colonne « Prix » avec le [calculateur de prix Azure](https://azure.microsoft.com/pricing/calculator/)
> (région France Central) et joignez une capture ou l'export à votre rendu.

## Postes à chiffrer

| Poste | Démonstration (faible coût) | Production (plus fiable) | Prix démo | Prix prod |
|---|---|---|---|---|
| Machine virtuelle | `Standard_B1s`, arrêt à 22h00 et au démarrage à la demande | VM plus grande, ou base managée | | |
| Stockage de la VM | Disque système standard (HDD/SSD standard) | SSD premium, instantanés planifiés | | |
| Azure App Service | Un plan Linux partagé par les 4 API (B1, ou F1 gratuit pour tester) | Plan Premium, 2 instances minimum | | |
| Azure Functions | Plan Consommation (1 million d'exécutions mensuelles offertes) | Plan Consommation ou Premium | | |
| Base de données | Incluse dans la VM | PostgreSQL Flexible Server avec haute disponibilité | | |
| Storage Account (file, sauvegardes) | `Standard_LRS` | `Standard_GRS` | | |
| Azure AI Language | Niveau F0 (gratuit, volume limité) | Niveau S payant à la consommation | | |
| Réseau | IP publique de la VM, trafic sortant faible | Gateway, Private Endpoints | | |
| Journaux et supervision | Journaux App Service, rétention courte | Log Analytics + Application Insights | | |

## Comment réduire le coût de 30 % sans perdre de fonctionnalité

| Levier | Effet |
|---|---|
| Arrêt automatique de la VM à 22h00 (et démarrage le matin) | Le calcul n'est facturé que quand la VM tourne. Exemple : 14 h/24 h de marche = 42 % d'économie sur le calcul de la VM. Le disque et l'IP publique restent facturés |
| Un seul plan App Service pour les 4 API | On paie un plan, pas quatre |
| Function en plan Consommation | Facturation à l'exécution : zéro coût sans messages |
| Azure AI Language en F0 pour la démo | Gratuit dans la limite du quota |
| Supprimer le groupe de ressources après la démo | `az group delete -n rg-beacom-prod` arrête toute facturation |
| Étiquettes (tags) et alerte de budget | Rendre les coûts visibles par service et être prévenu avant le dépassement |
| En production : réservations 1 ou 3 ans | Remise importante sur la VM et le plan App Service pour une charge stable |

Une alerte de budget se crée dans Cost Management (menu « Budgets »).
