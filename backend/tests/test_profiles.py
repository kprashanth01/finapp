import pytest
from tests.support import AuthenticatedTestClient
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
    with AuthenticatedTestClient(app) as test_client:
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


def test_analysis_uses_monthly_flows_instead_of_balances(client):
    user = client.post(
        "/users",
        json={"name": "Analysis User", "email": "analysis@sample-finapp.org", "monthly_income": "5000.00"},
    )
    user_id = user.json()["id"]
    profile = client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "3000.00",
            "savings": "50000.00",
            "existing_debt": "20000.00",
            "emergency_fund": "9000.00",
            "risk_tolerance": "moderate",
            "monthly_savings_contribution": "500.00",
            "monthly_debt_payments": "500.00",
        },
    )
    assert profile.status_code == 200
    assert profile.json()["monthly_debt_payments"] == "500.00"

    response = client.get(f"/users/{user_id}/financial-analysis")
    assert response.status_code == 200
    assert response.json() == {
        "savings_rate_percent": "10.00",
        "debt_to_income_percent": "10.00",
        "expense_to_income_percent": "60.00",
        "emergency_fund_months": "3.00",
        "health_score": 59,
    }


def test_existing_profile_without_monthly_flows_has_partial_analysis(client):
    user = client.post(
        "/users",
        json={"name": "Existing User", "email": "existing@sample-finapp.org", "monthly_income": "5000.00"},
    )
    user_id = user.json()["id"]
    client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "3000.00",
            "savings": "8000.00",
            "existing_debt": "1000.00",
            "emergency_fund": "4000.00",
            "risk_tolerance": "moderate",
        },
    )

    response = client.get(f"/users/{user_id}/financial-analysis")
    assert response.status_code == 200
    assert response.json() == {
        "savings_rate_percent": None,
        "debt_to_income_percent": None,
        "expense_to_income_percent": "60.00",
        "emergency_fund_months": "1.33",
        "health_score": None,
    }


def test_zero_income_and_expenses_leave_undefined_ratios_unavailable(client):
    user = client.post(
        "/users",
        json={"name": "Zero User", "email": "zero@sample-finapp.org", "monthly_income": "0.00"},
    )
    user_id = user.json()["id"]
    client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "0.00",
            "savings": "0.00",
            "existing_debt": "0.00",
            "emergency_fund": "0.00",
            "risk_tolerance": "conservative",
            "monthly_savings_contribution": "0.00",
            "monthly_debt_payments": "0.00",
        },
    )

    response = client.get(f"/users/{user_id}/financial-analysis")
    assert response.status_code == 200
    assert response.json() == {
        "savings_rate_percent": None,
        "debt_to_income_percent": None,
        "expense_to_income_percent": None,
        "emergency_fund_months": None,
        "health_score": None,
    }


def test_negative_monthly_flow_is_rejected_without_changing_profile(client):
    user = client.post(
        "/users",
        json={"name": "Validation User", "email": "validation@sample-finapp.org", "monthly_income": "5000.00"},
    )
    user_id = user.json()["id"]
    valid = {
        "monthly_expenses": "3000.00",
        "savings": "8000.00",
        "existing_debt": "1000.00",
        "emergency_fund": "4000.00",
        "risk_tolerance": "moderate",
        "monthly_savings_contribution": "500.00",
        "monthly_debt_payments": "200.00",
    }
    assert client.put(f"/users/{user_id}/financial-profile", json=valid).status_code == 200
    invalid = {**valid, "monthly_debt_payments": "-1.00"}
    assert client.put(f"/users/{user_id}/financial-profile", json=invalid).status_code == 422
    saved = client.get(f"/users/{user_id}/financial-profile")
    assert saved.json()["monthly_debt_payments"] == "200.00"


def test_debt_payments_cannot_exceed_total_expenses(client):
    user = client.post(
        "/users",
        json={"name": "Expense User", "email": "expense@sample-finapp.org", "monthly_income": "5000.00"},
    )
    user_id = user.json()["id"]
    response = client.put(
        f"/users/{user_id}/financial-profile",
        json={
            "monthly_expenses": "300.00",
            "savings": "0.00",
            "existing_debt": "1000.00",
            "emergency_fund": "0.00",
            "risk_tolerance": "moderate",
            "monthly_debt_payments": "500.00",
        },
    )
    assert response.status_code == 422
    assert client.get(f"/users/{user_id}/financial-profile").status_code == 404
