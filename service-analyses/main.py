import os
from datetime import datetime
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

from auth import cle_interne, configurer, exiger_roles, utilisateur_courant

DATABASE_URL = os.environ["DATABASE_URL"]

Sentiment = Literal["positive", "negative", "neutral", "mixed"]

app = FastAPI(title="service-analyses")
configurer(app)


def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


class AnalyseIn(BaseModel):
    avis_id: int
    organisation_id: int
    etablissement_id: int
    sentiment: Sentiment
    score_positif: float = Field(ge=0, le=1)
    score_neutre: float = Field(ge=0, le=1)
    score_negatif: float = Field(ge=0, le=1)
    date_avis: datetime | None = None
    mots_cles: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("mots_cles")
    @classmethod
    def nettoyer(cls, mots: list[str]) -> list[str]:
        """Minuscules, espaces normalisés, sans doublon, 200 caractères au plus : « Service » et « service » comptent ensemble."""
        vus: dict[str, None] = {}
        for mot in mots:
            mot = " ".join(mot.split()).lower()[:200]
            if mot:
                vus.setdefault(mot)
        return list(vus)


class AlerteIn(BaseModel):
    avis_id: int
    organisation_id: int
    etablissement_id: int
    score_negatif: float = Field(ge=0, le=1)
    extrait: str = Field(min_length=1, max_length=300)


class AlertePatch(BaseModel):
    traitee: bool


def filtre_organisation(user: dict, etablissement_id: int | None) -> tuple[str, list]:
    """Clause WHERE commune : toujours l'organisation du jeton, et l'établissement s'il est demandé."""
    clause, params = "organisation_id = %s", [user["organisation_id"]]
    if etablissement_id is not None:
        clause += " AND etablissement_id = %s"
        params.append(etablissement_id)
    return clause, params


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyses/interne", status_code=201, dependencies=[Depends(cle_interne)])
def enregistrer(a: AnalyseIn):
    """Route interne, appelée par l'Azure Function. Idempotente : rejouer le message remplace l'analyse et ses
    mots-clés, sans doublon."""
    with db() as conn:
        analyse = conn.execute(
            """INSERT INTO analyses_sentiment
                   (organisation_id, etablissement_id, avis_id, sentiment, score_positif, score_neutre,
                    score_negatif, date_avis)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (avis_id) DO UPDATE SET
                   etablissement_id = EXCLUDED.etablissement_id,
                   sentiment = EXCLUDED.sentiment,
                   score_positif = EXCLUDED.score_positif,
                   score_neutre = EXCLUDED.score_neutre,
                   score_negatif = EXCLUDED.score_negatif,
                   date_avis = EXCLUDED.date_avis,
                   analyse_le = now()
               RETURNING *""",
            (a.organisation_id, a.etablissement_id, a.avis_id, a.sentiment, a.score_positif, a.score_neutre,
             a.score_negatif, a.date_avis),
        ).fetchone()
        conn.execute("DELETE FROM mots_cles WHERE avis_id = %s", (a.avis_id,))
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO mots_cles (organisation_id, etablissement_id, avis_id, sentiment, mot_cle)
                   VALUES (%s, %s, %s, %s, %s)""",
                [(a.organisation_id, a.etablissement_id, a.avis_id, a.sentiment, m) for m in a.mots_cles],
            )
    return {**analyse, "mots_cles": a.mots_cles}


@app.post("/analyses/interne/alertes", dependencies=[Depends(cle_interne)])
def creer_alerte(a: AlerteIn):
    """Route interne : enregistre une alerte au plus une fois par avis.

    `creee` vaut false si l'alerte existait déjà (message rejoué) : la Function n'envoie alors pas un second e-mail.
    """
    with db() as conn:
        row = conn.execute(
            """INSERT INTO alertes (organisation_id, etablissement_id, avis_id, score_negatif, extrait)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (avis_id) DO NOTHING RETURNING *""",
            (a.organisation_id, a.etablissement_id, a.avis_id, a.score_negatif, a.extrait),
        ).fetchone()
    return {"creee": row is not None, "alerte": row}


@app.get("/analyses")
def lister(
    sentiment: Sentiment | None = None,
    etablissement_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(utilisateur_courant),
):
    clause, params = filtre_organisation(user, etablissement_id)
    if sentiment:
        clause += " AND sentiment = %s"
        params.append(sentiment)
    with db() as conn:
        return conn.execute(
            f"SELECT * FROM analyses_sentiment WHERE {clause} ORDER BY id DESC LIMIT %s OFFSET %s",
            (*params, min(limit, 500), max(offset, 0)),
        ).fetchall()


@app.get("/analyses/resume")
def resume(etablissement_id: int | None = None, user: dict = Depends(utilisateur_courant)):
    """Répartition des sentiments de l'organisation, ou d'un de ses établissements (tableau de bord)."""
    clause, params = filtre_organisation(user, etablissement_id)
    with db() as conn:
        return conn.execute(
            f"""SELECT sentiment, COUNT(*) AS total FROM analyses_sentiment WHERE {clause}
                GROUP BY sentiment ORDER BY total DESC""",
            params,
        ).fetchall()


@app.get("/analyses/tendance")
def tendance(
    periode: Literal["jour", "semaine"] = "semaine",
    depuis_jours: int = Query(90, ge=1, le=730),
    etablissement_id: int | None = None,
    user: dict = Depends(utilisateur_courant),
):
    """Répartition des sentiments par jour ou par semaine (semaine ISO, commençant le lundi).

    La date retenue est celle de l'avis si elle est connue (import CSV), sinon celle de l'analyse.
    """
    unite = {"jour": "day", "semaine": "week"}[periode]  # valeur fixe : pas d'injection possible
    clause, params = filtre_organisation(user, etablissement_id)
    with db() as conn:
        return conn.execute(
            f"""SELECT date_trunc('{unite}', COALESCE(date_avis, analyse_le))::date AS periode,
                       COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive,
                       COUNT(*) FILTER (WHERE sentiment = 'neutral') AS neutral,
                       COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative,
                       COUNT(*) FILTER (WHERE sentiment = 'mixed') AS mixed,
                       COUNT(*) AS total
                FROM analyses_sentiment
                WHERE {clause} AND COALESCE(date_avis, analyse_le) >= now() - make_interval(days => %s)
                GROUP BY 1 ORDER BY 1""",
            (*params, depuis_jours),
        ).fetchall()


@app.get("/analyses/themes")
def themes(
    sentiment: Sentiment = "negative",
    etablissement_id: int | None = None,
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(utilisateur_courant),
):
    """Mots-clés les plus fréquents parmi les avis d'un sentiment donné (par défaut : ce qui déçoit)."""
    clause, params = filtre_organisation(user, etablissement_id)
    with db() as conn:
        return conn.execute(
            f"""SELECT mot_cle, COUNT(*) AS total FROM mots_cles WHERE {clause} AND sentiment = %s
                GROUP BY mot_cle ORDER BY total DESC, mot_cle LIMIT %s""",
            (*params, sentiment, limit),
        ).fetchall()


