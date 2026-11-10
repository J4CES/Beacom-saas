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

from auth import bearer, cle_interne, configurer, exiger_roles, utilisateur_courant

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


@app.post("/avis", status_code=201, dependencies=[Depends(exiger_roles("admin", "gestionnaire"))])
def collecter(avis: AvisIn, creds: HTTPAuthorizationCredentials = Depends(bearer)):
    verifier_etablissement(avis.etablissement_id, creds.credentials)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        avis_id = conn.execute(
            """INSERT INTO avis (etablissement_id, auteur, note, texte, langue, date_avis, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                avis.etablissement_id,
                avis.auteur,
                avis.note,
                avis.texte,
                avis.langue,
                avis.date_avis,
                avis.source,
            ),
        ).fetchone()["id"]

        message = {"avis_id": avis_id, "texte": avis.texte, "langue": avis.langue}
        try:
            get_queue().send_message(json.dumps(message, ensure_ascii=False))
        except Exception as exc:
            # L'avis reste en 'nouveau' : POST /avis/renvoyer-nouveaux le renverra plus tard.
            conn.commit()
            logger.exception("Envoi en file échoué pour l'avis %s", avis_id)
            raise HTTPException(502, f"Avis enregistré (id={avis_id}) mais envoi en file échoué") from exc

        conn.execute("UPDATE avis SET statut = 'en_file' WHERE id = %s", (avis_id,))
    return {"id": avis_id, "statut": "en_file"}


@app.get("/avis", dependencies=[Depends(utilisateur_courant)])
def lister(etablissement_id: int | None = None, limit: int = 100, offset: int = 0):
    limit = min(limit, 500)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        if etablissement_id is not None:
            return conn.execute(
                "SELECT * FROM avis WHERE etablissement_id = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (etablissement_id, limit, offset),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM avis ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()


@app.post("/avis/renvoyer-nouveaux", dependencies=[Depends(exiger_roles("admin"))])
def renvoyer_nouveaux():
    """Renvoie dans la file les avis restés en statut 'nouveau'."""
    queue = get_queue()
    envoyes = 0
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        for r in conn.execute("SELECT id, texte, langue FROM avis WHERE statut = 'nouveau'").fetchall():
            queue.send_message(
                json.dumps({"avis_id": r["id"], "texte": r["texte"], "langue": r["langue"]}, ensure_ascii=False)
            )
            conn.execute("UPDATE avis SET statut = 'en_file' WHERE id = %s", (r["id"],))
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
