"""Authentification JWT, rôles, clé interne, limitation de débit, journal d'accès et observabilité.

Ce fichier est identique dans les quatre services : chacun reste déployable seul,
sans bibliothèque partagée. Toute modification doit être reportée dans les quatre copies.
"""
import contextvars
import hmac
import logging
import os
import re
import threading
import time
import uuid
from collections import deque

import jwt
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

# Limites d'usage par plan d'abonnement (None = illimité). Le plan voyage dans le jeton JWT.
LIMITES_PLANS: dict[str, dict[str, int | None]] = {
    "gratuit": {"etablissements": 1, "avis_par_mois": 100},
    "pro": {"etablissements": 5, "avis_par_mois": None},
    "entreprise": {"etablissements": None, "avis_par_mois": None},
}


def limite_du_plan(plan: str, ressource: str) -> int | None:
    """Limite du plan pour une ressource. Un plan inconnu reçoit les limites du plan gratuit."""
    return LIMITES_PLANS.get(plan, LIMITES_PLANS["gratuit"])[ressource]


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
            options={"require": ["exp", "sub", "org"]},
        )
        organisation_id = int(payload["org"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Jeton expiré", headers={"WWW-Authenticate": "Bearer"})
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(401, "Jeton invalide", headers={"WWW-Authenticate": "Bearer"})
    # organisation_id isole les clients : chaque service filtre toutes ses requêtes dessus.
    return {
        "id": int(payload["sub"]),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "organisation_id": organisation_id,
        "plan": payload.get("plan", "gratuit"),
    }


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


def ip_client(request: Request) -> str:
    """IP du client. Chaque proxy de confiance (frontal App Service, passerelle Next.js) ajoute une adresse à droite
    de X-Forwarded-For : on remonte de PROXIES_DE_CONFIANCE entrées (1 par défaut, 2 derrière la passerelle).
    Les entrées plus à gauche sont fournies par le client et ne sont pas fiables."""
    entrees = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
    rang = max(int(os.getenv("PROXIES_DE_CONFIANCE", "1")), 1)
    if entrees:
        ip = entrees[-rang] if len(entrees) >= rang else entrees[0]
        return ip.rsplit(":", 1)[0] if ip.count(":") == 1 else ip  # App Service ajoute parfois ":port"
    return request.client.host if request.client else "-"


class _Limiteur:
    """Limitation de débit en mémoire, par IP et par route (fenêtre glissante).

    Limite assumée : le compteur est propre à chaque instance et remis à zéro au redémarrage. Pour plusieurs
    instances ou une vraie protection, utiliser Azure Front Door / API Management (voir docs/03-securite.md).
    """

    def __init__(self) -> None:
        self._appels: dict[tuple[str, str], deque] = {}
        self._verrou = threading.Lock()

    def autoriser(self, cle: tuple[str, str], maximum: int, fenetre: float) -> float:
        """0 si l'appel est autorisé, sinon le nombre de secondes à attendre."""
        maintenant = time.monotonic()
        with self._verrou:
            if len(self._appels) > 10_000:  # purge des IP inactives : la mémoire reste bornée
                self._appels = {k: v for k, v in self._appels.items() if v and v[-1] > maintenant - 3600}
            appels = self._appels.setdefault(cle, deque())
            while appels and appels[0] <= maintenant - fenetre:
                appels.popleft()
            if len(appels) >= maximum:
                return appels[0] + fenetre - maintenant
            appels.append(maintenant)
            return 0.0

    def reinitialiser(self) -> None:
        with self._verrou:
            self._appels.clear()


limiteur = _Limiteur()


def limiter_debit(nom: str, maximum: int, fenetre_secondes: int):
    """Dépendance FastAPI : au plus `maximum` appels par IP sur la fenêtre, sinon 429."""

    def verifier(request: Request) -> None:
        attente = limiteur.autoriser((nom, ip_client(request)), maximum, fenetre_secondes)
        if attente:
            raise HTTPException(
                429,
                "Trop de requêtes : réessayez plus tard",
                headers={"Retry-After": str(int(attente) + 1)},
            )

    return verifier


# Identifiant de corrélation de la requête en cours, propagé aux appels sortants et au message de file.
_id_requete: contextvars.ContextVar[str] = contextvars.ContextVar("id_requete", default="-")
MOTIF_ID_REQUETE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def id_requete() -> str:
    return _id_requete.get()


def entetes_correlation() -> dict:
    """En-têtes à ajouter à tout appel vers un autre service."""
    return {"X-Request-ID": id_requete()} if id_requete() != "-" else {}


class _FiltreCorrelation(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = id_requete()  # visible dans les journaux et transmis à Application Insights
        return True


def activer_application_insights(app: FastAPI) -> bool:
    """Application Insights (OpenTelemetry), seulement si APPLICATIONINSIGHTS_CONNECTION_STRING est défini.
    Requêtes, dépendances HTTP, exceptions et journaux partent vers Azure Monitor."""
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    os.environ.setdefault("OTEL_SERVICE_NAME", app.title)  # nom du rôle dans la cartographie d'Application Insights
    configure_azure_monitor(logger_name="")
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health$")
    return True


def configurer(app: FastAPI, database_url: str | None = None) -> None:
    """CORS, corrélation X-Request-ID, journal d'accès, /health/db et Application Insights (si configuré)."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
    )
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, _FiltreCorrelation) for f in handler.filters):
            handler.addFilter(_FiltreCorrelation())
    activer_application_insights(app)

    if database_url:

        @app.get("/health/db")
        def health_db():
            """Disponibilité de la base : la connexion et une requête simple doivent aboutir en 3 secondes."""
            debut = time.perf_counter()
            try:
                with psycopg.connect(database_url, connect_timeout=3) as conn:
                    conn.execute("SELECT 1")
            except psycopg.Error:
                logging.getLogger("health").exception("Base de données injoignable")
                return JSONResponse({"status": "erreur", "db": "injoignable"}, status_code=503)
            return {"status": "ok", "db": "ok", "duree_ms": round((time.perf_counter() - debut) * 1000)}

    origines = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if origines:
        app.add_middleware(
            CORSMiddleware, allow_origins=origines, allow_methods=["*"], allow_headers=["*"]
        )

    @app.middleware("http")
    async def journaliser(request: Request, call_next):
        """Journal d'accès et corrélation : X-Request-ID reçu (passerelle, autre service) ou généré, puis renvoyé."""
        debut = time.perf_counter()
        recu = request.headers.get("x-request-id", "")
        jeton_ctx = _id_requete.set(recu if MOTIF_ID_REQUETE.fullmatch(recu) else uuid.uuid4().hex)
        try:
            reponse = await call_next(request)
            reponse.headers["X-Request-ID"] = id_requete()
            access_log.info(
                "%s %s -> %s (%.0f ms) ip=%s",
                request.method,
                request.url.path,
                reponse.status_code,
                (time.perf_counter() - debut) * 1000,
                ip_client(request),
            )
            return reponse
        finally:
            _id_requete.reset(jeton_ctx)
