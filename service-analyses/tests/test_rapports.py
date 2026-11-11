"""Rapports hebdomadaires : calcul interne idempotent et lecture par l'organisation."""
from datetime import date, timedelta

from conftest import CLE, entete
from test_tableau_de_bord import analyser

A, B = entete(1), entete(2)
LUNDI = date(2026, 11, 2)


def le(jour: date) -> str:
    return jour.isoformat() + "T10:00:00+00:00"


def preparer(client):
    # Semaine du 2 novembre : 3 avis pour l'organisation 1 (2 au café 10, 1 au café 11).
    analyser(client, 1, sentiment="negative", etab=10, date_avis=le(LUNDI), mots_cles=["attente", "prix"])
    analyser(client, 2, sentiment="positive", etab=10, date_avis=le(LUNDI + timedelta(days=3)))
    analyser(client, 3, sentiment="negative", etab=11, date_avis=le(LUNDI + timedelta(days=6)), mots_cles=["attente"])
    # Semaine précédente : 1 avis positif.
    analyser(client, 4, sentiment="positive", etab=10, date_avis=le(LUNDI - timedelta(days=2)))
    # Semaine suivante : ne compte pas.
    analyser(client, 5, sentiment="negative", etab=10, date_avis=le(LUNDI + timedelta(days=7)), mots_cles=["bruit"])
    # Autre organisation, même semaine.
    analyser(client, 6, org=2, sentiment="positive", date_avis=le(LUNDI + timedelta(days=1)))


def generer(client, semaine=LUNDI):
    r = client.post(f"/analyses/interne/rapports-hebdomadaires?semaine_debut={semaine}", headers=CLE)
    assert r.status_code == 200, r.text
    return r.json()


def test_contenu_du_rapport(client):
    preparer(client)
    rapports = {r["organisation_id"]: r["contenu"] for r in generer(client)["rapports"]}
    assert set(rapports) == {1, 2}
    c = rapports[1]
    assert (c["semaine_debut"], c["semaine_fin"]) == ("2026-11-02", "2026-11-08")
    assert c["total"] == 3 and c["par_sentiment"]["negative"] == 2 and c["part_negative"] == 0.667
    assert c["semaine_precedente"]["total"] == 1 and c["semaine_precedente"]["part_negative"] == 0.0
    assert c["themes_negatifs"] == [{"mot_cle": "attente", "total": 2}, {"mot_cle": "prix", "total": 1}]
    assert c["etablissements"] == [
        {"etablissement_id": 10, "total": 2, "negative": 1},
        {"etablissement_id": 11, "total": 1, "negative": 1},
    ]


def test_idempotent_et_lisible_par_la_seule_organisation(client, sql):
    preparer(client)
    generer(client)
    generer(client)
    assert sql.execute("SELECT COUNT(*) FROM rapports").fetchone() == (2,)
    (rapport,) = client.get("/analyses/rapports", headers=A).json()
    assert rapport["semaine_debut"] == "2026-11-02" and rapport["contenu"]["total"] == 3
    assert [r["contenu"]["total"] for r in client.get("/analyses/rapports", headers=B).json()] == [1]
    assert client.get("/analyses/rapports", headers=entete(3)).json() == []


def test_semaine_par_defaut_et_controles(client):
    aujourd_hui = date.today()
    lundi_dernier = aujourd_hui - timedelta(days=aujourd_hui.weekday() + 7)
    assert client.post("/analyses/interne/rapports-hebdomadaires", headers=CLE).json() == {
        "semaine_debut": lundi_dernier.isoformat(),
        "rapports": [],
    }
    assert client.post("/analyses/interne/rapports-hebdomadaires").status_code == 401
    assert client.post("/analyses/interne/rapports-hebdomadaires?semaine_debut=2026-11-04", headers=CLE).status_code == 422
