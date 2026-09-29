from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_core import issue_legacy_claim
from app.database import Base, get_session
from app.main import app
from app.models import AuthSession, User


MUTATION = {"X-FinApp-Request": "1"}


@pytest.fixture
def auth_client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'auth_api.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = override
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def signup(client, email="one@example.org"):
    return client.post("/users", headers=MUTATION,
                       json={"name": "Account One", "email": email,
                             "password": "a secure passphrase 123"})


def test_signup_restores_identity_from_httponly_cookie(auth_client):
    client, engine = auth_client
    response = signup(client)
    assert response.status_code == 201
    assert response.json()["monthly_income"] == "0.00"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert client.get("/auth/me").json()["id"] == response.json()["id"]
    with Session(engine) as db:
        user = db.get(User, response.json()["id"])
        assert user.password_hash.startswith("$argon2id$")
        assert "a secure passphrase 123" not in user.password_hash
        assert db.scalar(select(AuthSession)).token_digest not in cookie
    assert response.headers["cache-control"] == "no-store"


def test_login_wrong_credentials_logout_and_expiry(auth_client):
    client, engine = auth_client
    signup(client)
    assert client.post("/auth/logout", headers=MUTATION).status_code == 204
    assert client.get("/auth/me").status_code == 401
    invalid = client.post("/auth/login", headers=MUTATION,
                          json={"email": "one@example.org", "password": "wrong passphrase 123"})
    assert invalid.status_code == 401
    missing = client.post("/auth/login", headers=MUTATION,
                          json={"email": "missing@example.org", "password": "wrong passphrase 123"})
    assert missing.status_code == 401
    assert invalid.json()["detail"] == missing.json()["detail"]
    valid = client.post("/auth/login", headers=MUTATION,
                        json={"email": "ONE@example.org", "password": "a secure passphrase 123"})
    assert valid.status_code == 200
    assert client.get("/auth/me").status_code == 200
    with Session(engine) as db:
        row = db.scalar(select(AuthSession).where(AuthSession.revoked_at.is_(None)))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me").status_code == 401


def test_legacy_claim_requires_code_and_preserves_user_id(auth_client):
    client, engine = auth_client
    with Session(engine) as db:
        user = User(name="Earlier User", email="old@example.org", monthly_income=5000)
        db.add(user)
        db.commit()
        legacy_id = user.id
        code = issue_legacy_claim(user)
        db.commit()
    assert signup(client, "OLD@example.org").status_code == 409
    assert client.post("/auth/login", headers=MUTATION,
                       json={"email": "old@example.org", "password": "a secure passphrase 123"}).status_code == 401
    wrong = client.post("/auth/claim", headers=MUTATION,
                        json={"email": "old@example.org", "code": "bad", "password": "a secure passphrase 123"})
    assert wrong.status_code == 401
    claimed = client.post("/auth/claim", headers=MUTATION,
                          json={"email": "old@example.org", "code": code,
                                "password": "a secure passphrase 123"})
    assert claimed.status_code == 200
    assert claimed.json()["id"] == legacy_id
    assert client.get("/auth/me").json()["id"] == legacy_id
    assert client.post("/auth/claim", headers=MUTATION,
                       json={"email": "old@example.org", "code": code,
                             "password": "another passphrase 123"}).status_code == 401


def test_mutations_require_header_and_trusted_origin(auth_client):
    client, _ = auth_client
    payload = {"name": "New", "email": "new@example.org", "password": "a secure passphrase 123"}
    assert client.post("/users", json=payload).status_code == 403
    assert client.post("/users", json=payload,
                       headers={**MUTATION, "Origin": "http://evil.example"}).status_code == 403
    assert client.post("/users", json=payload,
                       headers={**MUTATION, "Origin": "http://127.0.0.1:5173"}).status_code == 201
    cors = client.options("/users", headers={"Origin": "http://127.0.0.1:5173",
                                            "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "x-finapp-request"})
    assert cors.status_code == 200
    assert cors.headers["access-control-allow-credentials"] == "true"


def test_login_attempts_are_throttled_per_email_and_client(auth_client):
    client, _ = auth_client
    for _ in range(5):
        response = client.post("/auth/login", headers=MUTATION,
                               json={"email": "missing@example.org", "password": "wrong passphrase 123"})
        assert response.status_code == 401
    blocked = client.post("/auth/login", headers=MUTATION,
                          json={"email": "missing@example.org", "password": "wrong passphrase 123"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]
