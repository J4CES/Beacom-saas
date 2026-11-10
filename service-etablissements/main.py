import os
from contextlib import contextmanager

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import configurer, exiger_roles, utilisateur_courant

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(title="service-etablissements")
configurer(app)


@contextmanager
def db():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


class EtablissementIn(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    categorie: str | None = Field(default=None, max_length=100)
    adresse: str | None = None
    ville: str | None = Field(default=None, max_length=100)
    source_id: str | None = Field(default=None, max_length=255)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/etablissements", status_code=201, dependencies=[Depends(exiger_roles("admin", "gestionnaire"))])
def creer(e: EtablissementIn):
    try:
        with db() as conn:
            return conn.execute(
                """INSERT INTO etablissements (nom, categorie, adresse, ville, source_id)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (e.nom, e.categorie, e.adresse, e.ville, e.source_id),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(409, "Un établissement avec ce source_id existe déjà")


@app.get("/etablissements", dependencies=[Depends(utilisateur_courant)])
def lister(ville: str | None = None, limit: int = 100, offset: int = 0):
    limit = min(limit, 500)
    with db() as conn:
        if ville:
            return conn.execute(
                "SELECT * FROM etablissements WHERE ville = %s ORDER BY id LIMIT %s OFFSET %s",
                (ville, limit, offset),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM etablissements ORDER BY id LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()


@app.get("/etablissements/{etab_id}", dependencies=[Depends(utilisateur_courant)])
def lire(etab_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM etablissements WHERE id = %s", (etab_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Établissement introuvable")
    return row


@app.delete("/etablissements/{etab_id}", status_code=204, dependencies=[Depends(exiger_roles("admin"))])
def supprimer(etab_id: int):
    with db() as conn:
        cur = conn.execute("DELETE FROM etablissements WHERE id = %s", (etab_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Établissement introuvable")
