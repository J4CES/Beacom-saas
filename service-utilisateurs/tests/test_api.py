"""Inscription, connexion et isolation des organisations dans service-utilisateurs."""
import jwt

from conftest import JWT_SECRET, entete


def inscrire(client, email, organisation="Café Atlas"):
    r = client.post(
        "/auth/inscription",
        json={"organisation": organisation, "email": email, "mot_de_passe": "MotDePasse!123"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_inscription_cree_organisation_gratuite_et_admin(client, sql):
    rep = inscrire(client, "Gerant@Atlas.ma")
    payload = jwt.decode(rep["access_token"], JWT_SECRET, algorithms=["HS256"])
    assert payload["role"] == "admin" and payload["plan"] == "gratuit"
    assert payload["org"] == rep["organisation_id"]
    org = sql.execute("SELECT nom, plan FROM organisations WHERE id = %s", (rep["organisation_id"],)).fetchone()
    assert org == ("Café Atlas", "gratuit")
    # L'e-mail est normalisé en minuscules.
    assert sql.execute("SELECT email FROM utilisateurs").fetchone() == ("gerant@atlas.ma",)


def test_inscription_email_deja_pris_sans_organisation_orpheline(client, sql):
    inscrire(client, "a@atlas.ma")
    r = client.post(
        "/auth/inscription", json={"organisation": "Autre", "email": "A@atlas.ma", "mot_de_passe": "MotDePasse!123"}
    )
    assert r.status_code == 409
    assert sql.execute("SELECT COUNT(*) FROM organisations").fetchone() == (1,)


def test_inscription_valide_les_champs(client):
    r = client.post("/auth/inscription", json={"organisation": "X", "email": "pas-un-email", "mot_de_passe": "court"})
    assert r.status_code == 422


def test_connexion_renvoie_organisation_et_plan(client):
    rep = inscrire(client, "a@atlas.ma")
    r = client.post("/auth/login", json={"email": "a@atlas.ma", "mot_de_passe": "MotDePasse!123"})
    assert r.status_code == 200
    assert r.json()["organisation_id"] == rep["organisation_id"] and r.json()["plan"] == "gratuit"
    me = client.get("/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).json()
    assert me["organisation_id"] == rep["organisation_id"] and me["plan"] == "gratuit"


def test_connexion_refusee(client):
    inscrire(client, "a@atlas.ma")
    assert client.post("/auth/login", json={"email": "a@atlas.ma", "mot_de_passe": "faux"}).status_code == 401
    assert client.post("/auth/login", json={"email": "inconnu@x.ma", "mot_de_passe": "faux"}).status_code == 401


def test_jeton_sans_organisation_refuse(client):
    jeton = jwt.encode({"sub": "1", "role": "admin", "exp": 9999999999}, JWT_SECRET, algorithm="HS256")
    assert client.get("/me", headers={"Authorization": f"Bearer {jeton}"}).status_code == 401


def test_admin_ne_gere_que_son_organisation(client):
    a = inscrire(client, "admin@a.ma", "Org A")
    b = inscrire(client, "admin@b.ma", "Org B")
    ha = {"Authorization": "Bearer " + a["access_token"]}
    hb = {"Authorization": "Bearer " + b["access_token"]}

    cree = client.post("/utilisateurs", headers=hb, json={"email": "serveur@b.ma", "mot_de_passe": "MotDePasse!123"})
    assert cree.status_code == 201 and cree.json()["organisation_id"] == b["organisation_id"]
    id_b = cree.json()["id"]

    # A ne voit pas les comptes de B, et reçoit 404 en voulant en modifier un.
    assert {u["email"] for u in client.get("/utilisateurs", headers=ha).json()} == {"admin@a.ma"}
    assert client.patch(f"/utilisateurs/{id_b}", headers=ha, json={"actif": False}).status_code == 404
    assert client.patch(f"/utilisateurs/{id_b}", headers=hb, json={"role": "gestionnaire"}).json()["role"] == (
        "gestionnaire"
    )


def test_roles(client):
    a = inscrire(client, "admin@a.ma", "Org A")
    lecteur = entete(a["organisation_id"], role="lecteur", user_id=99)
    assert client.get("/utilisateurs", headers=lecteur).status_code == 403
    assert client.patch("/organisations/moi", headers=lecteur, json={"plan": "pro"}).status_code == 403


def test_admin_ne_se_retire_pas_ses_droits(client):
    a = inscrire(client, "admin@a.ma", "Org A")
    h = {"Authorization": "Bearer " + a["access_token"]}
    me = client.get("/me", headers=h).json()
    assert client.patch(f"/utilisateurs/{me['id']}", headers=h, json={"actif": False}).status_code == 400


def test_changement_de_plan(client):
    a = inscrire(client, "admin@a.ma", "Org A")
    h = {"Authorization": "Bearer " + a["access_token"]}
    assert client.get("/organisations/moi", headers=h).json()["limites"]["etablissements"] == 1
    r = client.patch("/organisations/moi", headers=h, json={"plan": "pro"})
    assert r.status_code == 200 and r.json()["limites"]["etablissements"] == 5
    # Le nouveau plan est dans les jetons émis ensuite.
    r = client.post("/auth/login", json={"email": "admin@a.ma", "mot_de_passe": "MotDePasse!123"})
    assert r.json()["plan"] == "pro"
    assert client.patch("/organisations/moi", headers=h, json={"plan": "illimite"}).status_code == 422


def test_compte_de_demonstration_au_demarrage(monkeypatch, sql):
    from fastapi.testclient import TestClient

    import main

    monkeypatch.setenv("ADMIN_EMAIL", "Demo@Beacom.ma")
    monkeypatch.setenv("ADMIN_PASSWORD", "MotDePasse!123")
    for _ in range(2):  # deux démarrages : un seul compte créé
        with TestClient(main.app):
            pass
    assert sql.execute(
        "SELECT u.role, o.plan FROM utilisateurs u JOIN organisations o ON o.id = u.organisation_id"
    ).fetchall() == [("admin", "entreprise")]
