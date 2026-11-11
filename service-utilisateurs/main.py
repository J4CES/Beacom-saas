import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import LIMITES_PLANS, configurer, exiger_roles, utilisateur_courant
from security import creer_jeton, hasher_mot_de_passe, verifier_mot_de_passe

DATABASE_URL = os.environ["DATABASE_URL"]
logger = logging.getLogger("utilisateurs")

Role = Literal["admin", "gestionnaire", "lecteur"]
Plan = Literal["gratuit", "pro", "entreprise"]
COLONNES = "id, organisation_id, email, nom, role, actif, created_at"
MOTIF_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
# Hash factice : on le vérifie même si l'e-mail est inconnu, pour ne pas révéler son existence par le temps de réponse.
FAUX_HASH = hasher_mot_de_passe("mot-de-passe-factice")


@contextmanager
def db():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Compte de démonstration facultatif : si ADMIN_EMAIL / ADMIN_PASSWORD sont définis et que cet e-mail n'existe pas,
    crée une organisation (plan entreprise) et son administrateur. Les vrais clients passent par /auth/inscription."""
    email, mdp = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if email and mdp:
        with db() as conn:
            existe = conn.execute("SELECT 1 FROM utilisateurs WHERE email = %s", (email.lower(),)).fetchone()
            if not existe:
                org_id = conn.execute(
                    "INSERT INTO organisations (nom, plan) VALUES (%s, 'entreprise') RETURNING id",
                    (os.getenv("ADMIN_ORGANISATION", "Beacom (démonstration)"),),
                ).fetchone()["id"]
                conn.execute(
                    """INSERT INTO utilisateurs (organisation_id, email, nom, mot_de_passe_hash, role)
                       VALUES (%s, %s, %s, %s, 'admin')""",
                    (org_id, email.lower(), "Administrateur", hasher_mot_de_passe(mdp)),
                )
                logger.info("Administrateur initial créé dans l'organisation %s", org_id)
    yield


app = FastAPI(title="service-utilisateurs", lifespan=lifespan)
configurer(app)


class LoginIn(BaseModel):
    email: str
    mot_de_passe: str


class InscriptionIn(BaseModel):
    organisation: str = Field(min_length=2, max_length=255)
    nom: str | None = Field(default=None, max_length=255)
    email: str = Field(min_length=3, max_length=255, pattern=MOTIF_EMAIL)
    mot_de_passe: str = Field(min_length=10, max_length=128)


class OrganisationPatch(BaseModel):
    nom: str | None = Field(default=None, min_length=2, max_length=255)
    plan: Plan | None = None


class UtilisateurIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=MOTIF_EMAIL)
    nom: str | None = Field(default=None, max_length=255)
    mot_de_passe: str = Field(min_length=10, max_length=128)
    role: Role = "lecteur"


class UtilisateurPatch(BaseModel):
    role: Role | None = None
    actif: bool | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


def reponse_jeton(u: dict) -> dict:
    jeton, expire_dans = creer_jeton(u["id"], u["email"], u["role"], u["organisation_id"], u["plan"])
    return {
        "access_token": jeton,
        "token_type": "bearer",
        "expires_in": expire_dans,
        "role": u["role"],
        "organisation_id": u["organisation_id"],
        "plan": u["plan"],
    }


@app.post("/auth/inscription", status_code=201)
def inscription(d: InscriptionIn):
    """Route publique : crée une organisation (plan gratuit) et son premier administrateur, puis connecte celui-ci."""
    try:
        with db() as conn:
            org = conn.execute(
                "INSERT INTO organisations (nom) VALUES (%s) RETURNING id, plan", (d.organisation,)
            ).fetchone()
            u = conn.execute(
                """INSERT INTO utilisateurs (organisation_id, email, nom, mot_de_passe_hash, role)
                   VALUES (%s, %s, %s, %s, 'admin') RETURNING id, email, role, organisation_id""",
                (org["id"], d.email.lower(), d.nom, hasher_mot_de_passe(d.mot_de_passe)),
            ).fetchone()
    except UniqueViolation:
        # La transaction est annulée : aucune organisation orpheline n'est créée.
        raise HTTPException(409, "Cet e-mail est déjà utilisé")
    return reponse_jeton({**u, "plan": org["plan"]})


@app.post("/auth/login")
def login(d: LoginIn):
    with db() as conn:
        u = conn.execute(
            """SELECT u.*, o.plan FROM utilisateurs u JOIN organisations o ON o.id = u.organisation_id
               WHERE u.email = %s""",
            (d.email.lower(),),
        ).fetchone()
    mdp_ok = verifier_mot_de_passe(d.mot_de_passe, u["mot_de_passe_hash"] if u else FAUX_HASH)
    if not u or not mdp_ok or not u["actif"]:
        raise HTTPException(401, "Identifiants invalides")
    return reponse_jeton(u)


@app.get("/me")
def moi(user: dict = Depends(utilisateur_courant)):
    return user


@app.get("/organisations/moi")
def mon_organisation(user: dict = Depends(utilisateur_courant)):
    with db() as conn:
        org = conn.execute(
            "SELECT id, nom, plan, created_at FROM organisations WHERE id = %s", (user["organisation_id"],)
        ).fetchone()
    if not org:
        raise HTTPException(404, "Organisation introuvable")
    return {**org, "limites": LIMITES_PLANS[org["plan"]]}


@app.patch("/organisations/moi")
def modifier_organisation(patch: OrganisationPatch, admin: dict = Depends(exiger_roles("admin"))):
    """Renomme l'organisation ou change son plan (simulation d'abonnement : aucun paiement dans le prototype).
    Le nouveau plan s'applique aux jetons émis ensuite : l'utilisateur doit se reconnecter."""
    with db() as conn:
        org = conn.execute(
            """UPDATE organisations SET nom = COALESCE(%s, nom), plan = COALESCE(%s, plan)
               WHERE id = %s RETURNING id, nom, plan, created_at""",
            (patch.nom, patch.plan, admin["organisation_id"]),
        ).fetchone()
    if not org:
        raise HTTPException(404, "Organisation introuvable")
    return {**org, "limites": LIMITES_PLANS[org["plan"]]}


@app.post("/utilisateurs", status_code=201)
def creer(u: UtilisateurIn, admin: dict = Depends(exiger_roles("admin"))):
    """Crée un compte dans l'organisation de l'administrateur connecté."""
    try:
        with db() as conn:
            return conn.execute(
                f"""INSERT INTO utilisateurs (organisation_id, email, nom, mot_de_passe_hash, role)
                    VALUES (%s, %s, %s, %s, %s) RETURNING {COLONNES}""",
                (admin["organisation_id"], u.email.lower(), u.nom, hasher_mot_de_passe(u.mot_de_passe), u.role),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(409, "Cet e-mail est déjà utilisé")


@app.get("/utilisateurs")
def lister(limit: int = 100, offset: int = 0, admin: dict = Depends(exiger_roles("admin"))):
    with db() as conn:
        return conn.execute(
            f"""SELECT {COLONNES} FROM utilisateurs WHERE organisation_id = %s
                ORDER BY id LIMIT %s OFFSET %s""",
            (admin["organisation_id"], min(limit, 500), max(offset, 0)),
        ).fetchall()


@app.patch("/utilisateurs/{user_id}")
def modifier(user_id: int, patch: UtilisateurPatch, admin: dict = Depends(exiger_roles("admin"))):
    if user_id == admin["id"] and (patch.actif is False or (patch.role and patch.role != "admin")):
        raise HTTPException(400, "Un administrateur ne peut pas se retirer ses propres droits")
    with db() as conn:
        row = conn.execute(
            f"""UPDATE utilisateurs SET role = COALESCE(%s, role), actif = COALESCE(%s, actif)
                WHERE id = %s AND organisation_id = %s RETURNING {COLONNES}""",
            (patch.role, patch.actif, user_id, admin["organisation_id"]),
        ).fetchone()
    if not row:
        # Même réponse pour un compte inexistant et pour un compte d'une autre organisation.
        raise HTTPException(404, "Utilisateur introuvable")
    return row
