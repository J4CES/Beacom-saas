import csv
import io
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Literal

import psycopg
from azure.storage.queue import QueueClient, TextBase64EncodePolicy
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from auth import (
    bearer,
    cle_interne,
    configurer,
    entetes_correlation,
    exiger_roles,
    id_requete,
    limite_du_plan,
    limiter_debit,
    utilisateur_courant,
)

DATABASE_URL = os.environ["DATABASE_URL"]
STORAGE_CONNECTION_STRING = os.environ["STORAGE_CONNECTION_STRING"]
QUEUE_NAME = os.getenv("QUEUE_NAME", "avis-a-analyser")
ETABLISSEMENTS_API_URL = os.getenv("ETABLISSEMENTS_API_URL", "")
UTILISATEURS_API_URL = os.getenv("UTILISATEURS_API_URL", "")

IMPORT_TAILLE_MAX = 1_000_000  # octets
IMPORT_LIGNES_MAX = 1000
MOTIF_JETON = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

logger = logging.getLogger("collecte")
app = FastAPI(title="service-collecte")
configurer(app, DATABASE_URL)


def get_queue() -> QueueClient:
    # L'encodage base64 est celui attendu par défaut par le trigger Azure Functions.
    return QueueClient.from_connection_string(
        STORAGE_CONNECTION_STRING,
        QUEUE_NAME,
        message_encode_policy=TextBase64EncodePolicy(),
    )


COLONNES_MESSAGE = "id, organisation_id, etablissement_id, texte, langue, date_avis"


def message_file(avis: dict) -> str:
    """Message JSON de la file avis-a-analyser. L'organisation et l'établissement suivent l'avis jusqu'à
    service-analyses ; date_avis permet de dater correctement un avis ancien importé par CSV."""
    return json.dumps(
        {
            "avis_id": avis["id"],
            "organisation_id": avis["organisation_id"],
            "etablissement_id": avis["etablissement_id"],
            "texte": avis["texte"],
            "langue": avis["langue"],
            "date_avis": avis["date_avis"].isoformat() if avis["date_avis"] else None,
            # Corrélation : la Function renvoie cet identifiant à chaque service qu'elle appelle.
            "request_id": id_requete(),
        },
        ensure_ascii=False,
    )


def marquer_en_file(conn: psycopg.Connection, avis_id: int) -> None:
    """Passe l'avis à 'en_file', sauf si la Function l'a déjà marqué 'analyse' entre-temps."""
    conn.execute("UPDATE avis SET statut = 'en_file' WHERE id = %s AND statut = 'nouveau'", (avis_id,))
    conn.commit()


def appel_get(url: str, headers: dict, service: str) -> dict:
    """GET synchrone vers un autre service. 404 -> None ; autre erreur -> 502 ; injoignable -> 503."""
    try:
        requete = urllib.request.Request(url, headers={**headers, **entetes_correlation()})
        with urllib.request.urlopen(requete, timeout=5) as rep:
            return json.loads(rep.read() or b"null")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise HTTPException(502, f"{service} a répondu {exc.code}")
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(503, f"{service} injoignable")


def verifier_etablissement(etab_id: int, token: str) -> None:
    """Appel REST synchrone vers service-etablissements (le jeton de l'utilisateur est transmis)."""
    if not ETABLISSEMENTS_API_URL:
        logger.warning("ETABLISSEMENTS_API_URL non défini : existence de l'établissement non vérifiée")
        return
    trouve = appel_get(
        f"{ETABLISSEMENTS_API_URL.rstrip('/')}/etablissements/{etab_id}",
        {"Authorization": f"Bearer {token}"},
        "service-etablissements",
    )
    if trouve is None:
        raise HTTPException(422, "Établissement inexistant")


def resoudre_jeton_public(jeton: str) -> dict:
    """Route interne de service-etablissements : établissement et organisation d'un jeton public."""
    if not MOTIF_JETON.fullmatch(jeton) or not ETABLISSEMENTS_API_URL:
        raise HTTPException(404, "Lien inconnu")
    etab = appel_get(
        f"{ETABLISSEMENTS_API_URL.rstrip('/')}/interne/etablissements/par-jeton/{jeton}",
        {"X-API-Key": os.getenv("INTERNAL_API_KEY", "")},
        "service-etablissements",
    )
    if etab is None:
        raise HTTPException(404, "Lien inconnu")
    return etab


