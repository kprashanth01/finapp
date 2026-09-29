"""Opaque browser sessions, password hashes, and one-time legacy claim codes."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthSession, User


PASSWORD_HASHER = PasswordHash.recommended()
SESSION_LIFETIME = timedelta(days=7)
CLAIM_LIFETIME = timedelta(minutes=30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, digest: str | None) -> bool:
    if not digest:
        return False
    try:
        return PASSWORD_HASHER.verify(password, digest)
    except (ValueError, TypeError):
        return False


def new_session(db: Session, user: User, now: datetime | None = None) -> str:
    now = now or utc_now()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=user.id, token_digest=token_digest(token),
                       created_at=now, expires_at=now + SESSION_LIFETIME))
    db.flush()
    return token


def resolve_session(db: Session, token: str | None, now: datetime | None = None) -> User | None:
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(token)))
    now = now or utc_now()
    if row is None or row.revoked_at is not None or _aware(row.expires_at) <= now:
        return None
    return db.get(User, row.user_id)


def revoke_session(db: Session, token: str | None, now: datetime | None = None) -> None:
    if not token:
        return
    row = db.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = now or utc_now()


def issue_legacy_claim(user: User, now: datetime | None = None) -> str:
    if user.password_hash:
        raise ValueError("The account is already claimed.")
    now = now or utc_now()
    code = secrets.token_urlsafe(32)
    user.legacy_claim_digest = token_digest(code)
    user.legacy_claim_expires_at = now + CLAIM_LIFETIME
    return code


def consume_legacy_claim(user: User, code: str, password: str, now: datetime | None = None) -> bool:
    now = now or utc_now()
    digest = user.legacy_claim_digest
    if (user.password_hash or not digest or user.legacy_claim_expires_at is None or
            _aware(user.legacy_claim_expires_at) <= now or
            not hmac.compare_digest(digest, token_digest(code))):
        return False
    user.password_hash = hash_password(password)
    user.legacy_claim_digest = None
    user.legacy_claim_expires_at = None
    return True
