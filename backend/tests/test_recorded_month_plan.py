"""A recorded month can preview a current coordinated plan without changing saved data."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from tests.support import AuthenticatedTestClient


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'recorded-plan.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with AuthenticatedTestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def account(client, email="month-plan@example.org"):
    user = client.post("/users", json={"name": "Month Planner", "email": email,
                                       "monthly_income": "5000.00"}).json()
    profile = {
        "monthly_expenses": "3000.00", "savings": "8000.00", "existing_debt": "1000.00",
        "emergency_fund": "4000.00", "monthly_savings_contribution": "500.00",
        "monthly_debt_payments": "200.00", "risk_tolerance": "moderate",
        "investment_horizon_years": 7,
    }
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    return user, profile


def record(client, user_id, *, period="2026-09-01", income="3500.00", expenses="3000.00"):
    values = {
        "period": period, "monthly_income": income, "monthly_expenses": expenses,
        "fixed_expenses": "1800.00", "scheduled_emi": "300.00", "paid_emi": "300.00",
        "savings": "5500.00", "emergency_fund": "2500.00", "outstanding_debt": "4000.00",
        "unfunded_expenses": "0.00", "risk_tolerance": "conservative",
        "investment_horizon_years": 3,
    }
    response = client.put(f"/users/{user_id}/financial-months/{period}", json=values)
    assert response.status_code == 200, response.text
    return values


def test_recorded_month_preview_uses_month_values_current_goals_and_entered_savings(client):
    user, profile = account(client)
    month = record(client, user["id"])
    goal = client.post(f"/users/{user['id']}/goals", json={
        "name": "Laptop", "target_amount": "12000.00", "saved_amount": "0.00",
        "target_date": (date.today() + timedelta(days=365)).isoformat(), "priority": "high",
    }).json()
    path = f"/users/{user['id']}/financial-months/{month['period']}/plan-preview"
    response = client.post(path, json={"monthly_savings_contribution": "300.00"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_period"] == month["period"]
    state = body["result"]["state"]
    assert state["monthly_income"] == month["monthly_income"]
    assert state["monthly_expenses"] == month["monthly_expenses"]
    assert state["monthly_debt_payments"] == month["scheduled_emi"]
    assert state["existing_debt"] == month["outstanding_debt"]
    assert state["emergency_fund"] == month["emergency_fund"]
    assert state["risk_tolerance"] == month["risk_tolerance"]
    assert state["monthly_savings_contribution"] == "300.00"
    assert state["goals"][0]["id"] == goal["id"]
    plan = body["result"]["advice"]["monthly_plan"]
    assert plan["capacity"] == "300.00"
    assert plan["emergency_allocation"] == "300.00"
    assert client.get(f"/users/{user['id']}/advisory-sessions").json()["items"] == []
    assert client.get(f"/users/{user['id']}").json()["monthly_income"] == "5000.00"
    assert client.get(f"/users/{user['id']}/financial-profile").json()["monthly_savings_contribution"] == profile["monthly_savings_contribution"]
    assert client.get(f"/users/{user['id']}/financial-months").json()[0]["monthly_income"] == month["monthly_income"]


def test_recorded_month_preview_does_not_infer_savings_from_a_shortfall(client):
    user, _ = account(client)
    month = record(client, user["id"], income="1500.00")
    path = f"/users/{user['id']}/financial-months/{month['period']}/plan-preview"
    unknown = client.post(path, json={"monthly_savings_contribution": None})
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["result"]["advice"]["monthly_plan"]["capacity"] is None
    zero = client.post(path, json={"monthly_savings_contribution": "0.00"})
    assert zero.status_code == 200, zero.text
    assert zero.json()["result"]["advice"]["monthly_plan"]["capacity"] == "0.00"
    assert client.post(path, json={"monthly_savings_contribution": "1.00"}).status_code == 422
    assert client.post(path, json={"monthly_savings_contribution": "-1.00"}).status_code == 422


def test_recorded_month_preview_rejects_excess_and_other_account_month(client):
    user, _ = account(client)
    month = record(client, user["id"])
    path = f"/users/{user['id']}/financial-months/{month['period']}/plan-preview"
    too_much = client.post(path, json={"monthly_savings_contribution": "501.00"})
    assert too_much.status_code == 422
    assert "income minus expenses" in too_much.json()["detail"]
    assert client.post(f"/users/{user['id']}/financial-months/2026-08-01/plan-preview",
                       json={"monthly_savings_contribution": None}).status_code == 404
    other, _ = account(client, "other-month-plan@example.org")
    assert client.post(path, json={"monthly_savings_contribution": None}).status_code == 404
    assert client.post(f"/users/{other['id']}/financial-months/{month['period']}/plan-preview",
                       json={"monthly_savings_contribution": None}).status_code == 404


def test_unpaid_recorded_obligations_block_a_new_funded_allocation(client):
    user, _ = account(client)
    month = record(client, user["id"])
    record_path = f"/users/{user['id']}/financial-months/{month['period']}"
    plan_path = f"{record_path}/plan-preview"
    month["paid_emi"] = "100.00"
    assert client.put(record_path, json=month).status_code == 200
    missed = client.post(plan_path, json={"monthly_savings_contribution": "100.00"})
    assert missed.status_code == 422
    assert "loan payment" in missed.json()["detail"]
    assert client.post(plan_path, json={"monthly_savings_contribution": None}).status_code == 200
    month["paid_emi"] = month["scheduled_emi"]
    month["unfunded_expenses"] = "50.00"
    assert client.put(record_path, json=month).status_code == 200
    unfunded = client.post(plan_path, json={"monthly_savings_contribution": "100.00"})
    assert unfunded.status_code == 422
    assert "unfunded" in unfunded.json()["detail"]
