import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from auth import configurer, exiger_roles, utilisateur_courant
from security import creer_jeton, hasher_mot_de_passe, verifier_mot_de_passe

DATABASE_URL = os.environ["DATABASE_URL"]
logger = logging.getLogger("utilisateurs")

Role = Literal["admin", "gestionnaire", "lecteur"]
COLONNES = "id, email, nom, role, actif, created_at"
# Hash factice : on le vérifie même si l'e-mail est inconnu, pour ne pas révéler son existence par le temps de réponse.
FAUX_HASH = hasher_mot_de_passe("mot-de-passe-factice")


@contextmanager
def db():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Crée l'administrateur initial depuis ADMIN_EMAIL / ADMIN_PASSWORD s'il n'existe aucun admin."""
    email, mdp = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if email and mdp:
        with db() as conn:
            existe = conn.execute("SELECT 1 FROM utilisateurs WHERE role = 'admin' LIMIT 1").fetchone()
            if not existe:
                conn.execute(
                    "INSERT INTO utilisateurs (email, nom, mot_de_passe_hash, role) VALUES (%s, %s, %s, 'admin')",
                    (email.lower(), "Administrateur", hasher_mot_de_passe(mdp)),
                )
                logger.info("Administrateur initial créé : %s", email)
    yield


app = FastAPI(title="service-utilisateurs", lifespan=lifespan)
configurer(app)


class LoginIn(BaseModel):
    email: str
    mot_de_passe: str


class UtilisateurIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    nom: str | None = Field(default=None, max_length=255)
    mot_de_passe: str = Field(min_length=10, max_length=128)
    role: Role = "lecteur"


class UtilisateurPatch(BaseModel):
    role: Role | None = None
    actif: bool | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(d: LoginIn):
    with db() as conn:
        u = conn.execute("SELECT * FROM utilisateurs WHERE email = %s", (d.email.lower(),)).fetchone()
    mdp_ok = verifier_mot_de_passe(d.mot_de_passe, u["mot_de_passe_hash"] if u else FAUX_HASH)
    if not u or not mdp_ok or not u["actif"]:
        raise HTTPException(401, "Identifiants invalides")
    jeton, expire_dans = creer_jeton(u["id"], u["email"], u["role"])
    return {"access_token": jeton, "token_type": "bearer", "expires_in": expire_dans, "role": u["role"]}


@app.get("/me")
def moi(user: dict = Depends(utilisateur_courant)):
    return user


@app.post("/utilisateurs", status_code=201, dependencies=[Depends(exiger_roles("admin"))])
def creer(u: UtilisateurIn):
    try:
        with db() as conn:
            return conn.execute(
                f"""INSERT INTO utilisateurs (email, nom, mot_de_passe_hash, role)
                    VALUES (%s, %s, %s, %s) RETURNING {COLONNES}""",
                (u.email.lower(), u.nom, hasher_mot_de_passe(u.mot_de_passe), u.role),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(409, "Cet e-mail est déjà utilisé")


@app.get("/utilisateurs", dependencies=[Depends(exiger_roles("admin"))])
def lister(limit: int = 100, offset: int = 0):
    with db() as conn:
        return conn.execute(
            f"SELECT {COLONNES} FROM utilisateurs ORDER BY id LIMIT %s OFFSET %s", (min(limit, 500), offset)
        ).fetchall()


@app.patch("/utilisateurs/{user_id}")
def modifier(user_id: int, patch: UtilisateurPatch, admin: dict = Depends(exiger_roles("admin"))):
    if user_id == admin["id"] and (patch.actif is False or (patch.role and patch.role != "admin")):
        raise HTTPException(400, "Un administrateur ne peut pas se retirer ses propres droits")
    with db() as conn:
        row = conn.execute(
            f"""UPDATE utilisateurs SET role = COALESCE(%s, role), actif = COALESCE(%s, actif)
                WHERE id = %s RETURNING {COLONNES}""",
            (patch.role, patch.actif, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Utilisateur introuvable")
    return row
