import os

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import cle_interne, configurer, utilisateur_courant

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(title="service-analyses")
configurer(app)


class AnalyseIn(BaseModel):
    avis_id: int
    organisation_id: int
    sentiment: str = Field(pattern="^(positive|negative|neutral|mixed)$")
    score_positif: float = Field(ge=0, le=1)
    score_neutre: float = Field(ge=0, le=1)
    score_negatif: float = Field(ge=0, le=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyses/interne", status_code=201, dependencies=[Depends(cle_interne)])
def enregistrer(a: AnalyseIn):
    """Route interne, appelée par l'Azure Function. Idempotente : rejouer le message met à jour la ligne."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            """INSERT INTO analyses_sentiment
                   (organisation_id, avis_id, sentiment, score_positif, score_neutre, score_negatif)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (avis_id) DO UPDATE SET
                   sentiment = EXCLUDED.sentiment,
                   score_positif = EXCLUDED.score_positif,
                   score_neutre = EXCLUDED.score_neutre,
                   score_negatif = EXCLUDED.score_negatif,
                   analyse_le = now()
               RETURNING *""",
            (a.organisation_id, a.avis_id, a.sentiment, a.score_positif, a.score_neutre, a.score_negatif),
        ).fetchone()


@app.get("/analyses")
def lister(
    sentiment: str | None = None, limit: int = 100, offset: int = 0, user: dict = Depends(utilisateur_courant)
):
    params: list = [user["organisation_id"]]
    filtre = ""
    if sentiment:
        filtre = " AND sentiment = %s"
        params.append(sentiment)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            f"""SELECT * FROM analyses_sentiment WHERE organisation_id = %s{filtre}
                ORDER BY id DESC LIMIT %s OFFSET %s""",
            (*params, min(limit, 500), max(offset, 0)),
        ).fetchall()


@app.get("/analyses/resume")
def resume(user: dict = Depends(utilisateur_courant)):
    """Répartition des sentiments de l'organisation (tableau de bord)."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            """SELECT sentiment, COUNT(*) AS total FROM analyses_sentiment WHERE organisation_id = %s
               GROUP BY sentiment ORDER BY total DESC""",
            (user["organisation_id"],),
        ).fetchall()


@app.get("/analyses/avis/{avis_id}")
def par_avis(avis_id: int, user: dict = Depends(utilisateur_courant)):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT * FROM analyses_sentiment WHERE avis_id = %s AND organisation_id = %s",
            (avis_id, user["organisation_id"]),
        ).fetchone()
    if not row:
        # Même réponse pour une analyse inexistante et pour celle d'une autre organisation.
        raise HTTPException(404, "Analyse introuvable")
    return row
