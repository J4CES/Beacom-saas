"""Corrélation X-Request-ID, /health/db et activation conditionnelle d'Application Insights (auth.py commun)."""
import logging
import sys
import types

import auth


def test_identifiant_genere_et_renvoye(client):
    r = client.get("/health")
    assert len(r.headers["X-Request-ID"]) == 32
    assert client.get("/health").headers["X-Request-ID"] != r.headers["X-Request-ID"]


def test_identifiant_recu_conserve_ou_remplace_s_il_est_invalide(client):
    assert client.get("/health", headers={"X-Request-ID": "passerelle-1234abcd"}).headers["X-Request-ID"] == "passerelle-1234abcd"
    remplace = client.get("/health", headers={"X-Request-ID": "<script>"}).headers["X-Request-ID"]
    assert remplace != "<script>" and len(remplace) == 32


def test_identifiant_dans_le_journal_d_acces(client, caplog):
    with caplog.at_level(logging.INFO, logger="access"):
        client.get("/health", headers={"X-Request-ID": "trace-abcdef12"})
    assert any(getattr(r, "request_id", None) == "trace-abcdef12" for r in caplog.records if r.name == "access")


def test_health_db(client):
    r = client.get("/health/db")
    assert r.status_code == 200 and r.json()["db"] == "ok"


def test_health_db_base_injoignable(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    auth.configurer(app, "postgresql://personne:faux@127.0.0.1:1/aucune")
    r = TestClient(app).get("/health/db")
    assert r.status_code == 503 and r.json() == {"status": "erreur", "db": "injoignable"}
    assert TestClient(app).get("/health").status_code == 404  # /health reste défini par chaque service


def test_application_insights_inactif_sans_chaine_de_connexion(monkeypatch):
    from fastapi import FastAPI

    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert auth.activer_application_insights(FastAPI()) is False


def test_application_insights_actif_avec_chaine_de_connexion(monkeypatch):
    from fastapi import FastAPI

    appels = []
    faux = types.ModuleType("azure.monitor.opentelemetry")
    faux.configure_azure_monitor = lambda **kw: appels.append(("azure", kw))
    monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", faux)
    import opentelemetry.instrumentation.fastapi as instr

    monkeypatch.setattr(instr.FastAPIInstrumentor, "instrument_app", staticmethod(lambda app, **kw: appels.append(("fastapi", app.title))))
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    assert auth.activer_application_insights(FastAPI(title="service-test")) is True
    assert appels == [("azure", {"logger_name": ""}), ("fastapi", "service-test")]
    import os

    assert os.environ["OTEL_SERVICE_NAME"] == "service-test"
