import os
import sys

import jwt
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import security  # noqa: E402


def test_hash_et_verification():
    h = security.hasher_mot_de_passe("Motdepasse!123")
    assert h.startswith("scrypt$")
    assert "Motdepasse" not in h
    assert security.verifier_mot_de_passe("Motdepasse!123", h)
    assert not security.verifier_mot_de_passe("autre", h)


def test_hash_est_sale():
    assert security.hasher_mot_de_passe("abc") != security.hasher_mot_de_passe("abc")


def test_hash_malformé_refusé():
    assert not security.verifier_mot_de_passe("abc", "n-importe-quoi")
    assert not security.verifier_mot_de_passe("abc", "bcrypt$1$2$3$a$b")


def test_jeton_contient_role_et_expiration():
    jeton, duree = security.creer_jeton(7, "a@b.fr", "gestionnaire", 3, "pro", minutes=5)
    payload = jwt.decode(jeton, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert payload["sub"] == "7"
    assert payload["role"] == "gestionnaire"
    assert payload["org"] == 3
    assert payload["plan"] == "pro"
    assert duree == 300
    assert payload["exp"] - payload["iat"] == 300


def test_jeton_expire_refusé():
    jeton, _ = security.creer_jeton(1, "a@b.fr", "lecteur", 1, "gratuit", minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(jeton, os.environ["JWT_SECRET"], algorithms=["HS256"])


def test_mauvaise_clé_refusée():
    jeton, _ = security.creer_jeton(1, "a@b.fr", "lecteur", 1, "gratuit")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(jeton, "y" * 40, algorithms=["HS256"])


def test_secret_trop_court_refusé(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "court")
    with pytest.raises(RuntimeError):
        security.creer_jeton(1, "a@b.fr", "lecteur", 1, "gratuit")
