"""Session and account ownership dependencies for all private API routes."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth_core import resolve_session
from app.database import get_session
from app.models import User


def session_cookie_name(request: Request) -> str:
    if request.url.scheme == "http" and request.url.hostname in {"localhost", "127.0.0.1"}:
        return "finapp_dev_session"
    return "__Host-finapp_session"


def session_cookie(request: Request) -> str | None:
    return request.cookies.get(session_cookie_name(request))


def require_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    user = resolve_session(db, session_cookie(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def require_owner(user_id: int, current_user: User = Depends(require_current_user)) -> User:
    if current_user.id != user_id:
        raise HTTPException(status_code=404, detail="Record not found.")
    return current_user