@app.get("/analyses/alertes")
def alertes(
    traitee: bool | None = False,
    etablissement_id: int | None = None,
    limit: int = 100,
    user: dict = Depends(utilisateur_courant),
):
    """Alertes de l'organisation (par défaut : celles qui restent à traiter)."""
    clause, params = filtre_organisation(user, etablissement_id)
    if traitee is not None:
        clause += " AND traitee = %s"
        params.append(traitee)
    with db() as conn:
        return conn.execute(
            f"SELECT * FROM alertes WHERE {clause} ORDER BY creee_le DESC, id DESC LIMIT %s",
            (*params, min(limit, 500)),
        ).fetchall()


@app.patch("/analyses/alertes/{alerte_id}")
def traiter_alerte(
    alerte_id: int, patch: AlertePatch, user: dict = Depends(exiger_roles("admin", "gestionnaire"))
):
    with db() as conn:
        row = conn.execute(
            "UPDATE alertes SET traitee = %s WHERE id = %s AND organisation_id = %s RETURNING *",
            (patch.traitee, alerte_id, user["organisation_id"]),
        ).fetchone()
    if not row:
        # Même réponse pour une alerte inexistante et pour celle d'une autre organisation.
        raise HTTPException(404, "Alerte introuvable")
    return row


@app.get("/analyses/avis/{avis_id}")
def par_avis(avis_id: int, user: dict = Depends(utilisateur_courant)):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM analyses_sentiment WHERE avis_id = %s AND organisation_id = %s",
            (avis_id, user["organisation_id"]),
        ).fetchone()
        if row:
            mots = conn.execute("SELECT mot_cle FROM mots_cles WHERE avis_id = %s ORDER BY id", (avis_id,)).fetchall()
            row["mots_cles"] = [m["mot_cle"] for m in mots]
    if not row:
        # Même réponse pour une analyse inexistante et pour celle d'une autre organisation.
        raise HTTPException(404, "Analyse introuvable")
    return row
