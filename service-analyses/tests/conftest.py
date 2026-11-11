"""Tests contre un vrai PostgreSQL : une base de test dédiée, recréée à chaque test.

TEST_PG_ADMIN_URL désigne un serveur où l'on peut créer des bases (conteneur Docker en local, service en CI).
"""
import os
import sys
import time
from pathlib import Path

import jwt
import psycopg
import pytest

RACINE = Path(__file__).resolve().parents[2]
ADMIN_URL = os.getenv("TEST_PG_ADMIN_URL", "postgresql://beacom:beacom@localhost:5432/postgres")
BASE = "test_db_analyses"
SCRIPT_SQL = RACINE / "infra" / "sql" / "03_analyses.sql"
JWT_SECRET = "secret-de-test-" + "x" * 40
CLE_INTERNE = "cle-interne-de-test"

os.environ["DATABASE_URL"] = ADMIN_URL.rsplit("/", 1)[0] + "/" + BASE
os.environ["JWT_SECRET"] = JWT_SECRET
os.environ["INTERNAL_API_KEY"] = CLE_INTERNE

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with psycopg.connect(ADMIN_URL, autocommit=True) as _c:
    if not _c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BASE,)).fetchone():
        _c.execute(f'CREATE DATABASE "{BASE}"')


@pytest.fixture(autouse=True)
def base_neuve():
    """Schéma recréé à partir du script de création : chaque test part d'une base vide."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(SCRIPT_SQL.read_text())
    import auth

    auth.limiteur.reinitialiser()  # la limitation de débit en mémoire ne doit pas fuiter d'un test à l'autre
    yield


@pytest.fixture
def sql():
    """Connexion directe à la base de test, pour préparer ou vérifier des données."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        yield conn


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        yield c


def entete(organisation_id: int, role: str = "admin", plan: str = "entreprise", user_id: int = 1) -> dict:
    """En-tête Authorization avec un jeton signé comme le ferait service-utilisateurs."""
    maintenant = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": f"u{user_id}@org{organisation_id}.test",
        "role": role,
        "org": organisation_id,
        "plan": plan,
        "iat": maintenant,
        "exp": maintenant + 600,
    }
    return {"Authorization": "Bearer " + jwt.encode(payload, JWT_SECRET, algorithm="HS256")}


CLE = {"X-API-Key": CLE_INTERNE}
