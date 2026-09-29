import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'advisory.db').as_posix()}",
        connect_args={"check_same_thread": False},
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


def create_profile(client, email="example@sample-finapp.org"):
    user = client.post(
        "/users",
        json={"name": "Example User", "email": email, "monthly_income": "5000.00"},
    ).json()
    profile = {
        "monthly_expenses": "3000.00",
        "savings": "8000.00",
        "existing_debt": "1000.00",
        "emergency_fund": "4000.00",
        "monthly_savings_contribution": "500.00",
        "monthly_debt_payments": "200.00",
        "risk_tolerance": "moderate",
        "investment_horizon_years": 7,
    }
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    return user, profile


def test_run_persists_result_and_latest_can_reload_it(client):
    user, _ = create_profile(client)
    path = f"/users/{user['id']}/advisory-sessions"
    created = client.post(path)
    assert created.status_code == 201
    session = created.json()
    assert session["id"] > 0
    assert session["method"] == "rule_based"
    assert session["is_stale"] is False
    assert session["result"]["advice"]["priority_actions"][0]["source_refs"][0]["agent_id"] == "emergency"
    assert session["result"]["agent_results"][2]["findings"][0]["evidence"][1]["value"] == "5000.00"

    latest = client.get(f"{path}/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == session["id"]
    assert latest.json()["result"] == session["result"]


def test_run_requires_saved_user_and_profile(client):
    missing_user = client.post("/users/999/advisory-sessions")
    assert missing_user.status_code == 404
    assert missing_user.json()["detail"] == "User not found."
    user = client.post(
        "/users",
        json={"name": "No Profile", "email": "none@sample-finapp.org", "monthly_income": "5000"},
    ).json()
    path = f"/users/{user['id']}/advisory-sessions"
    missing_profile = client.post(path)
    assert missing_profile.status_code == 404
    assert missing_profile.json()["detail"] == "Financial profile not found."
    assert client.get(f"{path}/latest").status_code == 404


def test_profile_edit_marks_old_run_stale_without_rewriting_it(client):
    user, profile = create_profile(client)
    path = f"/users/{user['id']}/advisory-sessions"
    first = client.post(path).json()
    profile["emergency_fund"] = "12000.00"
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200

    stale = client.get(f"{path}/latest").json()
    assert stale["id"] == first["id"]
    assert stale["is_stale"] is True
    assert stale["result"] == first["result"]

    second = client.post(path).json()
    assert second["id"] != first["id"]
    assert second["is_stale"] is False
    assert second["result"]["advice"]["priority_actions"] == []
    assert client.get(f"{path}/latest").json()["id"] == second["id"]


def test_identity_edit_does_not_mark_financial_run_stale(client):
    user, _ = create_profile(client)
    path = f"/users/{user['id']}/advisory-sessions"
    assert client.post(path).status_code == 201
    assert client.put(
        f"/users/{user['id']}",
        json={"name": "Renamed User", "email": "renamed@sample-finapp.org", "monthly_income": "5000.00"},
    ).status_code == 200
    assert client.get(f"{path}/latest").json()["is_stale"] is False


def test_history_empty_and_missing_user(client):
    user = client.post(
        "/users",
        json={"name": "No Profile", "email": "empty@sample-finapp.org", "monthly_income": "5000"},
    ).json()
    path = f"/users/{user['id']}/advisory-sessions"
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_before_id": None}
    assert client.get("/users/999/advisory-sessions").status_code == 404


def test_history_orders_pages_and_reports_stale_summaries(client):
    user, profile = create_profile(client)
    path = f"/users/{user['id']}/advisory-sessions"
    first = client.post(path).json()
    profile["emergency_fund"] = "12000.00"
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    second = client.post(path).json()
    profile["emergency_fund"] = "4000.00"
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200
    third = client.post(path).json()

    page = client.get(path, params={"limit": 2})
    assert page.status_code == 200
    assert [item["id"] for item in page.json()["items"]] == [third["id"], second["id"]]
    assert page.json()["next_before_id"] == second["id"]
    assert page.json()["items"][0]["priority_titles"] == ["Review emergency reserve"]
    assert page.json()["items"][0]["priority_count"] == 1
    assert page.json()["items"][0]["is_stale"] is False
    assert page.json()["items"][1]["priority_titles"] == []
    assert page.json()["items"][1]["is_stale"] is True

    last = client.get(path, params={"limit": 1, "before_id": second["id"]})
    assert last.status_code == 200
    assert [item["id"] for item in last.json()["items"]] == [first["id"]]
    assert last.json()["next_before_id"] is None
    assert client.get(path, params={"before_id": first["id"]}).json()["items"] == []
    assert client.get(path, params={"limit": 0}).status_code == 422
    assert client.get(path, params={"limit": 51}).status_code == 422


def test_history_detail_is_owned_and_immutable(client):
    user, profile = create_profile(client)
    other, _ = create_profile(client, email="other@sample-finapp.org")
    path = f"/users/{user['id']}/advisory-sessions"
    original = client.post(path).json()
    profile["emergency_fund"] = "12000.00"
    assert client.put(f"/users/{user['id']}/financial-profile", json=profile).status_code == 200

    detail = client.get(f"{path}/{original['id']}")
    assert detail.status_code == 200
    assert detail.json()["is_stale"] is True
    assert detail.json()["result"] == original["result"]
    assert detail.json()["result"]["state"]["emergency_fund"] == "4000.00"
    assert client.get(f"/users/{other['id']}/advisory-sessions").json() == {
        "items": [], "next_before_id": None
    }
    assert client.get(f"/users/{other['id']}/advisory-sessions/{original['id']}").status_code == 404
    assert client.get(f"{path}/999").status_code == 404


def test_goal_edits_archive_and_planning_date_freshness(client, monkeypatch):
    from datetime import date
    import app.api as api
    monkeypatch.setattr(api, 'planning_date', lambda: date(2026,9,29))
    user,_=create_profile(client)
    goals=f"/users/{user['id']}/goals"
    path=f"/users/{user['id']}/advisory-sessions"
    values=dict(name='Course',target_amount='6000',saved_amount='0',target_date='2027-09-24',priority='high')
    g=client.post(goals,json=values).json()
    first=client.post(path).json()
    values['saved_amount']='100'
    client.put(f"{goals}/{g['id']}",json=values)
    assert client.get(f'{path}/latest').json()['stale_reasons'] == ['inputs']
    client.patch(f"{goals}/{g['id']}",json={'archived':True})
    no_goals=client.post(path).json()
    values['saved_amount']='200'
    client.put(f"{goals}/{g['id']}",json=values)
    assert client.get(f'{path}/latest').json()['is_stale'] is False
    monkeypatch.setattr(api, 'planning_date', lambda: date(2026,9,30))
    assert client.get(f'{path}/latest').json()['stale_reasons'] == ['planning_date']
    client.patch(f"{goals}/{g['id']}",json={'archived':False})
    assert client.get(f'{path}/latest').json()['stale_reasons'] == ['inputs','planning_date']
    assert client.get(f"{path}/{first['id']}").json()['result'] == first['result']
    assert client.get(f"{path}/{no_goals['id']}").json()['result']['state']['goals'] == []


@pytest.mark.parametrize('explicit_version', [True, False])
def test_fixed_v1_payload_reads_without_new_fields(client, explicit_version):
    import json
    from pathlib import Path
    from app.models import AnalysisSession
    from app.advisory.types import AdvisoryResult
    from app.advisory.session_types import get_priority_actions
    user,_=create_profile(client)
    payload=json.loads((Path(__file__).parent/'fixtures/advisory_v1.json').read_text())
    if not explicit_version:
        payload['state'].pop('schema_version')
    assert get_priority_actions(AdvisoryResult.model_validate(payload))[0].title == 'Review emergency reserve'
    with next(app.dependency_overrides[get_session]()) as db:
        row=AnalysisSession(user_id=user['id'],method='rule_based',rule_version='rule-based-v1',
                            input_fingerprint=payload['state']['input_fingerprint'],result_payload=payload)
        db.add(row); db.commit(); db.refresh(row); row_id=row.id
    path=f"/users/{user['id']}/advisory-sessions"
    for suffix in ('latest',str(row_id)):
        result=client.get(f'{path}/{suffix}').json()
        expected = {**payload, 'state': {'schema_version': 'financial-state-v1', **payload['state']}}
        assert result['result'] == expected
        assert result['stale_reasons'] == ['rule_version']
        assert 'advice' not in result['result']
        assert 'goals' not in result['result']['state']
    assert client.get(path).json()['items'][0]['priority_titles'] == ['Review emergency reserve']
    with next(app.dependency_overrides[get_session]()) as db:
        assert db.get(AnalysisSession,row_id).result_payload == payload
