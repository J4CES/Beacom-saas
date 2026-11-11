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

**Bases déjà créées avec une version antérieure** : appliquez les migrations idempotentes, dans l'ordre, puis déployez
le code. Avant la migration multi-clients, laissez la file `avis-a-analyser` se vider (voir `infra/sql/migrations/README.md`).

```bash
for b in utilisateurs etablissements collecte analyses; do
  sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_$b -f migrations/001_multi_clients_$b.sql
done
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_etablissements -f migrations/002_jeton_public_etablissements.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_analyses       -f migrations/003_analyses_par_etablissement.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d db_analyses       -f migrations/004_rapports_hebdomadaires.sql
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
  UTILISATEURS_API_URL="https://app-beacom-utilisateurs.azurewebsites.net" \
  PROXIES_DE_CONFIANCE=2 ALLOWED_ORIGINS="https://<URL_FRONTEND>"
```

`INTERNAL_API_KEY` est la même valeur dans les 4 services et la Function. `PROXIES_DE_CONFIANCE` vaut `2` quand les
appels passent par la passerelle Next.js (frontal App Service du frontend + passerelle), `1` sinon.

| Application | Paramètres propres (en plus de `JWT_SECRET`, `ALLOWED_ORIGINS` et `PROXIES_DE_CONFIANCE`) |
|---|---|
| `app-beacom-utilisateurs` | `DATABASE_URL` (db_utilisateurs), `JWT_EXPIRE_MINUTES`, `INTERNAL_API_KEY` ; facultatifs, pour un compte de démonstration : `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_ORGANISATION` |
| `app-beacom-etablissements` | `DATABASE_URL` (db_etablissements), `INTERNAL_API_KEY` |
| `app-beacom-collecte` | voir ci-dessus |
| `app-beacom-analyses` | `DATABASE_URL` (db_analyses), `INTERNAL_API_KEY` |

### Frontend (Next.js, Node 20)

Même plan App Service que les API. Le workflow publie un paquet déjà construit (`.next/standalone`) : pas de build côté
Azure. Les URLs des services ne sont lues que par le serveur Next.js (passerelle `app/api/...`).

```bash
az webapp create -g $RG -p plan-beacom -n app-beacom-frontend --runtime "NODE:20-lts"
az webapp update -g $RG -n app-beacom-frontend --https-only true
az webapp config set -g $RG -n app-beacom-frontend --startup-file "node server.js"
az webapp config appsettings set -g $RG -n app-beacom-frontend --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=false NODE_ENV=production \
  UTILISATEURS_API_URL="https://app-beacom-utilisateurs.azurewebsites.net" \
  ETABLISSEMENTS_API_URL="https://app-beacom-etablissements.azurewebsites.net" \
  COLLECTE_API_URL="https://app-beacom-collecte.azurewebsites.net" \
  ANALYSES_API_URL="https://app-beacom-analyses.azurewebsites.net"
```

Le navigateur ne parle qu'au frontend : `ALLOWED_ORIGINS` des API peut rester vide (pas d'appel direct du navigateur
vers les services, donc pas de CORS). `PROXIES_DE_CONFIANCE=2` sur les 4 API (frontal App Service + passerelle).
Cinq applications partagent le plan B1 (1,75 Go de mémoire) : suffisant pour la démonstration.

## 4. Azure Function (FaaS)

```bash
az functionapp create -g $RG -n func-beacom-nlp --storage-account <STORAGE> \
  --consumption-plan-location francecentral --os-type Linux \
  --runtime python --runtime-version 3.11 --functions-version 4

az functionapp config appsettings set -g $RG -n func-beacom-nlp --settings \
  LANGUAGE_ENDPOINT="<ENDPOINT>" LANGUAGE_KEY="<CLE>" INTERNAL_API_KEY="<CLE_INTERNE>" \
  ANALYSES_API_URL="https://app-beacom-analyses.azurewebsites.net" \
  COLLECTE_API_URL="https://app-beacom-collecte.azurewebsites.net" \
  UTILISATEURS_API_URL="https://app-beacom-utilisateurs.azurewebsites.net" \
  ETABLISSEMENTS_API_URL="https://app-beacom-etablissements.azurewebsites.net" \
  SEUIL_ALERTE=0.8 FRONTEND_URL="https://<URL_FRONTEND>"
```

**Lancer le rapport hebdomadaire à la demande** (démonstration, sans attendre lundi) : appel de l'API d'administration
de la Function avec la clé maître (secret : ne pas la commiter).

```bash
CLE_MAITRE=$(az functionapp keys list -g $RG -n func-beacom-nlp --query masterKey -o tsv)
curl -s -X POST https://func-beacom-nlp.azurewebsites.net/admin/functions/rapport_hebdomadaire \
  -H "x-functions-key: $CLE_MAITRE" -H 'Content-Type: application/json' -d '{}'
```

