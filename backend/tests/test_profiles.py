import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app


@pytest.fixture
def client(tmp_path):
    # API behavior is checked quickly here; the migration is verified against PostgreSQL separately.
    db_path = (tmp_path / "profiles.db").as_posix()
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_user_profile_can_be_saved_and_reloaded(client):
    user_response = client.post(
        "/users",
        json={
            "name": "Example User",
            "email": "example@sample-finapp.org",
            "monthly_income": "5000.00",
        },
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    edited_user = client.put(
        f"/users/{user_id}",
        json={
            "name": "Example User",
            "email": "example@sample-finapp.org",
            "monthly_income": "5200.00",
        },
    )
    assert edited_user.status_code == 200
    assert client.get(f"/users/{user_id}").json()["monthly_income"] == "5200.00"

    profile_response = client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "3000.00",
            "savings": "8000.00",
            "existing_debt": "1000.00",
            "emergency_fund": "4000.00",
            "risk_tolerance": "moderate",
        },
    )
    assert profile_response.status_code == 200

    saved = client.get(f"/users/{user_id}/financial-profile")
    assert saved.status_code == 200
    assert saved.json()["monthly_expenses"] == "3000.00"
    assert saved.json()["risk_tolerance"] == "moderate"

    updated = client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "2800.00",
            "savings": "8000.00",
            "existing_debt": "1000.00",
            "emergency_fund": "4000.00",
            "risk_tolerance": "conservative",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == saved.json()["id"]
    assert client.get(f"/users/{user_id}/financial-profile").json()["monthly_expenses"] == "2800.00"


def test_invalid_amount_does_not_create_a_profile(client):
    user = client.post(
        "/users",
        json={
            "name": "Another User",
            "email": "another@sample-finapp.org",
            "monthly_income": "4500.00",
        },
    )
    assert user.status_code == 201
    user_id = user.json()["id"]

    invalid = client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "-1.00",
            "savings": "0.00",
            "existing_debt": "0.00",
            "emergency_fund": "0.00",
            "risk_tolerance": "moderate",
        },
    )
    assert invalid.status_code == 422
    assert client.get(f"/users/{user_id}/financial-profile").status_code == 404


def test_duplicate_email_is_rejected(client):
    payload = {
        "name": "Example User",
        "email": "duplicate@sample-finapp.org",
        "monthly_income": "5000.00",
    }
    assert client.post("/users", json=payload).status_code == 201
    assert client.post("/users", json=payload).status_code == 409
