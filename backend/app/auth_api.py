"""Signup, login, current account, logout, and legacy account claim."""

import hashlib
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_core import (
    hash_password, verify_password, new_session, revoke_session,
    consume_legacy_claim, utc_now,
)
from app.auth_dependencies import require_current_user, session_cookie, session_cookie_name
from app.database import get_session
from app.models import AuthFailure, User
from app.schemas import Money, Name, UserRead


router = APIRouter(tags=["accounts"])
FAILURE_WINDOW = timedelta(minutes=15)
MAX_FAILURES = 5
DUMMY_HASH = hash_password("invalid account placeholder password")


class Signup(BaseModel):
    name: Name
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    monthly_income: Money = Decimal("0")
    age: int | None = Field(default=None, ge=0, le=120)
    occupation: str | None = Field(default=None, max_length=100)


class Login(BaseModel):
    email: EmailStr
    password: str


class Claim(Login):
    code: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=12, max_length=128)


def _email(value: str) -> str:
    return value.strip().lower()


def _set_cookie(response: Response, request: Request, token: str) -> None:
    secure = session_cookie_name(request).startswith("__Host-")
    response.set_cookie(key=session_cookie_name(request), value=token, max_age=7 * 24 * 60 * 60,
                        path="/", httponly=True, secure=secure, samesite="strict")


def _failure_keys(request: Request, email: str) -> tuple[str, str]:
    address = request.client.host if request.client else "unknown"
    return (hashlib.sha256(email.encode()).hexdigest(), hashlib.sha256(address.encode()).hexdigest())


def _too_many_failures(db: Session, keys: tuple[str, str]) -> bool:
    cutoff = utc_now() - FAILURE_WINDOW
    count = db.query(AuthFailure).filter(
        AuthFailure.email_digest == keys[0], AuthFailure.ip_digest == keys[1],
        AuthFailure.created_at >= cutoff,
    ).count()
    return count >= MAX_FAILURES


@router.post("/users", response_model=UserRead, status_code=201)
def signup(payload: Signup, request: Request, response: Response, db: Session = Depends(get_session)) -> User:
    email = _email(payload.email)
    user = User(name=payload.name, email=email, password_hash=hash_password(payload.password),
                monthly_income=payload.monthly_income, age=payload.age, occupation=payload.occupation)
    db.add(user)
    try:
        db.flush()
        token = new_session(db, user)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account cannot be created with that email.") from error
    db.refresh(user)
    _set_cookie(response, request, token)
    return user


@router.post("/auth/login", response_model=UserRead)
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_session)) -> User:
    email = _email(payload.email)
    keys = _failure_keys(request, email)
    if _too_many_failures(db, keys):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.",
                            headers={"Retry-After": "900"})
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not verify_password(payload.password, user.password_hash if user and user.password_hash else DUMMY_HASH):
        db.add(AuthFailure(email_digest=keys[0], ip_digest=keys[1], created_at=utc_now()))
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = new_session(db, user)
    db.execute(delete(AuthFailure).where(AuthFailure.email_digest == keys[0], AuthFailure.ip_digest == keys[1]))
    db.commit()
    _set_cookie(response, request, token)
    return user


@router.get("/auth/me", response_model=UserRead)
def current_account(user: User = Depends(require_current_user)) -> User:
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_session)) -> None:
    revoke_session(db, session_cookie(request))
    db.commit()
    response.delete_cookie(session_cookie_name(request), path="/", samesite="strict")


@router.post("/auth/claim", response_model=UserRead)
def claim(payload: Claim, request: Request, response: Response, db: Session = Depends(get_session)) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == _email(payload.email)).with_for_update())
    if user is None or not consume_legacy_claim(user, payload.code, payload.password):
        raise HTTPException(status_code=401, detail="Invalid or expired claim details.")
    token = new_session(db, user)
    db.commit()
    _set_cookie(response, request, token)
    return user
