"""Isolation des organisations dans service-analyses."""
from conftest import CLE, entete

A, B = entete(1), entete(2)


def resultat(avis_id, organisation_id, sentiment="positive"):
    return {
        "avis_id": avis_id,
        "organisation_id": organisation_id,
        "sentiment": sentiment,
        "score_positif": 0.9,
        "score_neutre": 0.05,
        "score_negatif": 0.05,
    }


def test_route_interne_protegee_par_cle(client):
    assert client.post("/analyses/interne", json=resultat(1, 1)).status_code == 401
    assert client.post("/analyses/interne", headers=A, json=resultat(1, 1)).status_code == 401
    assert client.post("/analyses/interne", headers=CLE, json=resultat(1, 1)).status_code == 201


def test_organisation_obligatoire(client):
    corps = resultat(1, 1)
    del corps["organisation_id"]
    assert client.post("/analyses/interne", headers=CLE, json=corps).status_code == 422


def test_ecriture_idempotente(client, sql):
    client.post("/analyses/interne", headers=CLE, json=resultat(1, 1, "positive"))
    client.post("/analyses/interne", headers=CLE, json=resultat(1, 1, "negative"))
    assert sql.execute("SELECT sentiment FROM analyses_sentiment").fetchall() == [("negative",)]


def test_organisation_b_ne_voit_pas_les_analyses_de_a(client):
    client.post("/analyses/interne", headers=CLE, json=resultat(1, 1, "positive"))
    client.post("/analyses/interne", headers=CLE, json=resultat(2, 1, "negative"))
    client.post("/analyses/interne", headers=CLE, json=resultat(3, 2, "negative"))

    assert client.get("/analyses/avis/1", headers=A).status_code == 200
    assert client.get("/analyses/avis/1", headers=B).status_code == 404
    assert {a["avis_id"] for a in client.get("/analyses", headers=A).json()} == {1, 2}
    assert [a["avis_id"] for a in client.get("/analyses?sentiment=negative", headers=B).json()] == [3]
    assert sorted((r["sentiment"], r["total"]) for r in client.get("/analyses/resume", headers=A).json()) == [
        ("negative", 1),
        ("positive", 1),
    ]
    assert client.get("/analyses/resume", headers=entete(3)).json() == []


def test_authentification_requise(client):
    assert client.get("/analyses/resume").status_code == 401