**E-mails d'alerte (facultatif)** : Azure Communication Services avec un domaine géré par Azure. Sans ces paramètres,
les alertes sont enregistrées et journalisées, sans e-mail.

```bash
az extension add --name communication
az communication create -g $RG -n acs-beacom --location global --data-location Europe
az communication email create -g $RG -n email-beacom --location global --data-location Europe
az communication email domain create -g $RG --email-service-name email-beacom -n AzureManagedDomain \
  --location global --domain-management AzureManaged
# Relier le domaine à la ressource ACS (portail : Communication Services > Email > Domaines connectés), puis :
az communication list-key -g $RG -n acs-beacom --query primaryConnectionString -o tsv
az functionapp config appsettings set -g $RG -n func-beacom-nlp --settings \
  ACS_CONNECTION_STRING="<CHAINE_ACS>" ACS_EXPEDITEUR="DoNotReply@<domaine>.azurecomm.net"
```

La Function utilise le compte de stockage pour sa file (`AzureWebJobsStorage` est défini à la création).
Si elle doit lire une file d'un autre compte, ajoutez ce paramètre à la main.

## 5. GitHub Actions

Dans le dépôt : *Settings -> Secrets and variables -> Actions*, ajoutez les profils de publication
(`az webapp deployment list-publishing-profiles -g $RG -n <app> --xml`) :

`AZURE_PUBLISH_PROFILE_UTILISATEURS`, `AZURE_PUBLISH_PROFILE_ETABLISSEMENTS`, `AZURE_PUBLISH_PROFILE_COLLECTE`,
`AZURE_PUBLISH_PROFILE_ANALYSES`, `AZURE_PUBLISH_PROFILE_FRONTEND`, `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`.

Protégez la branche `main` (*Settings -> Branches*) : pull request et vérifications obligatoires.
Les profils de publication sont des secrets : ne les collez jamais ailleurs que dans GitHub.

## 6. Tests après déploiement et scénario de démonstration

```bash
U=https://app-beacom-utilisateurs.azurewebsites.net
E=https://app-beacom-etablissements.azurewebsites.net
C=https://app-beacom-collecte.azurewebsites.net
A=https://app-beacom-analyses.azurewebsites.net

# 1. Inscription d'un client (organisation + admin), qui renvoie directement un jeton
TOKEN=$(curl -s -X POST $U/auth/inscription -H 'Content-Type: application/json' \
  -d '{"organisation":"Café Atlas","email":"gerant@atlas.ma","mot_de_passe":"<MOT_DE_PASSE_LONG>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
# Connexions suivantes : POST $U/auth/login avec {"email":..., "mot_de_passe":...}

# 2. Créer un établissement (service-etablissements -> db_etablissements)
curl -s -X POST $E/etablissements -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"nom":"Café Atlas","categorie":"restaurant","ville":"Casablanca"}'

# 3. Enregistrer un avis (service-collecte -> REST vers etablissements -> db_collecte -> file)
curl -s -X POST $C/avis -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"etablissement_id":1,"texte":"Service très rapide et plats délicieux, je recommande.","langue":"fr","note":5}'

# 4. Après quelques secondes : la Function a analysé l'avis
curl -s $A/analyses/avis/1 -H "Authorization: Bearer $TOKEN"
curl -s "$A/analyses/resume?etablissement_id=1" -H "Authorization: Bearer $TOKEN"
curl -s "$A/analyses/tendance?periode=jour" -H "Authorization: Bearer $TOKEN"
curl -s "$A/analyses/themes?sentiment=negative" -H "Authorization: Bearer $TOKEN"
curl -s $A/analyses/alertes -H "Authorization: Bearer $TOKEN"   # l'avis « café froid » du 4 bis
curl -s $A/analyses/rapports -H "Authorization: Bearer $TOKEN"   # après le lundi, ou après un lancement à la demande
curl -s "$C/avis?etablissement_id=1" -H "Authorization: Bearer $TOKEN"   # statut passé à « analyse »

# 4 bis. Dépôt public par un client final, sans compte (jeton_public renvoyé à la création de l'établissement)
JETON=$(curl -s $E/etablissements/1 -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["jeton_public"])')
curl -s $E/public/etablissements/$JETON
curl -s -X POST $C/public/avis/$JETON -H 'Content-Type: application/json' \
  -d '{"texte":"Attente très longue et café froid.","note":1}'

# 4 ter. Import CSV
printf 'texte;note\nTrès bon accueil;5\nService lent;2\n' > avis.csv
curl -s -X POST "$C/avis/import?etablissement_id=1" -H "Authorization: Bearer $TOKEN" -F fichier=@avis.csv

# 5. Isolation : un second client ne voit pas les données du premier (404)
TOKEN2=$(curl -s -X POST $U/auth/inscription -H 'Content-Type: application/json' \
  -d '{"organisation":"Concurrent","email":"autre@exemple.ma","mot_de_passe":"<MOT_DE_PASSE_LONG>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -o /dev/null -w '%{http_code}\n' $E/etablissements/1 -H "Authorization: Bearer $TOKEN2"   # 404
```

