"""Isolation des organisations, limite mensuelle et ordre base -> file dans service-collecte."""
import io
import json
import os
import urllib.error

import psycopg
import pytest

import main
from conftest import CLE, entete

A, B = entete(1), entete(2)


class FileFactice:
    """Remplace la file Azure. `a_l_envoi` simule ce que ferait la Function à la réception du message."""

    def __init__(self, a_l_envoi=None, echec=False):
        self.messages, self.a_l_envoi, self.echec = [], a_l_envoi, echec

    def send_message(self, contenu):
        if self.echec:
            raise RuntimeError("file indisponible")
        message = json.loads(contenu)
        if self.a_l_envoi:
            self.a_l_envoi(message)
        self.messages.append(message)


@pytest.fixture
def file(monkeypatch):
    f = FileFactice()
    monkeypatch.setattr(main, "get_queue", lambda: f)
    return f


def deposer(client, h, etablissement_id=10, texte="Très bon accueil"):
    return client.post("/avis", headers=h, json={"etablissement_id": etablissement_id, "texte": texte, "langue": "fr"})


def test_message_de_file_porte_l_organisation(client, file):
    r = deposer(client, A)
    assert r.status_code == 201 and r.json()["statut"] == "en_file"
    assert file.messages == [
        {
            "avis_id": r.json()["id"],
            "organisation_id": 1,
            "etablissement_id": 10,
            "texte": "Très bon accueil",
            "langue": "fr",
            "date_avis": None,
            "request_id": r.headers["X-Request-ID"],
        }
    ]


def test_message_porte_la_date_d_un_avis_ancien(client, file):
    corps = {"etablissement_id": 10, "texte": "Bien", "date_avis": "2026-03-01T12:00:00+00:00"}
    assert client.post("/avis", headers=A, json=corps).status_code == 201
    assert file.messages[0]["date_avis"].startswith("2026-03-01T12:00:00")


def test_organisation_b_ne_voit_pas_les_avis_de_a(client, file):
    avis_id = deposer(client, A).json()["id"]
    assert client.get(f"/avis/{avis_id}", headers=A).status_code == 200
    assert client.get(f"/avis/{avis_id}", headers=B).status_code == 404
    assert client.get("/avis", headers=B).json() == []
    assert client.get("/avis?etablissement_id=10", headers=B).json() == []
    assert [a["id"] for a in client.get("/avis?etablissement_id=10", headers=A).json()] == [avis_id]


def test_avis_valide_en_base_avant_l_envoi_en_file(client, monkeypatch):
    """Correctif : la Function doit trouver l'avis dès qu'elle reçoit le message."""
    vus = []

    def comme_la_function(message):
        with psycopg.connect(os.environ["DATABASE_URL"]) as autre_connexion:
            vus.append(autre_connexion.execute("SELECT statut FROM avis WHERE id = %s", (message["avis_id"],)).fetchone())

    monkeypatch.setattr(main, "get_queue", lambda: FileFactice(a_l_envoi=comme_la_function))
    assert deposer(client, A).status_code == 201
    assert vus == [("nouveau",)]


def test_statut_analyse_non_ecrase_si_la_function_est_plus_rapide(client, monkeypatch, sql):
    def function_instantanee(message):
        r = client.patch(f"/avis/{message['avis_id']}/statut", headers=CLE, json={"statut": "analyse"})
        assert r.status_code == 200

    monkeypatch.setattr(main, "get_queue", lambda: FileFactice(a_l_envoi=function_instantanee))
    avis_id = deposer(client, A).json()["id"]
    assert sql.execute("SELECT statut FROM avis WHERE id = %s", (avis_id,)).fetchone() == ("analyse",)


def test_file_en_panne_puis_renvoi_limite_a_l_organisation(client, monkeypatch, sql):
    monkeypatch.setattr(main, "get_queue", lambda: FileFactice(echec=True))
    r = deposer(client, A)
    assert r.status_code == 502
    deposer(client, B)
    assert sql.execute("SELECT organisation_id, statut FROM avis ORDER BY id").fetchall() == [(1, "nouveau"), (2, "nouveau")]

    f = FileFactice()
    monkeypatch.setattr(main, "get_queue", lambda: f)
    assert client.post("/avis/renvoyer-nouveaux", headers=A).json() == {"envoyes": 1}
    assert [m["organisation_id"] for m in f.messages] == [1]
    assert sql.execute("SELECT organisation_id, statut FROM avis ORDER BY id").fetchall() == [(1, "en_file"), (2, "nouveau")]


def test_renvoi_garde_les_envois_reussis_en_cas_de_panne(client, monkeypatch, sql):
    sql.execute("INSERT INTO avis (organisation_id, etablissement_id, texte) VALUES (1, 10, 'a'), (1, 10, 'b')")

    class PanneAuDeuxieme(FileFactice):
        def send_message(self, contenu):
            if self.messages:
                raise RuntimeError("panne")
            super().send_message(contenu)

    monkeypatch.setattr(main, "get_queue", lambda: PanneAuDeuxieme())
    assert client.post("/avis/renvoyer-nouveaux", headers=A).status_code == 502
    assert sql.execute("SELECT statut FROM avis ORDER BY id").fetchall() == [("en_file",), ("nouveau",)]


def test_plan_gratuit_limite_a_100_avis_par_mois(client, file, sql):
    h = entete(3, plan="gratuit")
    sql.execute("INSERT INTO avis (organisation_id, etablissement_id, texte) SELECT 3, 10, 'x' FROM generate_series(1, 99)")
    # Un avis du mois dernier ne compte pas.
    sql.execute(
        "INSERT INTO avis (organisation_id, etablissement_id, texte, collecte_le) "
        "VALUES (3, 10, 'ancien', date_trunc('month', now()) - interval '1 day')"
    )
    assert deposer(client, h).status_code == 201
    r = deposer(client, h)
    assert r.status_code == 402 and "100 avis par mois" in r.json()["detail"]
    # La limite d'une organisation ne touche pas les autres.
    assert deposer(client, entete(4, plan="gratuit")).status_code == 201


def test_etablissement_d_une_autre_organisation_refuse(client, file, monkeypatch):
    """service-etablissements répond 404 pour un établissement d'une autre organisation."""

    def urlopen_404(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "introuvable", {}, io.BytesIO())

    monkeypatch.setattr(main, "ETABLISSEMENTS_API_URL", "http://etablissements.test")
    monkeypatch.setattr(main.urllib.request, "urlopen", urlopen_404)
    assert deposer(client, A).status_code == 422
    assert file.messages == []


def test_roles_et_cle_interne(client, file):
    assert deposer(client, entete(1, role="lecteur")).status_code == 403
    avis_id = deposer(client, A).json()["id"]
    assert client.patch(f"/avis/{avis_id}/statut", json={"statut": "analyse"}).status_code == 401
    assert client.patch(f"/avis/{avis_id}/statut", headers=A, json={"statut": "analyse"}).status_code == 401
    assert client.post("/avis/renvoyer-nouveaux", headers=entete(1, role="gestionnaire")).status_code == 403
