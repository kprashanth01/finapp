from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_core import (
    consume_legacy_claim,
    hash_password,
    issue_legacy_claim,
    new_session,
    resolve_session,
    revoke_session,
    verify_password,
)
from app.database import Base
from app.legacy_claim import main as legacy_claim_main
from app.models import AuthSession, User


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'auth.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def legacy_user(db):
    user = User(name="Saved user", email="saved@example.org", monthly_income=5000)
    db.add(user)
    db.commit()
    return user


def test_password_hash_is_argon2_and_verifies_without_plaintext():
    digest = hash_password("a long private passphrase")
    assert digest.startswith("$argon2id$")
    assert "a long private passphrase" not in digest
    assert verify_password("a long private passphrase", digest)
    assert not verify_password("different passphrase", digest)


def test_opaque_session_stores_only_digest_and_can_expire_or_revoke(db):
    user = legacy_user(db)
    now = datetime(2026, 9, 29, tzinfo=timezone.utc)
    token = new_session(db, user, now)
    db.commit()
    row = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    assert len(token) >= 40
    assert token not in str(row.__dict__)
    assert row.token_digest == sha256(token.encode()).hexdigest()
    assert resolve_session(db, token, now + timedelta(days=6)).id == user.id
    assert resolve_session(db, token, now + timedelta(days=7)) is None
    revoke_session(db, token, now + timedelta(days=1))
    db.commit()
    assert resolve_session(db, token, now + timedelta(days=1)) is None


def test_legacy_code_rotates_expires_and_can_only_be_consumed_once(db):
    user = legacy_user(db)
    original_id = user.id
    now = datetime(2026, 9, 29, tzinfo=timezone.utc)
    first = issue_legacy_claim(user, now)
    second = issue_legacy_claim(user, now)
    assert first != second
    assert first not in str(user.__dict__)
    assert not consume_legacy_claim(user, first, "another long passphrase", now)
    assert not consume_legacy_claim(user, second, "another long passphrase", now + timedelta(minutes=30))
    assert consume_legacy_claim(user, second, "another long passphrase", now + timedelta(minutes=29))
    db.commit()
    assert user.id == original_id
    assert verify_password("another long passphrase", user.password_hash)
    assert user.legacy_claim_digest is None
    assert not consume_legacy_claim(user, second, "different long passphrase", now)


def test_local_claim_command_prints_code_once_for_existing_unclaimed_user(db, monkeypatch, capsys):
    user = legacy_user(db)
    monkeypatch.setattr("app.legacy_claim.get_engine", lambda: db.get_bind())
    assert legacy_claim_main(["--email", "SAVED@example.org"]) == 0
    printed = capsys.readouterr().out
    code = printed.split("Claim code: ")[1].splitlines()[0]
    db.expire_all()
    assert db.get(User, user.id).legacy_claim_digest == sha256(code.encode()).hexdigest()
    assert code not in str(db.get(User, user.id).__dict__)
