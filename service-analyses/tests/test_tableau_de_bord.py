"""Analyses par établissement : résumé, tendance, thèmes, alertes."""
from datetime import date, timedelta

from conftest import CLE, entete
from test_api import resultat

A, B = entete(1), entete(2)


def analyser(client, avis_id, org=1, sentiment="positive", etab=10, **extra):
    r = client.post("/analyses/interne", headers=CLE, json=resultat(avis_id, org, sentiment, etab, **extra))
    assert r.status_code == 201, r.text
    return r.json()


def test_resume_par_etablissement(client):
    analyser(client, 1, sentiment="positive", etab=10)
    analyser(client, 2, sentiment="negative", etab=10)
    analyser(client, 3, sentiment="negative", etab=11)
    analyser(client, 4, org=2, sentiment="negative", etab=10)  # même numéro d'établissement, autre client
    total = {r["sentiment"]: r["total"] for r in client.get("/analyses/resume", headers=A).json()}
    assert total == {"negative": 2, "positive": 1}
    etab10 = {r["sentiment"]: r["total"] for r in client.get("/analyses/resume?etablissement_id=10", headers=A).json()}
    assert etab10 == {"negative": 1, "positive": 1}
    assert [a["avis_id"] for a in client.get("/analyses?etablissement_id=11", headers=A).json()] == [3]


def test_mots_cles_normalises_et_idempotents(client, sql):
    analyser(client, 1, sentiment="negative", mots_cles=["Attente", "attente", "  café   froid ", ""])
    analyser(client, 1, sentiment="negative", mots_cles=["Attente", "café froid"])  # message rejoué
    assert sql.execute("SELECT mot_cle FROM mots_cles ORDER BY mot_cle").fetchall() == [("attente",), ("café froid",)]
    assert client.get("/analyses/avis/1", headers=A).json()["mots_cles"] == ["attente", "café froid"]


def test_themes_negatifs(client):
    analyser(client, 1, sentiment="negative", mots_cles=["attente", "prix"])
    analyser(client, 2, sentiment="negative", mots_cles=["attente"])
    analyser(client, 3, sentiment="positive", mots_cles=["accueil", "attente"])
    analyser(client, 4, sentiment="negative", etab=11, mots_cles=["bruit"])
    analyser(client, 5, org=2, sentiment="negative", mots_cles=["attente", "attente2"])
    assert client.get("/analyses/themes", headers=A).json() == [
        {"mot_cle": "attente", "total": 2},
        {"mot_cle": "bruit", "total": 1},
        {"mot_cle": "prix", "total": 1},
    ]
    assert client.get("/analyses/themes?etablissement_id=11", headers=A).json() == [{"mot_cle": "bruit", "total": 1}]
    assert client.get("/analyses/themes?sentiment=positive&limit=1", headers=A).json() == [
        {"mot_cle": "accueil", "total": 1}
    ]
    assert client.get("/analyses/themes?sentiment=furieux", headers=A).status_code == 422


def test_tendance_par_semaine_et_par_jour(client):
    aujourd_hui = date.today()
    il_y_a_10_jours = (aujourd_hui - timedelta(days=10)).isoformat() + "T12:00:00+00:00"
    tres_ancien = (aujourd_hui - timedelta(days=400)).isoformat() + "T12:00:00+00:00"
    analyser(client, 1, sentiment="positive")
    analyser(client, 2, sentiment="negative")
    analyser(client, 3, sentiment="negative", date_avis=il_y_a_10_jours)  # avis importé : sa date compte
    analyser(client, 4, sentiment="negative", date_avis=tres_ancien)  # hors fenêtre
    analyser(client, 5, org=2, sentiment="negative")

    jours = client.get("/analyses/tendance?periode=jour&depuis_jours=30", headers=A).json()
    assert [(j["periode"], j["positive"], j["negative"], j["total"]) for j in jours] == [
        ((aujourd_hui - timedelta(days=10)).isoformat(), 0, 1, 1),
        (aujourd_hui.isoformat(), 1, 1, 2),
    ]
    semaines = client.get("/analyses/tendance", headers=A).json()
    lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    assert semaines[-1]["periode"] == lundi.isoformat()
    assert sum(s["total"] for s in semaines) == 3
    assert client.get("/analyses/tendance?periode=mois", headers=A).status_code == 422


def test_alertes(client):
    corps = {"avis_id": 1, "organisation_id": 1, "etablissement_id": 10, "score_negatif": 0.97, "extrait": "Horrible"}
    assert client.post("/analyses/interne/alertes", json=corps).status_code == 401
    assert client.post("/analyses/interne/alertes", headers=CLE, json=corps).json()["creee"] is True
    # Message rejoué : pas de seconde alerte (donc pas de second e-mail).
    assert client.post("/analyses/interne/alertes", headers=CLE, json=corps).json()["creee"] is False
    client.post("/analyses/interne/alertes", headers=CLE, json=corps | {"avis_id": 2, "organisation_id": 2})

    (alerte,) = client.get("/analyses/alertes", headers=A).json()
    assert alerte["extrait"] == "Horrible" and alerte["traitee"] is False
    assert client.patch(f"/analyses/alertes/{alerte['id']}", headers=B, json={"traitee": True}).status_code == 404
    assert client.patch(f"/analyses/alertes/{alerte['id']}", headers=entete(1, role="lecteur"), json={"traitee": True}).status_code == 403
    assert client.patch(f"/analyses/alertes/{alerte['id']}", headers=A, json={"traitee": True}).json()["traitee"] is True
    assert client.get("/analyses/alertes", headers=A).json() == []
    assert len(client.get("/analyses/alertes?traitee=true", headers=A).json()) == 1
