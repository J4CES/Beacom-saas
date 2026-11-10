"""Hachage des mots de passe (scrypt, bibliothèque standard) et jetons JWT."""
import base64
import hashlib
import hmac
import os
import time

import jwt

ALGORITHM = "HS256"
_N, _R, _P = 2**14, 8, 1


def _secret() -> str:
    secret = os.environ["JWT_SECRET"]
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET doit faire au moins 32 caractères")
    return secret


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode())


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    sel = os.urandom(16)
    h = hashlib.scrypt(mot_de_passe.encode(), salt=sel, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(sel)}${_b64(h)}"


def verifier_mot_de_passe(mot_de_passe: str, stocke: str) -> bool:
    try:
        algo, n, r, p, sel, h = stocke.split("$")
        if algo != "scrypt":
            return False
        attendu = _b64d(h)
        calcule = hashlib.scrypt(
            mot_de_passe.encode(), salt=_b64d(sel), n=int(n), r=int(r), p=int(p), dklen=len(attendu)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calcule, attendu)


def creer_jeton(user_id: int, email: str, role: str, minutes: int | None = None) -> tuple[str, int]:
    """Retourne (jeton, durée de validité en secondes)."""
    minutes = minutes or int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    maintenant = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": maintenant,
        "exp": maintenant + minutes * 60,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM), minutes * 60