À montrer à l'oral : la connexion, l'appel du microservice, l'écriture en base, l'exécution de la Function (onglet *Monitor* de la
Function App), les ressources dans le groupe `rg-beacom-prod`, et les journaux (*Log stream* des App Service).
Prévoyez des captures d'écran ou une vidéo de secours.

## 7. Observabilité (voir `06-observabilite.md`)

Commandes à lancer une fois les ressources créées (non exécutées par l'équipe de développement : à valider avant).

```bash
# Espace Log Analytics (rétention 30 jours) et Application Insights adossé
az monitor log-analytics workspace create -g $RG -n log-beacom --location francecentral --retention-time 30
WS=$(az monitor log-analytics workspace show -g $RG -n log-beacom --query id -o tsv)
az monitor app-insights component create -g $RG --app appi-beacom -l francecentral --workspace $WS
APPI=$(az monitor app-insights component show -g $RG --app appi-beacom --query id -o tsv)
CS=$(az monitor app-insights component show -g $RG --app appi-beacom --query connectionString -o tsv)

# Activation dans les 4 API, le frontend et la Function
for a in utilisateurs etablissements collecte analyses frontend; do
  az webapp config appsettings set -g $RG -n app-beacom-$a --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$CS"
done
az functionapp config appsettings set -g $RG -n func-beacom-nlp --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$CS"

# Groupe d'actions : e-mail à l'équipe
az monitor action-group create -g $RG -n ag-beacom --short-name beacom --action email equipe <EMAIL_EQUIPE>
AG=$(az monitor action-group show -g $RG -n ag-beacom --query id -o tsv)

# Tests de disponibilité sur /health (toutes les 5 min, France Central + Europe de l'Ouest)
for a in utilisateurs etablissements collecte analyses; do
  az monitor app-insights web-test create -g $RG -n dispo-$a -l francecentral --web-test-kind standard \
    --defined-web-test-name dispo-$a --frequency 300 --timeout 30 --enabled true --retry-enabled false \
    --locations Id=emea-fr-pra-edge --locations Id=emea-nl-ams-azr \
    --request-url https://app-beacom-$a.azurewebsites.net/health --expected-status-code 200 \
    --tags "hidden-link:$APPI=Resource"
done

# Alerte 1 : /health échoue 2 fois de suite
az monitor scheduled-query create -g $RG -n alerte-indisponible --scopes $APPI --severity 1 \
  --evaluation-frequency 5m --window-size 10m --action-groups $AG \
  --condition "count 'Q1' >= 2" \
  --condition-query Q1="availabilityResults | where success == false | summarize n = count() by name | where n >= 2"

# Alerte 2 : plus de 5 % de 5xx sur 10 minutes (au moins 20 requêtes)
az monitor scheduled-query create -g $RG -n alerte-5xx --scopes $APPI --severity 2 \
  --evaluation-frequency 5m --window-size 10m --action-groups $AG \
  --condition "count 'Q2' > 0" \
  --condition-query Q2="requests | summarize total = count(), e = countif(toint(resultCode) >= 500) by cloud_RoleName | where total >= 20 and 100.0 * e / total > 5"

# Alerte 3 : au moins 1 message en poison queue
az monitor scheduled-query create -g $RG -n alerte-poison --scopes $APPI --severity 2 \
  --evaluation-frequency 5m --window-size 5m --action-groups $AG \
  --condition "count 'Q3' > 0" --condition-query Q3="traces | where message has 'avis-a-analyser-poison'"

# Alerte 4 : 80 % du budget mensuel (montant : voir 04-finops.md)
SUB=$(az account show --query id -o tsv)
az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Consumption/budgets/budget-beacom?api-version=2023-05-01" \
  --body '{"properties":{"category":"Cost","amount":<BUDGET_USD>,"timeGrain":"Monthly",
    "timePeriod":{"startDate":"<AAAA-MM-01>"},
    "notifications":{"reel-80":{"enabled":true,"operator":"GreaterThanOrEqualTo","threshold":80,
      "thresholdType":"Actual","contactEmails":["<EMAIL_EQUIPE>"]}}}}'
```
