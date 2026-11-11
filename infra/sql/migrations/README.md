# Migrations SQL

Scripts **idempotents** à appliquer sur une base déjà créée avec une version précédente des scripts `../0X_*.sql`.
On peut les rejouer sans risque. Une installation neuve n'en a pas besoin : les scripts de création sont déjà à jour.

Ordre d'application, sur la VM :

```bash
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_utilisateurs   -f 001_multi_clients_utilisateurs.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_etablissements -f 001_multi_clients_etablissements.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_collecte       -f 001_multi_clients_collecte.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_analyses       -f 001_multi_clients_analyses.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_etablissements -f 002_jeton_public_etablissements.sql
```

| Migration | Effet |
|---|---|
| `001_multi_clients_*` | Ajoute les organisations. Les données existantes sont rattachées à l'organisation 1, « Organisation par défaut », au plan `entreprise` pour ne pas les soumettre aux limites. |
| `002_jeton_public_etablissements` | Jeton public de collecte (lien et QR code), un par établissement, unique et aléatoire. |

Avant de déployer la version multi-clients, laissez la file `avis-a-analyser` se vider : un ancien message sans
`organisation_id` serait refusé par `service-analyses` et finirait dans la poison queue. On le rattrape ensuite avec
`POST /avis/renvoyer-nouveaux` après avoir remis l'avis au statut `nouveau`.
