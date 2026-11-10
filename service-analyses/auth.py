"""Authentification JWT, rôles, clé interne et journal d'accès.

Ce fichier est identique dans les quatre services : chacun reste déployable seul,
sans bibliothèque partagée. Toute modification doit être reportée dans les quatre copies.
"""
import hmac
import logging
import os
import time

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

bearer = HTTPBearer(auto_error=False)
access_log = logging.getLogger("access")


def utilisateur_courant(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "Authentification requise", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(
            creds.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Jeton expiré", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Jeton invalide", headers={"WWW-Authenticate": "Bearer"})
    return {"id": int(payload["sub"]), "email": payload.get("email"), "role": payload.get("role")}


def exiger_roles(*roles: str):
    def verifier(user: dict = Depends(utilisateur_courant)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Droits insuffisants")
        return user

    return verifier


def cle_interne(x_api_key: str | None = Header(default=None)) -> None:
    """Authentification de service à service (ex. Azure Function -> API)."""
    attendue = os.getenv("INTERNAL_API_KEY", "")
    if not attendue or not x_api_key or not hmac.compare_digest(x_api_key.encode(), attendue.encode()):
        raise HTTPException(401, "Clé interne invalide")


def configurer(app: FastAPI) -> None:
    """CORS (origines autorisées via ALLOWED_ORIGINS) et journal d'accès."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    origines = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if origines:
        app.add_middleware(
            CORSMiddleware, allow_origins=origines, allow_methods=["*"], allow_headers=["*"]
        )

    @app.middleware("http")
    async def journaliser(request: Request, call_next):
        debut = time.perf_counter()
        reponse = await call_next(request)
        ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "-")
        access_log.info(
            "%s %s -> %s (%.0f ms) ip=%s",
            request.method,
            request.url.path,
            reponse.status_code,
            (time.perf_counter() - debut) * 1000,
            ip,
        )
        return reponse
