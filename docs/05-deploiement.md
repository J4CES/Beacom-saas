# 5. Déploiement sur Azure et démonstration

Région : `francecentral`. Groupe de ressources : `rg-beacom-prod`. Les commandes supposent `az login` déjà fait.
Les noms `app-beacom-*` doivent être uniques dans Azure : ajoutez un suffixe si besoin, et reportez-le dans `deploy.yml`.

## 1. Préparer

La VM, le Storage Account (file `avis-a-analyser`) et Azure AI Language se créent comme décrit à l'étape 1 du projet.
Ajoutez la quatrième base et les tables :

```bash
# Sur la VM, depuis une copie du dossier infra/sql
sudo -u postgres createdb db_utilisateurs
sudo -u postgres psql -d db_etablissements -f 01_etablissements.sql
sudo -u postgres psql -d db_collecte       -f 02_collecte.sql
sudo -u postgres psql -d db_analyses       -f 03_analyses.sql
sudo -u postgres psql -d db_utilisateurs   -f 04_utilisateurs.sql
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE db_utilisateurs TO beacom;"
```

## 2. Réseau : permettre aux App Service de joindre PostgreSQL

Les App Service doivent atteindre la VM par son adresse **privée**, jamais par Internet. Vérifiez les noms créés par `az vm create` :

```bash
RG=rg-beacom-prod
az network vnet list -g $RG -o table      # nom du réseau virtuel et plage d'adresses (souvent 10.0.0.0/16)
az vm show -d -g $RG -n vm-beacom-db --query privateIps -o tsv
```

```bash
VNET=vm-beacom-dbVNET                      # adaptez au nom constaté
az network vnet subnet create -g $RG --vnet-name $VNET -n snet-apps \
  --address-prefixes 10.0.1.0/24 --delegations Microsoft.Web/serverFarms

# Autoriser 5432 uniquement depuis ce sous-réseau
az network nsg rule create -g $RG --nsg-name vm-beacom-dbNSG -n allow-pg-from-apps --priority 1100 \
  --protocol Tcp --destination-port-ranges 5432 --source-address-prefixes 10.0.1.0/24 --access Allow
```

Sur la VM (PostgreSQL 14) :

```bash
# /etc/postgresql/14/main/postgresql.conf
listen_addresses = 'localhost,<IP_PRIVEE_VM>'
# /etc/postgresql/14/main/pg_hba.conf
host  all  beacom  10.0.1.0/24  scram-sha-256

sudo systemctl restart postgresql
```

## 3. App Service (PaaS)

```bash
az appservice plan create -g $RG -n plan-beacom --is-linux --sku B1

for s in utilisateurs etablissements collecte analyses; do
  az webapp create -g $RG -p plan-beacom -n app-beacom-$s --runtime "PYTHON:3.11"
  az webapp update -g $RG -n app-beacom-$s --https-only true
  az webapp config set -g $RG -n app-beacom-$s \
    --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
  az webapp vnet-integration add -g $RG -n app-beacom-$s --vnet $VNET --subnet snet-apps
  az webapp config appsettings set -g $RG -n app-beacom-$s --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
done
```

Paramètres d'application (secrets : à générer avec `openssl rand -hex 32`, jamais dans Git). Exemple pour `service-collecte` :

```bash
az webapp config appsettings set -g $RG -n app-beacom-collecte --settings \
  DATABASE_URL="postgresql://beacom:<MOT_DE_PASSE>@<IP_PRIVEE_VM>:5432/db_collecte" \
  JWT_SECRET="<SECRET_JWT>" INTERNAL_API_KEY="<CLE_INTERNE>" \
  STORAGE_CONNECTION_STRING="<CHAINE_STORAGE>" QUEUE_NAME="avis-a-analyser" \
  ETABLISSEMENTS_API_URL="https://app-beacom-etablissements.azurewebsites.net" \
  ALLOWED_ORIGINS="https://<URL_FRONTEND>"
```

| Application | Paramètres propres (en plus de `JWT_SECRET` et `ALLOWED_ORIGINS`) |
|---|---|
| `app-beacom-utilisateurs` | `DATABASE_URL` (db_utilisateurs), `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `JWT_EXPIRE_MINUTES` |
| `app-beacom-etablissements` | `DATABASE_URL` (db_etablissements) |
| `app-beacom-collecte` | voir ci-dessus |
| `app-beacom-analyses` | `DATABASE_URL` (db_analyses), `INTERNAL_API_KEY` |

## 4. Azure Function (FaaS)

```bash
az functionapp create -g $RG -n func-beacom-nlp --storage-account <STORAGE> \
  --consumption-plan-location francecentral --os-type Linux \
  --runtime python --runtime-version 3.11 --functions-version 4

az functionapp config appsettings set -g $RG -n func-beacom-nlp --settings \
  LANGUAGE_ENDPOINT="<ENDPOINT>" LANGUAGE_KEY="<CLE>" INTERNAL_API_KEY="<CLE_INTERNE>" \
  ANALYSES_API_URL="https://app-beacom-analyses.azurewebsites.net" \
  COLLECTE_API_URL="https://app-beacom-collecte.azurewebsites.net"
```

La Function utilise le compte de stockage pour sa file (`AzureWebJobsStorage` est défini à la création).
Si elle doit lire une file d'un autre compte, ajoutez ce paramètre à la main.

## 5. GitHub Actions

Dans le dépôt : *Settings -> Secrets and variables -> Actions*, ajoutez les profils de publication
(`az webapp deployment list-publishing-profiles -g $RG -n <app> --xml`) :

`AZURE_PUBLISH_PROFILE_UTILISATEURS`, `AZURE_PUBLISH_PROFILE_ETABLISSEMENTS`, `AZURE_PUBLISH_PROFILE_COLLECTE`,
`AZURE_PUBLISH_PROFILE_ANALYSES`, `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`.

Protégez la branche `main` (*Settings -> Branches*) : pull request et vérifications obligatoires.
Les profils de publication sont des secrets : ne les collez jamais ailleurs que dans GitHub.

## 6. Tests après déploiement et scénario de démonstration

```bash
U=https://app-beacom-utilisateurs.azurewebsites.net
E=https://app-beacom-etablissements.azurewebsites.net
C=https://app-beacom-collecte.azurewebsites.net
A=https://app-beacom-analyses.azurewebsites.net

# 1. Connexion
TOKEN=$(curl -s -X POST $U/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"<ADMIN_EMAIL>","mot_de_passe":"<ADMIN_PASSWORD>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2. Créer un établissement (service-etablissements -> db_etablissements)
curl -s -X POST $E/etablissements -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"nom":"Café Atlas","categorie":"restaurant","ville":"Casablanca"}'

# 3. Enregistrer un avis (service-collecte -> REST vers etablissements -> db_collecte -> file)
curl -s -X POST $C/avis -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"etablissement_id":1,"texte":"Service très rapide et plats délicieux, je recommande.","langue":"fr","note":5}'

# 4. Après quelques secondes : la Function a analysé l'avis
curl -s $A/analyses/avis/1 -H "Authorization: Bearer $TOKEN"
curl -s $A/analyses/resume -H "Authorization: Bearer $TOKEN"
curl -s "$C/avis?etablissement_id=1" -H "Authorization: Bearer $TOKEN"   # statut passé à « analyse »
```

À montrer à l'oral : la connexion, l'appel du microservice, l'écriture en base, l'exécution de la Function (onglet *Monitor* de la
Function App), les ressources dans le groupe `rg-beacom-prod`, et les journaux (*Log stream* des App Service).
Prévoyez des captures d'écran ou une vidéo de secours.
