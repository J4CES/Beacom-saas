"""Les migrations s'appliquent sur l'ancien schéma, conservent les données et peuvent être rejouées."""
import os
from pathlib import Path

import psycopg
import pytest

SQL = Path(__file__).resolve().parents[1] / "sql"
AVANT = Path(__file__).resolve().parent / "schema_avant_001"
ADMIN_URL = os.getenv("TEST_PG_ADMIN_URL", "postgresql://beacom:beacom@localhost:5432/postgres")

CAS = {
    # base : (script de création, insertion d'une ligne existante, table migrée)
    "utilisateurs": (
        "04_utilisateurs.sql",
        "INSERT INTO utilisateurs (email, mot_de_passe_hash, role) VALUES ('a@b.ma', 'h', 'admin')",
        "utilisateurs",
    ),
    "etablissements": ("01_etablissements.sql", "INSERT INTO etablissements (nom, source_id) VALUES ('Atlas', 'g-1')", "etablissements"),
    "collecte": ("02_collecte.sql", "INSERT INTO avis (etablissement_id, texte) VALUES (1, 'Bien')", "avis"),
    "analyses": ("03_analyses.sql", "INSERT INTO analyses_sentiment (avis_id, sentiment) VALUES (1, 'positive')", "analyses_sentiment"),
}


def base_vide(nom: str) -> str:
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{nom}"')
        c.execute(f'CREATE DATABASE "{nom}"')
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + nom


@pytest.mark.parametrize("base", CAS)
def test_migration_sur_ancien_schema(base):
    script, insertion, table = CAS[base]
    url = base_vide(f"test_migration_{base}")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((AVANT / script).read_text())
        c.execute(insertion)
        for _ in range(2):  # idempotente : rejouable
            c.execute((SQL / "migrations" / f"001_multi_clients_{base}.sql").read_text())
        assert c.execute(f"SELECT organisation_id FROM {table}").fetchall() == [(1,)]
        nullable = c.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_name = %s AND column_name = 'organisation_id'",
            (table,),
        ).fetchone()
        assert nullable == ("NO",)
        if base == "utilisateurs":
            assert c.execute("SELECT id, plan FROM organisations").fetchall() == [(1, "entreprise")]
            # La séquence a été recalée : la prochaine organisation reçoit l'id 2.
            assert c.execute("INSERT INTO organisations (nom) VALUES ('Nouvelle') RETURNING id").fetchone() == (2,)


@pytest.mark.parametrize("base", CAS)
def test_migration_sans_effet_sur_une_installation_neuve(base):
    script, _, _ = CAS[base]
    url = base_vide(f"test_neuve_{base}")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((SQL / script).read_text())
        c.execute((SQL / "migrations" / f"001_multi_clients_{base}.sql").read_text())


def test_source_id_unique_par_organisation_apres_migration():
    url = base_vide("test_migration_source_id")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((AVANT / "01_etablissements.sql").read_text())
        c.execute((SQL / "migrations" / "001_multi_clients_etablissements.sql").read_text())
        c.execute("INSERT INTO etablissements (organisation_id, nom, source_id) VALUES (1, 'a', 'g'), (2, 'b', 'g')")
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("INSERT INTO etablissements (organisation_id, nom, source_id) VALUES (1, 'c', 'g')")


def test_migration_002_jeton_public():
    url = base_vide("test_migration_002")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((AVANT / "01_etablissements.sql").read_text())
        c.execute("INSERT INTO etablissements (nom) VALUES ('a'), ('b'), ('c')")
        for _ in range(2):
            c.execute((SQL / "migrations" / "001_multi_clients_etablissements.sql").read_text())
            c.execute((SQL / "migrations" / "002_jeton_public_etablissements.sql").read_text())
        jetons = [j for (j,) in c.execute("SELECT jeton_public FROM etablissements").fetchall()]
        assert len(set(jetons)) == 3 and all(len(j) == 32 for j in jetons)
        neuve = base_vide("test_neuve_002")
    with psycopg.connect(neuve, autocommit=True) as c:
        c.execute((SQL / "01_etablissements.sql").read_text())
        c.execute((SQL / "migrations" / "002_jeton_public_etablissements.sql").read_text())


def test_migration_003_analyses():
    url = base_vide("test_migration_003")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((AVANT / "03_analyses.sql").read_text())
        c.execute("INSERT INTO analyses_sentiment (avis_id, sentiment) VALUES (1, 'negative')")
        for _ in range(2):
            c.execute((SQL / "migrations" / "001_multi_clients_analyses.sql").read_text())
            c.execute((SQL / "migrations" / "003_analyses_par_etablissement.sql").read_text())
        assert c.execute("SELECT organisation_id, etablissement_id FROM analyses_sentiment").fetchall() == [(1, None)]
        assert c.execute("SELECT COUNT(*) FROM mots_cles").fetchone() == (0,)
        assert c.execute("SELECT COUNT(*) FROM alertes").fetchone() == (0,)
    neuve = base_vide("test_neuve_003")
    with psycopg.connect(neuve, autocommit=True) as c:
        c.execute((SQL / "03_analyses.sql").read_text())
        c.execute((SQL / "migrations" / "003_analyses_par_etablissement.sql").read_text())