def plan_de_l_organisation(organisation_id: int) -> str:
    """Plan d'une organisation, pour un dépôt sans jeton utilisateur. À défaut d'information : plan gratuit."""
    if not UTILISATEURS_API_URL:
        logger.warning("UTILISATEURS_API_URL non défini : limites du plan gratuit appliquées")
        return "gratuit"
    org = appel_get(
        f"{UTILISATEURS_API_URL.rstrip('/')}/interne/organisations/{organisation_id}",
        {"X-API-Key": os.getenv("INTERNAL_API_KEY", "")},
        "service-utilisateurs",
    )
    return org["plan"] if org else "gratuit"


class AvisIn(BaseModel):
    etablissement_id: int
    texte: str = Field(min_length=1, max_length=5000)
    auteur: str | None = Field(default=None, max_length=255)
    note: int | None = Field(default=None, ge=1, le=5)
    langue: str | None = Field(default=None, min_length=2, max_length=10)
    date_avis: datetime | None = None
    source: str | None = Field(default=None, max_length=100)


class AvisPublicIn(BaseModel):
    """Avis déposé par un client final depuis le lien public ou le QR code. Validation stricte."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    texte: str = Field(min_length=5, max_length=2000)
    note: int = Field(ge=1, le=5)
    auteur: str | None = Field(default=None, max_length=100)
    langue: str | None = Field(default=None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    # Champ piège : caché aux humains par le formulaire, rempli par les robots qui complètent tout.
    site_web: str | None = Field(default=None, max_length=500)


class LigneCsv(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    texte: str = Field(min_length=1, max_length=5000)
    note: int | None = Field(default=None, ge=1, le=5)
    auteur: str | None = Field(default=None, max_length=255)
    langue: str | None = Field(default=None, min_length=2, max_length=10)
    date_avis: datetime | None = None
    source: str | None = Field(default=None, max_length=100)

    @field_validator("note", "auteur", "langue", "date_avis", "source", mode="before")
    @classmethod
    def vide_devient_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class StatutIn(BaseModel):
    statut: Literal["en_file", "analyse"]


def enregistrer_et_publier(org_id: int, plan: str, etab_id: int, avis: list[dict]) -> list[int]:
    """Enregistre des avis (tout ou rien), valide la transaction, puis les publie dans la file.

    Le quota mensuel du plan est vérifié sous verrou par organisation. Les avis dont l'envoi en file échoue restent
    'nouveau' : POST /avis/renvoyer-nouveaux les rattrape.
    """
    maximum = limite_du_plan(plan, "avis_par_mois")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        if maximum is not None:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (org_id,))
            nb = conn.execute(
                """SELECT COUNT(*) AS nb FROM avis
                   WHERE organisation_id = %s AND collecte_le >= date_trunc('month', now())""",
                (org_id,),
            ).fetchone()["nb"]
            if nb + len(avis) > maximum:
                raise HTTPException(
                    402,
                    f"Le plan {plan} est limité à {maximum} avis par mois ({nb} déjà collectés). "
                    "Passez à un plan supérieur pour en collecter davantage.",
                )
        lignes = [
            conn.execute(
                """INSERT INTO avis (organisation_id, etablissement_id, auteur, note, texte, langue, date_avis, source)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING """ + COLONNES_MESSAGE,
                (org_id, etab_id, a.get("auteur"), a.get("note"), a["texte"], a.get("langue"),
                 a.get("date_avis"), a.get("source")),
            ).fetchone()
            for a in avis
        ]
        # Les avis doivent être visibles en base AVANT d'être en file : sinon la Function, plus rapide,
        # recevrait un 404 en mettant à jour leur statut.
        conn.commit()

        queue = get_queue()
        for i, ligne in enumerate(lignes):
            try:
                queue.send_message(message_file(ligne))
            except Exception as exc:
                logger.exception("Envoi en file échoué pour l'avis %s", ligne["id"])
                raise HTTPException(
                    502,
                    f"{len(lignes)} avis enregistrés, {i} envoyés en file avant l'échec : "
                    "les autres seront renvoyés par POST /avis/renvoyer-nouveaux",
                ) from exc
            marquer_en_file(conn, ligne["id"])
    return [ligne["id"] for ligne in lignes]


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
    champs = avis.model_dump(exclude={"etablissement_id"})
    (avis_id,) = enregistrer_et_publier(user["organisation_id"], user["plan"], avis.etablissement_id, [champs])
    return {"id": avis_id, "statut": "en_file"}


@app.post(
    "/public/avis/{jeton}",
    status_code=201,
    dependencies=[Depends(limiter_debit("public-avis", 10, 600))],
)
def deposer_avis_public(jeton: str, avis: AvisPublicIn):
    """Route publique, sans authentification : un client final dépose un avis via le lien ou le QR code."""
    etab = resoudre_jeton_public(jeton)
    if avis.site_web:
        # Robot probable : on répond comme si tout allait bien, sans rien enregistrer.
        logger.info("Champ piège rempli sur le lien de l'établissement %s : avis ignoré", etab["id"])
        return {"statut": "recu"}
    champs = avis.model_dump(exclude={"site_web"}) | {"source": "lien_public"}
    plan = plan_de_l_organisation(etab["organisation_id"])
    enregistrer_et_publier(etab["organisation_id"], plan, etab["id"], [champs])
    # Ni identifiant ni détail interne dans la réponse publique.
    return {"statut": "recu"}


def lire_csv(contenu: bytes) -> list[dict]:
    """CSV UTF-8 (avec ou sans BOM), séparateur ',' ou ';' (Excel en français). Colonne obligatoire : texte."""
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "Le fichier doit être encodé en UTF-8")
    premiere_ligne = texte.split("\n", 1)[0]
    separateur = ";" if premiere_ligne.count(";") > premiere_ligne.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    colonnes = {c.strip().lower() for c in (lecteur.fieldnames or [])}
    if "texte" not in colonnes:
        raise HTTPException(422, "Colonne obligatoire absente : texte (colonnes possibles : texte, note, auteur, "
                                 "langue, date_avis, source)")
    avis, erreurs = [], []
    for numero, brute in enumerate(lecteur, start=2):  # la ligne 1 est l'en-tête
        if numero - 1 > IMPORT_LIGNES_MAX:
            raise HTTPException(422, f"Au plus {IMPORT_LIGNES_MAX} avis par import")
        ligne = {(k or "").strip().lower(): v for k, v in brute.items()}
        try:
            champs = LigneCsv(**{k: v for k, v in ligne.items() if k in LigneCsv.model_fields})
            avis.append(champs.model_dump() | {"source": champs.source or "import_csv"})
        except ValidationError as exc:
            erreurs.append({"ligne": numero, "erreur": "; ".join(e["msg"] for e in exc.errors())})
    if erreurs:
        # Tout ou rien : un fichier partiellement importé serait difficile à corriger puis à réimporter.
        raise HTTPException(422, {"message": "Import refusé : corrigez ces lignes", "erreurs": erreurs[:50]})
    if not avis:
        raise HTTPException(422, "Le fichier ne contient aucun avis")
    return avis


@app.post("/avis/import", status_code=201)
async def importer(
    etablissement_id: int,
    fichier: UploadFile = File(...),
    user: dict = Depends(exiger_roles("admin", "gestionnaire")),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    """Importe des avis depuis un CSV pour un établissement de l'organisation (tout ou rien)."""
    contenu = await fichier.read(IMPORT_TAILLE_MAX + 1)
    if len(contenu) > IMPORT_TAILLE_MAX:
        raise HTTPException(413, f"Fichier trop volumineux (maximum {IMPORT_TAILLE_MAX // 1000} ko)")
    avis = lire_csv(contenu)
    verifier_etablissement(etablissement_id, creds.credentials)
    ids = enregistrer_et_publier(user["organisation_id"], user["plan"], etablissement_id, avis)
    return {"importes": len(ids)}


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
            f"""SELECT {COLONNES_MESSAGE} FROM avis
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
