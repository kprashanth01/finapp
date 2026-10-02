"""A scenario changes calculated facts for one preview, never saved account data."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from tests.support import AuthenticatedTestClient


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'events.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    with AuthenticatedTestClient(app) as current:
        yield current
    app.dependency_overrides.clear()
    engine.dispose()


def account(client, email="events@example.org"):
    user = client.post("/users", json={"name": "Example", "email": email, "monthly_income": "5000"}).json()
    assert client.sign_in(email).status_code == 200
    profile = {"monthly_expenses": "3000", "savings": "8000", "existing_debt": "1000",
               "emergency_fund": "4000", "monthly_savings_contribution": "500",
               "monthly_debt_payments": "200", "risk_tolerance": "moderate"}
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    return user['id'], profile


def preview(client, user_id, **event):
    return client.post(f"/users/{user_id}/event-scenario", json=event)


def test_income_events_change_current_estimate_without_rewriting_history(client):
    user_id, _ = account(client)
    lower = preview(client, user_id, kind="income_decrease", amount="1500")
    assert lower.status_code == 200, lower.text
    data = lower.json()
    assert data["before"]["income"]["expected_monthly"]["value"] == "5000.00"
    assert data["after"]["income"]["expected_monthly"]["value"] == "3500.00"
    assert data["after"]["spending"]["gross_cash_flow"]["value"] == "500.00"
    assert data["after"]["income"]["expected_monthly"]["source"].startswith("scenario.")
    assert data["one_time_cash_need"] == "0"
    assert client.get(f"/users/{user_id}").json()["monthly_income"] == "5000.00"
    assert preview(client, user_id, kind="income_increase", amount="200").json()["after"]["income"]["expected_monthly"]["value"] == "5200.00"
    assert preview(client, user_id, kind="income_decrease", amount="5001").status_code == 422


def test_one_time_expense_is_separate_from_monthly_spending(client):
    user_id, _ = account(client)
    now = preview(client, user_id, kind="unexpected_expense", amount="800", reserved_amount="100")
    assert now.status_code == 200, now.text
    data = now.json()
    assert data["after"]["spending"]["monthly_total"]["value"] == "3000.00"
    assert data["after"]["planned_due_90_days"]["value"] == "800.00"
    assert data["after"]["planned_due_90_days"]["source"].startswith("scenario.")
    assert data["one_time_cash_need"] == "700.00"
    assert data["illustrative_current_month_cash_after_event"] == "1300.00"
    assert client.get(f"/users/{user_id}/financial-details").json()["planned_expenses"] == []

    due = (date.today() + timedelta(days=30)).isoformat()
    future = preview(client, user_id, kind="upcoming_expense", amount="900", reserved_amount="200", due_date=due,
                     is_essential=True)
    assert future.status_code == 200, future.text
    assert future.json()["after"]["unreserved_due_90_days"]["value"] == "700.00"
    assert future.json()["after"]["obligations"][0]["is_essential"] is True
    assert future.json()["illustrative_current_month_cash_after_event"] is None
    assert preview(client, user_id, kind="upcoming_expense", amount="900", due_date="2020-01-01").status_code == 422


def test_one_time_extra_income_changes_only_this_months_illustrative_cash(client):
    user_id, _ = account(client)
    result = preview(client, user_id, kind="one_time_income", amount="1500")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["before"]["income"]["expected_monthly"]["value"] == "5000.00"
    assert data["after"]["income"]["expected_monthly"]["value"] == "5000.00"
    assert data["one_time_cash_inflow"] == "1500.00"
    assert data["illustrative_current_month_cash_after_event"] == "3500.00"
    assert client.get(f"/users/{user_id}").json()["monthly_income"] == "5000.00"


def test_subscription_reduction_uses_owned_discretionary_item(client):
    user_id, _ = account(client)
    details = client.put(f"/users/{user_id}/financial-details", json={
        "income_pattern": "stable", "guaranteed_monthly_income": None,
        "recurring_expenses": [{"name": "Streaming", "monthly_amount": "100", "category": "discretionary"},
                               {"name": "Rent", "monthly_amount": "1000", "category": "essential_fixed"}],
        "loans": [], "planned_expenses": [],
    }).json()
    streaming, rent = (row["id"] for row in details["recurring_expenses"])
    response = preview(client, user_id, kind="subscription_reduction", amount="60", expense_id=streaming)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["after"]["spending"]["monthly_total"]["value"] == "2940.00"
    assert data["after"]["spending"]["known_discretionary"]["value"] == "40.00"
    assert data["after"]["spending"]["gross_cash_flow"]["value"] == "2060.00"
    assert preview(client, user_id, kind="subscription_reduction", amount="101", expense_id=streaming).status_code == 422
    assert preview(client, user_id, kind="subscription_reduction", amount="1", expense_id=rent).status_code == 422
    assert client.get(f"/users/{user_id}/financial-details").json()["recurring_expenses"][0]["monthly_amount"] == "100.00"


def test_extra_loan_payment_and_emergency_deposit_do_not_change_saved_balances(client):
    user_id, profile = account(client)
    details = client.put(f"/users/{user_id}/financial-details", json={
        "income_pattern": "stable", "guaranteed_monthly_income": None,
        "recurring_expenses": [], "loans": [{"name": "Vehicle", "remaining_balance": "800",
                                           "monthly_payment": "200", "payment_day": 15}],
        "planned_expenses": [],
    }).json()
    loan_id = details["loans"][0]["id"]
    payment = preview(client, user_id, kind="additional_loan_payment", amount="300", loan_id=loan_id)
    assert payment.status_code == 200, payment.text
    assert payment.json()["loan_effect"] == {"loan_id": loan_id, "balance_before": "800.00", "balance_after": "500.00"}
    assert payment.json()["after"]["spending"]["monthly_total"]["value"] == "3000.00"
    assert payment.json()["one_time_cash_need"] == "300.00"
    assert preview(client, user_id, kind="additional_loan_payment", amount="801", loan_id=loan_id).status_code == 422
    savings = preview(client, user_id, kind="additional_savings", amount="500")
    assert savings.status_code == 200, savings.text
    assert savings.json()["before"]["reserve"]["funding_gap"]["value"] == "5000.00"
    assert savings.json()["after"]["reserve"]["funding_gap"]["value"] == "4500.00"
    assert client.get(f"/users/{user_id}/financial-profile").json()["emergency_fund"] == profile["emergency_fund"] + ".00"
    assert client.get(f"/users/{user_id}/financial-details").json()["loans"][0]["remaining_balance"] == "800.00"


def test_goal_contribution_change_compares_selected_goal_without_saving(client):
    user_id, profile = account(client)
    profile["emergency_fund"] = "9000"
    assert client.put(f"/users/{user_id}/financial-profile", json=profile).status_code == 200
    goal = client.post(f"/users/{user_id}/goals", json={"name": "Laptop", "target_amount": "12000",
        "saved_amount": "0", "target_date": (date.today() + timedelta(days=365)).isoformat(),
        "priority": "high"}).json()
    result = preview(client, user_id, kind="goal_contribution_change", amount="300", goal_id=goal["id"])
    assert result.status_code == 200, result.text
    effect = result.json()["goal_effect"]
    assert effect["goal_id"] == goal["id"]
    assert effect["current_plan_allocation"] == "500.00"
    assert effect["hypothetical_contribution"] == "300.00"
    assert result.json()["after"]["spending"]["entered_savings_capacity"]["value"] == "500.00"
    assert client.get(f"/users/{user_id}/financial-profile").json()["monthly_savings_contribution"] == "500.00"
    over_budget = preview(client, user_id, kind="goal_contribution_change", amount="700", goal_id=goal["id"])
    assert over_budget.status_code == 200, over_budget.text
    assert over_budget.json()["goal_effect"]["budget_shortfall"] == "200.00"


def test_event_endpoint_is_account_scoped(client):
    first, _ = account(client, "first-events@example.org")
    second, _ = account(client, "second-events@example.org")
    assert preview(client, first, kind="unexpected_expense", amount="100").status_code == 404
    assert preview(client, second, kind="unexpected_expense", amount="100").status_code == 200
