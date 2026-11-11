"""Jeton public, route publique et route interne de résolution dans service-etablissements."""
import re

from conftest import CLE, entete

A, B = entete(1), entete(2)


def creer(client, h=A, nom="Café Atlas"):
    r = client.post("/etablissements", headers=h, json={"nom": nom, "categorie": "café", "ville": "Rabat"})
    assert r.status_code == 201, r.text
    return r.json()


def test_jeton_public_aleatoire_et_unique(client):
    jetons = {creer(client, nom=f"Café {i}")["jeton_public"] for i in range(5)}
    assert len(jetons) == 5
    assert all(re.fullmatch(r"[0-9a-f]{32}", j) for j in jetons)


def test_route_publique_ne_revele_que_le_necessaire(client):
    etab = creer(client)
    r = client.get(f"/public/etablissements/{etab['jeton_public']}")
    assert r.status_code == 200
    assert r.json() == {"nom": "Café Atlas", "categorie": "café", "ville": "Rabat"}


def test_jeton_inconnu_ou_mal_forme(client):
    creer(client)
    assert client.get("/public/etablissements/" + "0" * 32).status_code == 404
    assert client.get("/public/etablissements/court").status_code == 404
    assert client.get("/public/etablissements/' OR 1=1 --xxxxxxxxxxx").status_code == 404


def test_route_interne_protegee_et_renvoie_l_organisation(client):
    etab = creer(client, entete(7))
    url = f"/interne/etablissements/par-jeton/{etab['jeton_public']}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=entete(7)).status_code == 401
    assert client.get(url, headers=CLE).json() == {"id": etab["id"], "organisation_id": 7, "nom": "Café Atlas"}


def test_regeneration_du_jeton(client):
    etab = creer(client)
    url = f"/etablissements/{etab['id']}/jeton-public"
    assert client.post(url, headers=B).status_code == 404
    assert client.post(url, headers=entete(1, role="gestionnaire")).status_code == 403
    nouveau = client.post(url, headers=A).json()["jeton_public"]
    assert nouveau != etab["jeton_public"]
    assert client.get(f"/public/etablissements/{etab['jeton_public']}").status_code == 404
    assert client.get(f"/public/etablissements/{nouveau}").status_code == 200


def test_limitation_de_debit_par_ip(client):
    jeton = creer(client)["jeton_public"]
    ip1, ip2 = {"X-Forwarded-For": "203.0.113.1"}, {"X-Forwarded-For": "203.0.113.2"}
    for _ in range(60):
        assert client.get(f"/public/etablissements/{jeton}", headers=ip1).status_code == 200
    r = client.get(f"/public/etablissements/{jeton}", headers=ip1)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert client.get(f"/public/etablissements/{jeton}", headers=ip2).status_code == 200


def test_route_interne_noms_des_etablissements(client):
    creer(client, A, "Café Atlas")
    creer(client, B, "Concurrent")
    assert client.get("/interne/organisations/1/etablissements").status_code == 401
    noms = client.get("/interne/organisations/1/etablissements", headers=CLE).json()
    assert [e["nom"] for e in noms] == ["Café Atlas"]
