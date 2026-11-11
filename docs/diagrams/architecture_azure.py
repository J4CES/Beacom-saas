"""Diagramme Cloud de Beacom (bibliothèque `diagrams`, icônes Azure).

Regénérer depuis la racine du dépôt (Docker, rien à installer) :
    docker run --rm -v "$PWD/docs/diagrams":/d -w /d python:3.11-slim sh -c \\
      "apt-get update -qq && apt-get install -y -qq graphviz fonts-dejavu-core >/dev/null \\
       && pip install -q diagrams && python architecture_azure.py"
Produit architecture_azure.png à côté du script.
"""
from diagrams import Cluster, Diagram, Edge
from diagrams.azure.analytics import LogAnalyticsWorkspaces
from diagrams.azure.compute import VM, AppServices, FunctionApps
from diagrams.azure.devops import ApplicationInsights
from diagrams.azure.ml import CognitiveServices
from diagrams.azure.network import NetworkSecurityGroupsClassic, Subnets
from diagrams.azure.storage import QueuesStorage
from diagrams.azure.web import AppServicePlans
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users
from diagrams.onprem.database import Postgresql

attributs = {"fontsize": "20", "pad": "0.6", "splines": "spline", "nodesep": "0.7", "ranksep": "1.1"}

with Diagram("Beacom sur Azure (francecentral)", filename="architecture_azure", show=False,
             direction="LR", graph_attr=attributs, outformat="png"):
    clients = Users("Gérants et\nclients finaux\n(HTTPS)")
    ci = GithubActions("GitHub Actions\n(tests, déploiement)")

    with Cluster("Groupe de ressources rg-beacom-prod"):
        with Cluster("Réseau virtuel vm-beacom-dbVNET"):
            with Cluster("Sous-réseau snet-apps 10.0.1.0/24 (délégué à App Service)"):
                integration = Subnets("intégration VNet")
            with Cluster("Sous-réseau de la VM (sans IP publique)"):
                nsg = NetworkSecurityGroupsClassic("NSG : 5432 depuis\nsnet-apps seulement\naucun port Internet")
                vm = VM("vm-beacom-db\nUbuntu 22.04, B1s\nStandard SSD")
                pg = Postgresql("PostgreSQL 14\n4 bases (une par service)")
                vm - pg

        with Cluster("Plan App Service B1 Linux (PaaS)"):
            plan = AppServicePlans("plan-beacom")
            front = AppServices("app-beacom-frontend\nNext.js + passerelle d'API")
            api = [
                AppServices("utilisateurs"),
                AppServices("etablissements"),
                AppServices("collecte"),
                AppServices("analyses"),
            ]

        file = QueuesStorage("Storage : file\navis-a-analyser\n(+ poison)")
        func = FunctionApps("func-beacom-nlp (FaaS)\nanalyser_avis\nrapport_hebdomadaire")
        langue = CognitiveServices("Azure AI Language\nsentiment, mots-clés")

        with Cluster("Supervision"):
            appi = ApplicationInsights("Application Insights")
            logs = LogAnalyticsWorkspaces("Log Analytics\n(KQL, alertes)")
            appi >> logs

    clients >> Edge(label="HTTPS") >> front
    front >> Edge(label="REST + JWT") >> api
    plan - Edge(style="dotted") - front
    api[2] >> Edge(label="message", color="darkorange") >> file
    file >> Edge(label="déclencheur", color="darkorange") >> func
    func >> langue
    func >> Edge(label="REST (clé interne)", style="dashed") >> api[3]
    api >> Edge(label="SQL", color="firebrick") >> integration
    integration >> Edge(label="5432 privé", color="firebrick") >> nsg >> vm
    ci >> Edge(label="déploie", style="dashed") >> plan
    ci >> Edge(style="dashed") >> func
    [front, func] >> Edge(style="dotted", color="gray") >> appi
