"""Route interne des organisations, limitation de débit et calcul de l'IP client."""
from types import SimpleNamespace

from conftest import CLE, entete

import auth


def test_route_interne_organisation(client):
    r = client.post(
        "/auth/inscription", json={"organisation": "Café Atlas", "email": "a@atlas.ma", "mot_de_passe": "MotDePasse!123"}
    )
    org_id = r.json()["organisation_id"]
    assert client.get(f"/interne/organisations/{org_id}").status_code == 401
    assert client.get(f"/interne/organisations/{org_id}", headers=entete(org_id)).status_code == 401
    assert client.get(f"/interne/organisations/{org_id}", headers=CLE).json() == {"id": org_id, "plan": "gratuit"}
    assert client.get("/interne/organisations/999", headers=CLE).status_code == 404


def test_connexion_limitee_par_ip(client):
    corps = {"email": "x@y.ma", "mot_de_passe": "faux"}
    for _ in range(10):
        assert client.post("/auth/login", json=corps, headers={"X-Forwarded-For": "198.51.100.7"}).status_code == 401
    assert client.post("/auth/login", json=corps, headers={"X-Forwarded-For": "198.51.100.7"}).status_code == 429
    assert client.post("/auth/login", json=corps, headers={"X-Forwarded-For": "198.51.100.8"}).status_code == 401


def test_inscription_limitee_par_ip(client):
    h = {"X-Forwarded-For": "198.51.100.9"}
    for i in range(5):
        corps = {"organisation": f"Org {i}", "email": f"a{i}@x.ma", "mot_de_passe": "MotDePasse!123"}
        assert client.post("/auth/inscription", json=corps, headers=h).status_code == 201
    corps = {"organisation": "Org 6", "email": "a6@x.ma", "mot_de_passe": "MotDePasse!123"}
    assert client.post("/auth/inscription", json=corps, headers=h).status_code == 429


def requete(xff=None, hote="10.0.0.1"):
    return SimpleNamespace(headers={"x-forwarded-for": xff} if xff else {}, client=SimpleNamespace(host=hote))


def test_ip_client(monkeypatch):
    assert auth.ip_client(requete()) == "10.0.0.1"
    assert auth.ip_client(requete("203.0.113.5:51234")) == "203.0.113.5"
    # Une entrée ajoutée par le client à gauche est ignorée : on lit celle du proxy de confiance.
    assert auth.ip_client(requete("1.1.1.1, 203.0.113.5")) == "203.0.113.5"
    monkeypatch.setenv("PROXIES_DE_CONFIANCE", "2")  # derrière la passerelle Next.js
    assert auth.ip_client(requete("1.1.1.1, 203.0.113.5, 10.1.0.4")) == "203.0.113.5"
    assert auth.ip_client(requete("203.0.113.5")) == "203.0.113.5"
    assert auth.ip_client(requete("2001:db8::1")) == "2001:db8::1"
