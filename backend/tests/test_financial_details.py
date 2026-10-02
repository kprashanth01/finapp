"""Optional real-user detail must remain account-owned and descriptive of saved totals."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from tests.support import AuthenticatedTestClient


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'details.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    with AuthenticatedTestClient(app) as current:
        yield current
    app.dependency_overrides.clear()
    engine.dispose()


def account(client, email="details@example.org"):
    user_id = client.post("/users", json={
        "name": "Detail user", "email": email, "monthly_income": "50000",
    }).json()["id"]
    assert client.sign_in(email).status_code == 200
    profile = {
        "monthly_expenses": "30000", "savings": "25000", "existing_debt": "100000",
        "emergency_fund": "10000", "monthly_savings_contribution": "5000",
        "monthly_debt_payments": "5000", "risk_tolerance": "moderate",
        "investment_horizon_years": 5,
    }
    assert client.put(f"/users/{user_id}/financial-profile", json=profile).status_code == 200
    return user_id, profile


def details(**overrides):
    value = {
        "income_pattern": "variable", "guaranteed_monthly_income": "10000",
        "recurring_expenses": [{
            "name": "Rent", "monthly_amount": "14000", "category": "essential_fixed",
        }],
        "loans": [{
            "name": "Education loan", "remaining_balance": "80000",
            "monthly_payment": "4000", "loan_type": "education",
            "annual_interest_rate_percent": "10.50", "payment_day": 5,
            "rate_change_date": "2027-03-01", "new_annual_interest_rate_percent": "11.00",
        }],
        "planned_expenses": [{
            "name": "Trip", "estimated_amount": "20000", "amount_reserved": "2500",
            "due_date": "2027-06-01", "is_essential": False,
        }],
    }
    value.update(overrides)
    return value


def test_details_are_optional_and_can_be_saved_without_changing_the_current_plan(client):
    user_id, _ = account(client)
    path = f"/users/{user_id}/financial-details"
    empty = client.get(path)
    assert empty.status_code == 200
    assert empty.json()["income_pattern"] is None
    assert empty.json()["recurring_expenses"] == []
    assert empty.json()["loans"] == []
    assert empty.json()["planned_expenses"] == []

    before = client.post(f"/users/{user_id}/advisory-sessions").json()
    saved = client.put(path, json=details())
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["guaranteed_monthly_income"] == "10000.00"
    assert data["recurring_expenses"][0]["name"] == "Rent"
    assert data["loans"][0]["monthly_payment"] == "4000.00"
    assert data["planned_expenses"][0]["amount_reserved"] == "2500.00"
    assert data["subtotals"]["recurring_monthly"] == "14000.00"
    assert data["subtotals"]["loan_monthly_payments"] == "4000.00"
    assert client.get(path).json() == data
    assert client.get(f"/users/{user_id}/advisory-sessions/{before['id']}").status_code == 200
    after = client.post(f"/users/{user_id}/advisory-sessions").json()
    assert after["result"]["advice"] == before["result"]["advice"]


def test_details_replace_rows_and_preserve_owned_ids(client):
    user_id, _ = account(client)
    path = f"/users/{user_id}/financial-details"
    saved = client.put(path, json=details()).json()
    expense = saved["recurring_expenses"][0]
    updated = details(
        recurring_expenses=[{
            "id": expense["id"], "name": "Rent", "monthly_amount": "15000",
            "category": "essential_fixed",
        }],
        loans=[], planned_expenses=[],
    )
    response = client.put(path, json=updated)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["recurring_expenses"][0]["id"] == expense["id"]
    assert value["recurring_expenses"][0]["monthly_amount"] == "15000.00"
    assert value["loans"] == []
    assert value["planned_expenses"] == []


def test_details_reject_foreign_or_repeated_ids(client):
    owner, _ = account(client)
    owner_path = f"/users/{owner}/financial-details"
    owner_expense = client.put(owner_path, json=details()).json()["recurring_expenses"][0]
    other, _ = account(client, "other-detail@example.org")
    other_path = f"/users/{other}/financial-details"
    foreign = details(recurring_expenses=[{
        "id": owner_expense["id"], "name": "Rent", "monthly_amount": "100",
        "category": "essential_fixed",
    }], loans=[], planned_expenses=[])
    assert client.put(other_path, json=foreign).status_code == 422
    assert client.get(other_path).json()["recurring_expenses"] == []
    assert client.get(owner_path).status_code == 404
    assert client.sign_in("details@example.org").status_code == 200
    repeated = details(recurring_expenses=[foreign["recurring_expenses"][0]] * 2,
                       loans=[], planned_expenses=[])
    assert client.put(owner_path, json=repeated).status_code == 422
    assert len(client.get(owner_path).json()["recurring_expenses"]) == 1


@pytest.mark.parametrize("change", [
    {"guaranteed_monthly_income": "60000"},
    {"recurring_expenses": [{"name": "Everything", "monthly_amount": "26000", "category": "discretionary"}]},
    {"loans": [{"name": "Loan", "remaining_balance": "100001", "monthly_payment": "100"}]},
    {"loans": [{"name": "Loan", "remaining_balance": "1000", "monthly_payment": "5001"}]},
    {"planned_expenses": [{"name": "Trip", "estimated_amount": "500", "amount_reserved": "600", "due_date": "2027-06-01", "is_essential": False}]},
])
def test_details_reject_inconsistent_amounts(client, change):
    user_id, _ = account(client)
    response = client.put(f"/users/{user_id}/financial-details", json=details(**change))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("change", [
    {"monthly_expenses": "18000"},
    {"existing_debt": "70000"},
    {"monthly_debt_payments": "3000"},
])
def test_profile_edit_cannot_undercut_saved_detail(client, change):
    user_id, profile = account(client)
    client.put(f"/users/{user_id}/financial-details", json=details())
    response = client.put(f"/users/{user_id}/financial-profile", json={
        **profile, **change,
    })
    assert response.status_code == 422
    assert client.get(f"/users/{user_id}/financial-profile").json()["monthly_expenses"] == "30000.00"


def test_loan_detail_does_not_turn_an_unknown_aggregate_payment_into_zero(client):
    user_id, profile = account(client)
    assert client.put(f"/users/{user_id}/financial-profile", json={
        **profile, "monthly_debt_payments": None,
    }).status_code == 200
    path = f"/users/{user_id}/financial-details"
    saved = client.put(path, json=details())
    assert saved.status_code == 200, saved.text
    assert saved.json()["subtotals"]["loan_monthly_payments"] == "4000.00"
    assert client.get(f"/users/{user_id}/financial-profile").json()["monthly_debt_payments"] is None
    plan = client.post(f"/users/{user_id}/advisory-sessions").json()["result"]
    assert plan["state"]["monthly_debt_payments"] is None
    assert plan["state"]["debt_to_income_percent"] is None
    overfilled = details(recurring_expenses=[{
        "name": "Other spending", "monthly_amount": "27000", "category": "discretionary",
    }])
    assert client.put(path, json=overfilled).status_code == 422


def test_user_income_edit_cannot_fall_below_entered_guarantee(client):
    user_id, _ = account(client)
    assert client.put(f"/users/{user_id}/financial-details", json=details()).status_code == 200
    response = client.put(f"/users/{user_id}", json={
        "name": "Detail user", "email": "details@example.org", "monthly_income": "9000",
    })
    assert response.status_code == 422
    assert client.get(f"/users/{user_id}").json()["monthly_income"] == "50000.00"


def test_unreported_money_reserved_for_a_planned_expense_stays_unknown(client):
    user_id, _ = account(client)
    payload = details(planned_expenses=[{
        "name": "Annual insurance", "estimated_amount": "12000", "due_date": "2027-01-01",
        "is_essential": True,
    }])
    response = client.put(f"/users/{user_id}/financial-details", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["planned_expenses"][0]["amount_reserved"] is None
    assert response.json()["subtotals"]["planned_reserved"] is None


def test_unreported_loan_payment_stays_unknown(client):
    user_id, _ = account(client)
    payload = details(loans=[{
        "name": "Family loan", "remaining_balance": "20000",
    }])
    response = client.put(f"/users/{user_id}/financial-details", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["loans"][0]["monthly_payment"] is None
    assert response.json()["subtotals"]["loan_monthly_payments"] is None


def test_unreported_individual_loan_balance_stays_unknown(client):
    user_id, _ = account(client)
    payload = details(loans=[{
        "name": "Vehicle loan", "monthly_payment": "2500",
    }])
    response = client.put(f"/users/{user_id}/financial-details", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["loans"][0]["remaining_balance"] is None
    assert response.json()["subtotals"]["loan_balance"] is None
