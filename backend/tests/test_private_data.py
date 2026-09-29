import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from app.models import User


MUTATION = {"X-FinApp-Request": "1"}


@pytest.fixture
def accounts(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'private.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = override
    with (TestClient(app, base_url="http://127.0.0.1") as first,
          TestClient(app, base_url="http://127.0.0.1") as second,
          TestClient(app, base_url="http://127.0.0.1") as anonymous):
        yield first, second, anonymous, engine
    app.dependency_overrides.clear()
    engine.dispose()


def signup(client, email):
    response = client.post("/users", headers=MUTATION,
                           json={"name": email.split("@")[0], "email": email,
                                 "password": "a secure passphrase 123", "monthly_income": "5000"})
    assert response.status_code == 201
    return response.json()["id"]


PROFILE = {"monthly_expenses": "3000", "savings": "8000", "existing_debt": "1000",
           "emergency_fund": "4000", "monthly_savings_contribution": "500",
           "monthly_debt_payments": "200", "risk_tolerance": "moderate"}
GOAL = {"name": "Course", "target_amount": "6000", "saved_amount": "1000",
        "target_date": "2027-08-29", "priority": "high"}


def test_every_private_path_requires_account_and_exact_owner(accounts):
    first, second, anonymous, _ = accounts
    owner, other = signup(first, "first@example.org"), signup(second, "second@example.org")
    owner_path = f"/users/{owner}"
    assert first.put(f"{owner_path}/financial-profile", headers=MUTATION, json=PROFILE).status_code == 200
    goal = first.post(f"{owner_path}/goals", headers=MUTATION, json=GOAL).json()
    run = first.post(f"{owner_path}/advisory-sessions", headers=MUTATION).json()
    paths = [owner_path, f"{owner_path}/financial-profile", f"{owner_path}/financial-analysis",
             f"{owner_path}/goals", f"{owner_path}/advisory-sessions",
             f"{owner_path}/advisory-sessions/latest",
             f"{owner_path}/advisory-sessions/{run['id']}"]
    for path in paths:
        assert anonymous.get(path).status_code == 401, path
        assert second.get(path).status_code == 404, path
    assert second.put(owner_path, headers=MUTATION,
                      json={"name": "Hacked", "email": "first@example.org", "monthly_income": "0"}).status_code == 404
    assert second.put(f"{owner_path}/financial-profile", headers=MUTATION, json=PROFILE).status_code == 404
    assert second.post(f"{owner_path}/goals", headers=MUTATION, json=GOAL).status_code == 404
    assert second.put(f"{owner_path}/goals/{goal['id']}", headers=MUTATION, json=GOAL).status_code == 404
    assert second.patch(f"{owner_path}/goals/{goal['id']}", headers=MUTATION,
                        json={"archived": True}).status_code == 404
    assert second.post(f"{owner_path}/advisory-sessions", headers=MUTATION).status_code == 404
    assert anonymous.post(f"{owner_path}/research/comparison", headers=MUTATION, json={"seed": 1}).status_code == 401
    assert second.post(f"{owner_path}/research/comparison", headers=MUTATION, json={"seed": 1}).status_code == 404
    assert anonymous.get(f"{owner_path}/research/actions").status_code == 401
    assert second.get(f"{owner_path}/research/actions").status_code == 404
    manual = f"{owner_path}/research/manual-action"
    assert anonymous.post(manual, headers=MUTATION, json={"selected_agents": ["budget"]}).status_code == 401
    assert second.post(manual, headers=MUTATION, json={"selected_agents": ["budget"]}).status_code == 404
    assert first.get(f"{owner_path}/advisory-sessions/{run['id']}").status_code == 200
    assert first.get(f"/users/{other}/advisory-sessions/{run['id']}").status_code == 404


def test_legacy_user_id_in_browser_is_not_an_authorization_token(accounts):
    _, _, anonymous, engine = accounts
    with Session(engine) as db:
        legacy = User(name="Old local record", email="old@example.org", monthly_income=5000)
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
    assert anonymous.get(f"/users/{legacy_id}").status_code == 401
    assert anonymous.get(f"/users/{legacy_id}/goals").status_code == 401
