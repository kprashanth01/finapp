"""Account-entered months reach the real DQN without altering the profile."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app


HEADERS = {"X-FinApp-Request": "1"}


@pytest.fixture
def clients(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'months.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = override
    with (TestClient(app, base_url="http://127.0.0.1") as owner,
          TestClient(app, base_url="http://127.0.0.1") as other,
          TestClient(app, base_url="http://127.0.0.1") as anonymous):
        yield owner, other, anonymous
    app.dependency_overrides.clear()
    engine.dispose()


def signup(client, email):
    response = client.post("/users", headers=HEADERS, json={
        "name": email.split("@")[0], "email": email,
        "password": "a secure passphrase 123", "monthly_income": "5000",
    })
    assert response.status_code == 201
    return response.json()["id"]


def month(period, income):
    return {
        "period": period, "monthly_income": income, "monthly_expenses": "3500",
        "fixed_expenses": "2500", "scheduled_emi": "500", "paid_emi": "500",
        "savings": "7000", "emergency_fund": "4500", "outstanding_debt": "10000",
        "unfunded_expenses": "0", "risk_tolerance": "moderate", "investment_horizon_years": 5,
    }


def test_owner_enters_two_months_and_model_uses_income_drop(clients):
    owner, other, anonymous = clients
    user_id = signup(owner, "owner@example.org")
    signup(other, "other@example.org")
    base = f"/users/{user_id}/financial-months"
    first = month("2026-08-01", "6000")
    second = month("2026-09-01", "1500")
    assert owner.put(f"{base}/{first['period']}", headers=HEADERS, json=first).status_code == 200
    assert owner.put(f"{base}/{second['period']}", headers=HEADERS, json=second).status_code == 200
    assert [row["period"] for row in owner.get(base).json()] == [first["period"], second["period"]]
    assert anonymous.get(base).status_code == 401
    assert other.get(base).status_code == 404
    assert other.put(f"{base}/{second['period']}", headers=HEADERS, json=second).status_code == 404
    assert other.get(f"{base}/{second['period']}/advice").status_code == 404

    result = owner.get(f"{base}/{second['period']}/advice")
    assert result.status_code == 200, result.text
    advice = result.json()
    assert advice["source"] == "account_entered_months"
    assert advice["context"]["recent_income_change_ratio"] == "-0.75"
    assert advice["context"]["observed_low_income"] is True
    assert advice["methods"]["trained_rl"]["selected_agents"]
    assert advice["methods"]["trained_rl"]["priority_actions"]
    assert advice["methods"]["rule_based"]["selected_agents"]

    focused = owner.get(f"{base}/{second['period']}/advice", params={"focus": "debt"}).json()
    assert focused["focused_review"]["agent_id"] == "debt"
    assert focused["focused_review"]["selected_by_dqn"] is True

    second["monthly_income"] = "0"
    assert owner.put(f"{base}/{second['period']}", headers=HEADERS, json=second).status_code == 200
    assert len(owner.get(base).json()) == 2
    zero = owner.get(f"{base}/{second['period']}/advice", params={"focus": "debt"}).json()
    assert zero["context"]["net_cash_flow"] == "-3500.00"
    assert "debt" in zero["methods"]["trained_rl"]["reward_audit"]["missed_critical_agents"]
    assert zero["focused_review"]["selected_by_dqn"] is False
    assert zero["methods"]["rule_based"]["recommendation"]["status"] == "complete"
    ask = f"{base}/{second['period']}/ask"
    assert anonymous.post(ask, headers=HEADERS, json={"question": "What now?"}).status_code == 401
    assert other.post(ask, headers=HEADERS, json={"question": "What now?"}).status_code == 404
    assert owner.delete(f"{base}/{second['period']}", headers=HEADERS).status_code == 204
    assert len(owner.get(base).json()) == 1


def test_month_rejects_inconsistent_finances(clients):
    owner, _, _ = clients
    user_id = signup(owner, "owner@example.org")
    base = f"/users/{user_id}/financial-months/2026-09-01"
    invalid = month("2026-09-01", "5000")
    invalid["monthly_expenses"] = "100"
    assert owner.put(base, headers=HEADERS, json=invalid).status_code == 422
    invalid = month("2026-09-01", "5000")
    invalid["emergency_fund"] = "8000"
    assert owner.put(base, headers=HEADERS, json=invalid).status_code == 422
    assert owner.put(base, headers=HEADERS, json=month("2026-08-01", "5000")).status_code == 422
