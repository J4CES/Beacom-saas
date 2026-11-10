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
            """INSERT INTO analyses_sentiment (avis_id, sentiment, score_positif, score_neutre, score_negatif)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (avis_id) DO UPDATE SET
                   sentiment = EXCLUDED.sentiment,
                   score_positif = EXCLUDED.score_positif,
                   score_neutre = EXCLUDED.score_neutre,
                   score_negatif = EXCLUDED.score_negatif,
                   analyse_le = now()
               RETURNING *""",
            (a.avis_id, a.sentiment, a.score_positif, a.score_neutre, a.score_negatif),
        ).fetchone()


@app.get("/analyses", dependencies=[Depends(utilisateur_courant)])
def lister(sentiment: str | None = None, limit: int = 100, offset: int = 0):
    limit = min(limit, 500)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        if sentiment:
            return conn.execute(
                "SELECT * FROM analyses_sentiment WHERE sentiment = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (sentiment, limit, offset),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM analyses_sentiment ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()


@app.get("/analyses/resume", dependencies=[Depends(utilisateur_courant)])
def resume():
    """Répartition des sentiments (tableau de bord)."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT sentiment, COUNT(*) AS total FROM analyses_sentiment GROUP BY sentiment ORDER BY total DESC"
        ).fetchall()


@app.get("/analyses/avis/{avis_id}", dependencies=[Depends(utilisateur_courant)])
def par_avis(avis_id: int):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        row = conn.execute("SELECT * FROM analyses_sentiment WHERE avis_id = %s", (avis_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Analyse introuvable")
    return row
