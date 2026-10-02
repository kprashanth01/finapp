"""Issue 3 financial facts must be deterministic and honest about missing inputs."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace as Row

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from app.services.financial_picture import build_financial_picture
from tests.support import AuthenticatedTestClient


def base(**changes):
    values = dict(monthly_expenses=Decimal("3000"), monthly_debt_payments=Decimal("200"),
                  monthly_savings_contribution=Decimal("500"), emergency_fund=Decimal("4000"),
                  guaranteed_monthly_income=None)
    values.update(changes)
    return Row(**values)


def picture(profile=None, *, expenses=(), loans=(), plans=(), goals=(), months=(),
            income=Decimal("5000"), as_of=date(2026, 10, 2)):
    return build_financial_picture(Row(monthly_income=income), profile or base(),
                                   expenses=expenses, loans=loans, plans=plans, goals=goals,
                                   months=months, as_of_date=as_of)


def test_complete_spending_breakdown_and_signed_cash_flow():
    rows = [Row(monthly_amount=Decimal("1500"), category="essential_fixed"),
            Row(monthly_amount=Decimal("500"), category="essential_variable"),
            Row(monthly_amount=Decimal("800"), category="discretionary")]
    result = picture(expenses=rows)
    assert result.spending.exact_essential.value == Decimal("2200")
    assert result.spending.exact_discretionary.value == Decimal("800")
    assert result.spending.unclassified_monthly.value == 0
    assert result.spending.gross_cash_flow.value == Decimal("2000")
    assert result.spending.available_surplus_upper_bound.status == "estimate"
    assert result.spending.entered_savings_capacity.value == Decimal("500")
    assert result.spending.savings_rate_percent.value == Decimal("10.00")
    assert result.spending.debt_to_income_percent.value == Decimal("4.00")
    assert result.reserve.total_expense_coverage_months.value == Decimal("1.33")
    assert result.reserve.essential_coverage_months.value == Decimal("1.82")
    assert result.reserve.funding_gap.value == Decimal("5000")

    short = picture(income=Decimal("2500"))
    assert short.spending.gross_cash_flow.value == Decimal("-500")
    assert short.spending.available_surplus_upper_bound.value == 0


def test_partial_breakdown_and_missing_debt_stay_unknown():
    rows = [Row(monthly_amount=Decimal("1000"), category="essential_fixed")]
    result = picture(base(monthly_debt_payments=None), expenses=rows,
                     loans=[Row(monthly_payment=Decimal("400"), payment_day=None, id=1, name="Loan")])
    assert result.spending.known_essential.value == Decimal("1000")
    assert result.spending.known_essential.status == "partial"
    assert result.spending.unclassified_monthly.value is None
    assert result.spending.exact_essential.value is None
    assert result.spending.debt_to_income_percent.value is None
    assert result.reserve.essential_coverage_months.value is None
    assert result.obligations[0].due_date is None


def test_income_history_distinguishes_observation_from_reference():
    months = [Row(period=date(2026, 7, 1), monthly_income=Decimal("4000")),
              Row(period=date(2026, 8, 1), monthly_income=Decimal("2000")),
              Row(period=date(2026, 9, 1), monthly_income=Decimal("3000"))]
    result = picture(months=months)
    assert result.income.observed_average.value == Decimal("3000.00")
    assert result.income.observed_recent.value == Decimal("3000")
    assert result.income.observed_minimum.value == Decimal("2000")
    assert result.income.variability_percent.value == Decimal("27.22")
    assert result.income.conservative_reference.value == Decimal("2000")
    assert result.income.conservative_reference.status == "estimate"
    assert result.income.guaranteed_monthly.value is None
    assert result.income.recent_period == date(2026, 9, 1)
    assert picture(months=months[:2]).income.conservative_reference.value is None
    assert picture(months=months, as_of=date(2027, 1, 1)).income.conservative_reference.value is None
    assert picture(months=months[::2]).income.variability_percent.value is not None


def test_goal_gaps_one_time_costs_overdue_items_and_loan_due_day():
    result = picture(
        goals=[Row(id=1, name="Laptop", target_amount=Decimal("1000"), saved_amount=Decimal("300"),
                   target_date=date(2027, 1, 1), priority="high", archived=False),
               Row(id=2, name="Old", target_amount=Decimal("100"), saved_amount=Decimal("0"),
                   target_date=date(2026, 1, 1), priority="low", archived=True)],
        plans=[Row(id=3, name="Insurance", estimated_amount=Decimal("800"), amount_reserved=Decimal("200"),
                   due_date=date(2026, 11, 1), is_essential=True),
               Row(id=4, name="Repair", estimated_amount=Decimal("100"), amount_reserved=None,
                   due_date=date(2026, 9, 1), is_essential=True)],
        loans=[Row(id=5, name="Vehicle", monthly_payment=Decimal("200"), payment_day=31)],
        as_of=date(2026, 10, 31),
    )
    assert result.goal_funding_gap.value == Decimal("700")
    assert len(result.goals) == 1
    assert result.planned_due_90_days.value == Decimal("800")
    assert result.unreserved_due_90_days.value == Decimal("600")
    assert next(row for row in result.obligations if row.id == 4).is_overdue
    loan = next(row for row in result.obligations if row.kind == "loan_payment")
    assert loan.due_date == date(2026, 10, 31)
    assert loan.unreserved_amount is None
    assert picture(plans=[Row(id=1, name="Trip", estimated_amount=Decimal("100"), amount_reserved=None,
                              due_date=date(2026, 11, 1), is_essential=False)]).unreserved_due_90_days.value is None


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'picture.db').as_posix()}",
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


def test_analysis_endpoint_uses_only_account_records(client):
    first = client.post("/users", json={"name": "First", "email": "picture-first@example.org", "monthly_income": "5000"}).json()["id"]
    second = client.post("/users", json={"name": "Second", "email": "picture-second@example.org", "monthly_income": "7000"}).json()["id"]
    assert client.sign_in("picture-first@example.org").status_code == 200
    profile = {"monthly_expenses": "3000", "savings": "8000", "existing_debt": "1000",
               "emergency_fund": "4000", "monthly_savings_contribution": "500",
               "monthly_debt_payments": "200", "risk_tolerance": "moderate"}
    assert client.put(f"/users/{first}/financial-profile", json=profile).status_code == 200
    assert client.put(f"/users/{first}/financial-details", json={
        "income_pattern": "variable", "guaranteed_monthly_income": "1000",
        "recurring_expenses": [{"name": "Rent", "monthly_amount": "1000", "category": "essential_fixed"}],
        "loans": [], "planned_expenses": [],
    }).status_code == 200
    analysis = client.get(f"/users/{first}/financial-analysis")
    assert analysis.status_code == 200, analysis.text
    data = analysis.json()
    assert data["picture"]["schema_version"] == "financial-picture-v1"
    assert data["picture"]["spending"]["known_essential"]["value"] == "1200.00"
    assert data["picture"]["income"]["guaranteed_monthly"]["value"] == "1000.00"
    assert client.get(f"/users/{second}/financial-analysis").status_code == 404


def test_analysis_endpoint_reads_saved_month_goals_and_upcoming_cost(client):
    user_id = client.post("/users", json={"name": "History", "email": "picture-history@example.org",
                                          "monthly_income": "5000"}).json()["id"]
    assert client.sign_in("picture-history@example.org").status_code == 200
    profile = {"monthly_expenses": "3000", "savings": "8000", "existing_debt": "1000",
               "emergency_fund": "4000", "monthly_savings_contribution": "500",
               "monthly_debt_payments": "200", "risk_tolerance": "moderate"}
    assert client.put(f"/users/{user_id}/financial-profile", json=profile).status_code == 200
    period = date.today().replace(day=1).isoformat()
    month = {"period": period, "monthly_income": "3500", "monthly_expenses": "3000",
             "fixed_expenses": "1000", "scheduled_emi": "200", "paid_emi": "200",
             "savings": "8000", "emergency_fund": "4000", "outstanding_debt": "1000",
             "risk_tolerance": "moderate", "investment_horizon_years": 5}
    assert client.put(f"/users/{user_id}/financial-months/{period}", json=month).status_code == 200
    due = (date.today() + timedelta(days=30)).isoformat()
    assert client.put(f"/users/{user_id}/financial-details", json={
        "income_pattern": "variable", "guaranteed_monthly_income": None,
        "recurring_expenses": [], "loans": [],
        "planned_expenses": [{"name": "Insurance", "estimated_amount": "800",
                              "amount_reserved": None, "due_date": due, "is_essential": True}],
    }).status_code == 200
    goal = client.post(f"/users/{user_id}/goals", json={
        "name": "Laptop", "target_amount": "1000", "saved_amount": "300",
        "target_date": due, "priority": "high",
    })
    assert goal.status_code == 201, goal.text
    response = client.get(f"/users/{user_id}/financial-analysis")
    assert response.status_code == 200, response.text
    data = response.json()["picture"]
    assert data["income"]["observed_recent"]["value"] == "3500.00"
    assert data["income"]["conservative_reference"]["value"] is None
    assert data["goal_funding_gap"]["value"] == "700.00"
    assert data["planned_due_90_days"]["value"] == "800.00"
    assert data["unreserved_due_90_days"]["value"] is None
