"""Құпиясөздер PBKDF2, токендер SHA-256 дайджесті арқылы сақталады."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .db import get_session
from .models import AuthSession, User, utcnow

ITERATIONS = 600_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def issue_session(session: Session, user: User) -> dict:
    token = secrets.token_urlsafe(32)
    session.add(AuthSession(token_hash=token_digest(token), user_id=user.id,
                            expires_at=utcnow() + timedelta(hours=24)))
    session.commit()
    # "bearer" names the HTTP authentication scheme; it is not a secret credential.
    token_type = "bearer"  # nosec B105
    return {"access_token": token, "token_type": token_type, "user": public_user(user)}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 session: Session = Depends(get_session)) -> User:
    if credentials is None:
        raise HTTPException(401, "Алдымен жүйеге кіріңіз.", headers={"WWW-Authenticate": "Bearer"})
    auth = session.exec(select(AuthSession).where(
        AuthSession.token_hash == token_digest(credentials.credentials),
        AuthSession.expires_at > utcnow())).first()
    if auth is None:
        raise HTTPException(401, "Сессия аяқталды. Қайта кіріңіз.", headers={"WWW-Authenticate": "Bearer"})
    user = session.get(User, auth.user_id)
    if user is None:
        raise HTTPException(401, "Пайдаланушы табылмады.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Бұл әрекет тек әкімшіге қолжетімді.")
    return user
