import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Literal

import psycopg
from azure.storage.queue import QueueClient, TextBase64EncodePolicy
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import bearer, cle_interne, configurer, exiger_roles, limite_du_plan, utilisateur_courant

DATABASE_URL = os.environ["DATABASE_URL"]
STORAGE_CONNECTION_STRING = os.environ["STORAGE_CONNECTION_STRING"]
QUEUE_NAME = os.getenv("QUEUE_NAME", "avis-a-analyser")
ETABLISSEMENTS_API_URL = os.getenv("ETABLISSEMENTS_API_URL", "")

logger = logging.getLogger("collecte")
app = FastAPI(title="service-collecte")
configurer(app)


def get_queue() -> QueueClient:
    # L'encodage base64 est celui attendu par défaut par le trigger Azure Functions.
    return QueueClient.from_connection_string(
        STORAGE_CONNECTION_STRING,
        QUEUE_NAME,
        message_encode_policy=TextBase64EncodePolicy(),
    )


def message_file(avis: dict) -> str:
    """Message JSON de la file avis-a-analyser. organisation_id suit l'avis jusqu'à service-analyses."""
    return json.dumps(
        {
            "avis_id": avis["id"],
            "organisation_id": avis["organisation_id"],
            "texte": avis["texte"],
            "langue": avis["langue"],
        },
        ensure_ascii=False,
    )


def marquer_en_file(conn: psycopg.Connection, avis_id: int) -> None:
    """Passe l'avis à 'en_file', sauf si la Function l'a déjà marqué 'analyse' entre-temps."""
    conn.execute("UPDATE avis SET statut = 'en_file' WHERE id = %s AND statut = 'nouveau'", (avis_id,))
    conn.commit()


def verifier_etablissement(etab_id: int, token: str) -> None:
    """Appel REST synchrone vers service-etablissements (le jeton de l'utilisateur est transmis)."""
    if not ETABLISSEMENTS_API_URL:
        logger.warning("ETABLISSEMENTS_API_URL non défini : existence de l'établissement non vérifiée")
        return
    req = urllib.request.Request(
        f"{ETABLISSEMENTS_API_URL.rstrip('/')}/etablissements/{etab_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(422, "Établissement inexistant")
        raise HTTPException(502, f"service-etablissements a répondu {exc.code}")
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(503, "service-etablissements injoignable")


class AvisIn(BaseModel):
    etablissement_id: int
    texte: str = Field(min_length=1, max_length=5000)
    auteur: str | None = Field(default=None, max_length=255)
    note: int | None = Field(default=None, ge=1, le=5)
    langue: str | None = Field(default=None, min_length=2, max_length=10)
    date_avis: datetime | None = None
    source: str | None = Field(default=None, max_length=100)


class StatutIn(BaseModel):
    statut: Literal["en_file", "analyse"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/avis", status_code=201)
def collecter(
    avis: AvisIn,
    user: dict = Depends(exiger_roles("admin", "gestionnaire")),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    # service-etablissements filtre par organisation : un établissement d'un autre client y est introuvable.
    verifier_etablissement(avis.etablissement_id, creds.credentials)
    org_id = user["organisation_id"]
    maximum = limite_du_plan(user["plan"], "avis_par_mois")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        if maximum is not None:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (org_id,))
            nb = conn.execute(
                """SELECT COUNT(*) AS nb FROM avis
                   WHERE organisation_id = %s AND collecte_le >= date_trunc('month', now())""",
                (org_id,),
            ).fetchone()["nb"]
            if nb >= maximum:
                raise HTTPException(
                    402,
                    f"Le plan {user['plan']} est limité à {maximum} avis par mois. "
                    "Passez à un plan supérieur pour en collecter davantage.",
                )
        ligne = conn.execute(
            """INSERT INTO avis (organisation_id, etablissement_id, auteur, note, texte, langue, date_avis, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, organisation_id, texte, langue""",
            (
                org_id,
                avis.etablissement_id,
                avis.auteur,
                avis.note,
                avis.texte,
                avis.langue,
                avis.date_avis,
                avis.source,
            ),
        ).fetchone()
        # L'avis doit être visible en base AVANT d'être en file : sinon la Function, plus rapide,
        # recevrait un 404 en mettant à jour son statut.
        conn.commit()

        try:
            get_queue().send_message(message_file(ligne))
        except Exception as exc:
            # L'avis reste en 'nouveau' : POST /avis/renvoyer-nouveaux le renverra plus tard.
            logger.exception("Envoi en file échoué pour l'avis %s", ligne["id"])
            raise HTTPException(502, f"Avis enregistré (id={ligne['id']}) mais envoi en file échoué") from exc

        marquer_en_file(conn, ligne["id"])
    return {"id": ligne["id"], "statut": "en_file"}


@app.get("/avis")
def lister(
    etablissement_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(utilisateur_courant),
):
    params: list = [user["organisation_id"]]
    filtre = ""
    if etablissement_id is not None:
        filtre = " AND etablissement_id = %s"
        params.append(etablissement_id)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(
            f"SELECT * FROM avis WHERE organisation_id = %s{filtre} ORDER BY id DESC LIMIT %s OFFSET %s",
            (*params, min(limit, 500), max(offset, 0)),
        ).fetchall()


@app.get("/avis/{avis_id}")
def lire(avis_id: int, user: dict = Depends(utilisateur_courant)):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT * FROM avis WHERE id = %s AND organisation_id = %s", (avis_id, user["organisation_id"])
        ).fetchone()
    if not row:
        # Même réponse pour un avis inexistant et pour celui d'une autre organisation.
        raise HTTPException(404, "Avis introuvable")
    return row


@app.post("/avis/renvoyer-nouveaux")
def renvoyer_nouveaux(user: dict = Depends(exiger_roles("admin"))):
    """Renvoie dans la file les avis de l'organisation restés en statut 'nouveau'.

    Chaque avis est validé séparément : une panne en cours de route n'annule pas les envois déjà faits.
    """
    queue = get_queue()
    envoyes = 0
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        lignes = conn.execute(
            """SELECT id, organisation_id, texte, langue FROM avis
               WHERE statut = 'nouveau' AND organisation_id = %s ORDER BY id""",
            (user["organisation_id"],),
        ).fetchall()
        conn.commit()
        for ligne in lignes:
            try:
                queue.send_message(message_file(ligne))
            except Exception as exc:
                logger.exception("Renvoi en file échoué pour l'avis %s", ligne["id"])
                raise HTTPException(
                    502, f"{envoyes} avis renvoyés, puis échec de l'envoi en file (avis {ligne['id']})"
                ) from exc
            marquer_en_file(conn, ligne["id"])
            envoyes += 1
    return {"envoyes": envoyes}


@app.patch("/avis/{avis_id}/statut", dependencies=[Depends(cle_interne)])
def changer_statut(avis_id: int, s: StatutIn):
    """Route interne, appelée par l'Azure Function une fois l'analyse enregistrée."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        row = conn.execute(
            "UPDATE avis SET statut = %s WHERE id = %s RETURNING id, statut", (s.statut, avis_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Avis introuvable")
    return row
