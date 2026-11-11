"""Isolation des organisations et limites de plan dans service-etablissements."""
from conftest import entete

A, B = entete(1), entete(2)


def creer(client, h, nom="Café Atlas", **extra):
    return client.post("/etablissements", headers=h, json={"nom": nom, "ville": "Casablanca", **extra})


def test_organisation_b_ne_voit_pas_les_etablissements_de_a(client):
    etab = creer(client, A).json()
    assert etab["organisation_id"] == 1
    assert client.get(f"/etablissements/{etab['id']}", headers=A).status_code == 200
    assert client.get(f"/etablissements/{etab['id']}", headers=B).status_code == 404
    assert client.get("/etablissements", headers=B).json() == []
    assert client.delete(f"/etablissements/{etab['id']}", headers=B).status_code == 404
    assert client.delete(f"/etablissements/{etab['id']}", headers=A).status_code == 204


def test_filtre_ville_reste_dans_l_organisation(client):
    creer(client, A, "Atlas")
    creer(client, B, "Concurrent")
    assert [e["nom"] for e in client.get("/etablissements?ville=Casablanca", headers=B).json()] == ["Concurrent"]


def test_source_id_unique_par_organisation(client):
    assert creer(client, A, source_id="g-123").status_code == 201
    assert creer(client, B, source_id="g-123").status_code == 201
    assert creer(client, A, "Doublon", source_id="g-123").status_code == 409


def test_plan_gratuit_limite_a_un_etablissement(client):
    h = entete(3, plan="gratuit")
    assert creer(client, h).status_code == 201
    r = creer(client, h, "Deuxième")
    assert r.status_code == 402
    assert "limité à 1" in r.json()["detail"]


def test_plan_pro_limite_a_cinq(client):
    h = entete(4, plan="pro")
    for i in range(5):
        assert creer(client, h, f"Café {i}").status_code == 201
    assert creer(client, h, "Sixième").status_code == 402


def test_plan_entreprise_illimite(client):
    h = entete(5, plan="entreprise")
    for i in range(7):
        assert creer(client, h, f"Café {i}").status_code == 201


def test_roles(client):
    assert creer(client, entete(1, role="lecteur")).status_code == 403
    etab = creer(client, entete(1, role="gestionnaire")).json()
    assert client.delete(f"/etablissements/{etab['id']}", headers=entete(1, role="gestionnaire")).status_code == 403


def test_authentification_requise(client):
    assert client.get("/etablissements").status_code == 401
