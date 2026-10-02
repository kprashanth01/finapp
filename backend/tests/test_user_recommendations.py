"""Current decisions must use saved facts, dated obligations, and user goal priorities."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace as Row

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from tests.support import AuthenticatedTestClient


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'decisions.db').as_posix()}",
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


def account(client, email="decisions@example.org", income="5000", expenses="3000", reserve="4000"):
    user = client.post("/users", json={"name": "Example", "email": email, "monthly_income": income}).json()
    assert client.sign_in(email).status_code == 200
    profile = {"monthly_expenses": expenses, "savings": "8000", "existing_debt": "1000",
               "emergency_fund": reserve, "monthly_savings_contribution": "500",
               "monthly_debt_payments": "200", "risk_tolerance": "moderate"}
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    return user["id"]


def test_overdue_essential_cost_and_current_shortfall_outrank_reserve(client):
    user_id = account(client, income="2500")
    overdue = (date.today() - timedelta(days=2)).isoformat()
    saved = client.put(f"/users/{user_id}/financial-details", json={
        "income_pattern": "stable", "guaranteed_monthly_income": None,
        "recurring_expenses": [], "loans": [],
        "planned_expenses": [{"name": "Insurance", "estimated_amount": "800",
                              "amount_reserved": "100", "due_date": overdue, "is_essential": True}],
    })
    assert saved.status_code == 200, saved.text
    response = client.get(f"/users/{user_id}/recommendations")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema_version"] == "user-recommendations-v1"
    items = data["recommendations"]
    assert items[0]["area"] == "upcoming_cost"
    assert items[0]["priority"] == 1
    assert items[0]["supporting_calculations"][0]["source"]
    assert any(item["code"] == "cash_shortfall" for item in items[:2])
    assert next(item for item in items if item["area"] == "emergency")["priority"] > 2
    assert client.get(f"/users/{user_id}/financial-details").json()["planned_expenses"][0]["estimated_amount"] == "800.00"


def test_unknown_reserved_amount_stays_unknown(client):
    user_id = account(client)
    due = (date.today() + timedelta(days=5)).isoformat()
    saved = client.put(f"/users/{user_id}/financial-details", json={
        "income_pattern": "stable", "guaranteed_monthly_income": None,
        "recurring_expenses": [], "loans": [],
        "planned_expenses": [{"name": "School fee", "estimated_amount": "900",
                              "amount_reserved": None, "due_date": due, "is_essential": True}],
    })
    assert saved.status_code == 200, saved.text

    response = client.get(f"/users/{user_id}/recommendations")
    assert response.status_code == 200, response.text
    cost = next(item for item in response.json()["recommendations"] if item["area"] == "upcoming_cost")
    assert "cannot be confirmed" in cost["reason"]
    assert next(calc for calc in cost["supporting_calculations"] if calc["label"] == "Amount not marked reserved")["value"] is None


def test_variable_income_stress_uses_recorded_months_and_known_essentials():
    from app.services.financial_picture import build_financial_picture
    from app.services.user_recommendations import recommend

    as_of = date(2026, 10, 3)
    profile = Row(monthly_expenses=Decimal("3000"), monthly_debt_payments=Decimal("200"),
                  monthly_savings_contribution=Decimal("500"), emergency_fund=Decimal("9000"),
                  guaranteed_monthly_income=None, income_pattern="variable", risk_tolerance="moderate")
    months = [Row(period=date(2026, month, 1), monthly_income=Decimal(value))
              for month, value in ((7, "4500"), (8, "1000"), (9, "5000"))]
    expenses = [Row(category="essential_fixed", monthly_amount=Decimal("1500")),
                Row(category="essential_variable", monthly_amount=Decimal("800"))]
    picture = build_financial_picture(Row(monthly_income=Decimal("5000")), profile,
                                      expenses=expenses, months=months, as_of_date=as_of)
    result = recommend(picture, profile)
    action = next(item for item in result.recommendations if item.code == "income_stress")
    assert action.priority == 1
    assert action.area == "income"
    assert any(item.value == Decimal("1000") for item in action.supporting_calculations)
    assert any(item.value == Decimal("2500") for item in action.supporting_calculations)
    assert "not a forecast" in " ".join(action.assumptions).lower()


def test_gapped_variable_income_history_asks_for_recent_consecutive_months():
    from app.services.financial_picture import build_financial_picture
    from app.services.user_recommendations import recommend

    as_of = date(2026, 10, 3)
    profile = Row(monthly_expenses=Decimal("3000"), monthly_debt_payments=Decimal("200"),
                  monthly_savings_contribution=Decimal("500"), emergency_fund=Decimal("9000"),
                  guaranteed_monthly_income=None, income_pattern="variable", risk_tolerance="moderate")
    months = [Row(period=date(2026, month, 1), monthly_income=Decimal("5000")) for month in (5, 7, 9)]
    picture = build_financial_picture(Row(monthly_income=Decimal("5000")), profile,
                                      months=months, as_of_date=as_of)
    assert picture.income.observed_months == 3
    assert picture.income.conservative_reference.value is None
    result = recommend(picture, profile)
    assert any(item.code == "income_history" for item in result.recommendations)


def test_user_goal_priority_and_deadline_affect_rank():
    from app.services.financial_picture import build_financial_picture
    from app.services.user_recommendations import recommend

    as_of = date(2026, 10, 3)
    profile = Row(monthly_expenses=Decimal("3000"), monthly_debt_payments=Decimal("200"),
                  monthly_savings_contribution=Decimal("500"), emergency_fund=Decimal("9000"),
                  guaranteed_monthly_income=None, income_pattern="stable", risk_tolerance="moderate")
    goals = [Row(id=1, name="High goal", target_amount=Decimal("1000"), saved_amount=Decimal("0"),
                 target_date=date(2026, 10, 20), priority="high", archived=False),
             Row(id=2, name="Low goal", target_amount=Decimal("1000"), saved_amount=Decimal("0"),
                 target_date=date(2026, 10, 20), priority="low", archived=False)]
    picture = build_financial_picture(Row(monthly_income=Decimal("5000")), profile,
                                      goals=goals, as_of_date=as_of)
    result = recommend(picture, profile)
    assert [item.code for item in result.recommendations[:2]] == ["goal_1", "goal_2"]
    assert "high" in " ".join(result.recommendations[0].priority_factors).lower()


def test_loan_rate_change_is_named_without_counting_payment_twice():
    from app.services.financial_picture import build_financial_picture
    from app.services.user_recommendations import recommend

    as_of = date(2026, 10, 3)
    profile = Row(monthly_expenses=Decimal("3000"), monthly_debt_payments=Decimal("200"),
                  monthly_savings_contribution=Decimal("500"), emergency_fund=Decimal("9000"),
                  guaranteed_monthly_income=None, income_pattern="stable", risk_tolerance="moderate")
    loan = Row(id=4, name="Vehicle", payment_day=8, monthly_payment=Decimal("200"),
               annual_interest_rate_percent=Decimal("8"), rate_change_date=date(2026, 10, 15),
               new_annual_interest_rate_percent=Decimal("12"))
    picture = build_financial_picture(Row(monthly_income=Decimal("5000")), profile,
                                      loans=[loan], as_of_date=as_of)
    result = recommend(picture, profile)
    change = next(item for item in result.recommendations if item.code == "loan_rate_4")
    assert change.area == "debt"
    assert any(item.value == Decimal("12") for item in change.supporting_calculations)
    assert "already included" in " ".join(change.assumptions).lower()
    assert picture.spending.monthly_total.value == Decimal("3000")


def test_recommendation_endpoint_is_owned(client):
    first = account(client, "first-decisions@example.org")
    second = account(client, "second-decisions@example.org")
    assert client.get(f"/users/{first}/recommendations").status_code == 404
    assert client.get(f"/users/{second}/recommendations").status_code == 200
