import os
from contextlib import contextmanager

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import configurer, exiger_roles, limite_du_plan, utilisateur_courant

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


@app.post("/etablissements", status_code=201)
def creer(e: EtablissementIn, user: dict = Depends(exiger_roles("admin", "gestionnaire"))):
    org_id = user["organisation_id"]
    maximum = limite_du_plan(user["plan"], "etablissements")
    try:
        with db() as conn:
            if maximum is not None:
                # Verrou par organisation : deux créations simultanées ne peuvent pas dépasser la limite.
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (org_id,))
                nb = conn.execute(
                    "SELECT COUNT(*) AS nb FROM etablissements WHERE organisation_id = %s", (org_id,)
                ).fetchone()["nb"]
                if nb >= maximum:
                    raise HTTPException(
                        402,
                        f"Le plan {user['plan']} est limité à {maximum} établissement(s). "
                        "Passez à un plan supérieur pour en ajouter.",
                    )
            return conn.execute(
                """INSERT INTO etablissements (organisation_id, nom, categorie, adresse, ville, source_id)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                (org_id, e.nom, e.categorie, e.adresse, e.ville, e.source_id),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(409, "Un établissement avec ce source_id existe déjà")


@app.get("/etablissements")
def lister(
    ville: str | None = None, limit: int = 100, offset: int = 0, user: dict = Depends(utilisateur_courant)
):
    params: list = [user["organisation_id"]]
    filtre = ""
    if ville:
        filtre = " AND ville = %s"
        params.append(ville)
    with db() as conn:
        return conn.execute(
            f"SELECT * FROM etablissements WHERE organisation_id = %s{filtre} ORDER BY id LIMIT %s OFFSET %s",
            (*params, min(limit, 500), max(offset, 0)),
        ).fetchall()


@app.get("/etablissements/{etab_id}")
def lire(etab_id: int, user: dict = Depends(utilisateur_courant)):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM etablissements WHERE id = %s AND organisation_id = %s",
            (etab_id, user["organisation_id"]),
        ).fetchone()
    if not row:
        # Même réponse pour un établissement inexistant et pour celui d'une autre organisation.
        raise HTTPException(404, "Établissement introuvable")
    return row


@app.delete("/etablissements/{etab_id}", status_code=204)
def supprimer(etab_id: int, user: dict = Depends(exiger_roles("admin"))):
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM etablissements WHERE id = %s AND organisation_id = %s", (etab_id, user["organisation_id"])
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Établissement introuvable")
