"""Dépôt d'avis public (lien / QR code) et import CSV dans service-collecte."""
import pytest
from conftest import entete
from test_api import FileFactice

import main

JETON = "a" * 32
ETABLISSEMENTS = {JETON: {"id": 10, "organisation_id": 1, "nom": "Café Atlas"}}
PLANS = {1: "entreprise", 3: "gratuit"}


@pytest.fixture
def file(monkeypatch):
    f = FileFactice()
    monkeypatch.setattr(main, "get_queue", lambda: f)
    return f


@pytest.fixture(autouse=True)
def services(monkeypatch):
    """Simule service-etablissements et service-utilisateurs derrière appel_get."""
    appels = []

    def appel_get(url, headers, service):
        appels.append((url, headers))
        if "/interne/etablissements/par-jeton/" in url:
            return ETABLISSEMENTS.get(url.rsplit("/", 1)[1])
        if "/interne/organisations/" in url:
            org = int(url.rsplit("/", 1)[1])
            return {"id": org, "plan": PLANS[org]} if org in PLANS else None
        if "/etablissements/" in url:  # vérification avec le jeton utilisateur
            return {"id": int(url.rsplit("/", 1)[1])} if url.endswith("/10") else None
        raise AssertionError(url)

    monkeypatch.setattr(main, "ETABLISSEMENTS_API_URL", "http://etablissements.test")
    monkeypatch.setattr(main, "UTILISATEURS_API_URL", "http://utilisateurs.test")
    monkeypatch.setattr(main, "appel_get", appel_get)
    return appels


def deposer(client, jeton=JETON, ip="203.0.113.1", **corps):
    corps = {"texte": "Thé à la menthe parfait", "note": 5, **corps}
    return client.post(f"/public/avis/{jeton}", json=corps, headers={"X-Forwarded-For": ip})


def test_depot_public(client, file, sql, services):
    r = deposer(client)
    assert r.status_code == 201 and r.json() == {"statut": "recu"}
    assert sql.execute("SELECT organisation_id, etablissement_id, note, source, statut FROM avis").fetchall() == [
        (1, 10, 5, "lien_public", "en_file")
    ]
    assert file.messages[0]["organisation_id"] == 1
    # Les appels internes portent la clé interne.
    assert all(h.get("X-API-Key") == "cle-interne-de-test" for url, h in services if "/interne/" in url)


def test_jeton_inconnu(client, file):
    assert deposer(client, jeton="b" * 32).status_code == 404
    assert deposer(client, jeton="pas-un-jeton!").status_code == 404
    assert file.messages == []


def test_champ_piege_rien_enregistre(client, file, sql):
    r = deposer(client, site_web="http://spam.example")
    assert r.status_code == 201 and r.json() == {"statut": "recu"}
    assert sql.execute("SELECT COUNT(*) FROM avis").fetchone() == (0,)
    assert file.messages == []


@pytest.mark.parametrize(
    "corps",
    [
        {"note": 6},
        {"note": None},
        {"texte": "ok"},
        {"texte": "x" * 2001},
        {"langue": "français"},
        {"organisation_id": 2},  # champ inconnu refusé : impossible de forcer une organisation
    ],
)
def test_validation_stricte(client, file, corps):
    assert deposer(client, **corps).status_code == 422


def test_texte_nettoye(client, file, sql):
    deposer(client, texte="   Très bon couscous   ")
    assert sql.execute("SELECT texte FROM avis").fetchone() == ("Très bon couscous",)


def test_limitation_de_debit(client, file):
    for _ in range(10):
        assert deposer(client, ip="203.0.113.50").status_code == 201
    assert deposer(client, ip="203.0.113.50").status_code == 429
    assert deposer(client, ip="203.0.113.51").status_code == 201


def test_quota_du_plan_applique_au_depot_public(client, file, sql, monkeypatch):
    monkeypatch.setitem(ETABLISSEMENTS, "c" * 32, {"id": 30, "organisation_id": 3, "nom": "Petit café"})
    sql.execute("INSERT INTO avis (organisation_id, etablissement_id, texte) SELECT 3, 30, 'x' FROM generate_series(1, 100)")
    assert deposer(client, jeton="c" * 32).status_code == 402


CSV_OK = "﻿texte;note;auteur\nTrès bon accueil;5;Sara\nAttente trop longue;2;\n".encode()


def importer(client, contenu, h=None, etablissement_id=10):
    return client.post(
        f"/avis/import?etablissement_id={etablissement_id}",
        headers=h or entete(1),
        files={"fichier": ("avis.csv", contenu, "text/csv")},
    )


def test_import_csv_point_virgule_et_bom(client, file, sql):
    r = importer(client, CSV_OK)
    assert r.status_code == 201 and r.json() == {"importes": 2}
    assert sql.execute("SELECT texte, note, auteur, source, statut FROM avis ORDER BY id").fetchall() == [
        ("Très bon accueil", 5, "Sara", "import_csv", "en_file"),
        ("Attente trop longue", 2, None, "import_csv", "en_file"),
    ]
    assert len(file.messages) == 2


def test_import_csv_virgule(client, file):
    assert importer(client, b"texte,note\nBien,4\n").json() == {"importes": 1}


def test_import_tout_ou_rien(client, file, sql):
    r = importer(client, "texte;note\nBien;4\n;3\nCorrect;9\n".encode())
    assert r.status_code == 422
    assert [e["ligne"] for e in r.json()["detail"]["erreurs"]] == [3, 4]
    assert sql.execute("SELECT COUNT(*) FROM avis").fetchone() == (0,)


def test_import_refus(client, file):
    assert importer(client, b"commentaire\nBien\n").status_code == 422  # colonne texte absente
    assert importer(client, b"texte\n").status_code == 422  # vide
    assert importer(client, "texte\nBien\n".encode("utf-16")).status_code == 422  # encodage
    assert importer(client, b"texte\n" + b"Bien\n" * 1001).status_code == 422
    assert importer(client, b"texte\n" + b"x" * 1_000_001).status_code == 413
    assert importer(client, CSV_OK, h=entete(1, role="lecteur")).status_code == 403
    # Établissement inconnu ou d'une autre organisation : service-etablissements répond 404.
    assert importer(client, CSV_OK, etablissement_id=99).status_code == 422
    assert file.messages == []


def test_import_au_dela_du_quota(client, file, sql):
    sql.execute("INSERT INTO avis (organisation_id, etablissement_id, texte) SELECT 3, 10, 'x' FROM generate_series(1, 99)")
    r = importer(client, CSV_OK, h=entete(3, plan="gratuit"))
    assert r.status_code == 402 and "99 déjà collectés" in r.json()["detail"]
    assert sql.execute("SELECT COUNT(*) FROM avis WHERE organisation_id = 3").fetchone() == (99,)
