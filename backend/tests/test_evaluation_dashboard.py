"""The dashboard reads stored experiment rows, never account advisory history."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app
from app.models import AnalysisSession, Experiment, ExperimentMetric, ExperimentRun
from app.rl.evaluation_store import import_evaluation_report
from tests.support import AuthenticatedTestClient


@pytest.fixture
def dashboard_clients(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'dashboard.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = override
    with (AuthenticatedTestClient(app) as owner,
          AuthenticatedTestClient(app) as other,
          TestClient(app, base_url="http://127.0.0.1") as anonymous):
        yield owner, other, anonymous, engine
    app.dependency_overrides.clear()
    engine.dispose()


def _signup(client, email):
    response = client.post("/users", json={
        "name": "Researcher", "email": email, "monthly_income": "5000",
    })
    assert response.status_code == 201
    return response.json()["id"]


def test_dashboard_filters_stored_measurements_and_shows_unmeasured_consistency(dashboard_clients):
    owner, other, anonymous, engine = dashboard_clients
    user_id = _signup(owner, "dashboard@example.org")
    _signup(other, "other-dashboard@example.org")
    path = f"/users/{user_id}/research/experiments/latest/metrics"

    with Session(engine) as db:
        import_evaluation_report(db)

    response = owner.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "available"
    assert data["experiment"]["model_version"]
    assert len(data["rows"]) == 54  # 3 overall + 12 segment runs, with their measured metrics.
    assert {row["method"] for row in data["rows"]} == {"random", "rule_based", "rl"}
    assert list(dict.fromkeys(row["method"] for row in data["rows"])) == ["random", "rule_based", "rl"]
    assert {row["scenario"] for row in data["rows"]} >= {"overall", "low_reserve"}
    metric_availability = {option["name"]: option["available"] for option in data["filters"]["metrics"]}
    assert {"mean_reward", "risk_coverage_rate", "goal_alignment_rate", "mean_agent_calls",
            "mean_execution_ms", "reward_variance"} <= metric_availability.keys()
    assert metric_availability["recommendation_consistency"] is False

    focused = owner.get(path, params={"method": "rl", "scenario": "overall", "metric": "mean_reward"}).json()
    assert len(focused["rows"]) == 1
    assert focused["rows"][0]["value"] == 7.825
    assert focused["rows"][0]["case_count"] == 256
    assert focused["rows"][0]["scope"] == "aggregate"
    risk = owner.get(path, params={"method": "rl", "scenario": "overall",
                                   "metric": "risk_coverage_rate"}).json()
    assert risk["rows"][0]["value"] == 1.0

    segment = owner.get(path, params={"method": "random", "scenario": "low_reserve",
                                      "metric": "critical_miss_rate"}).json()
    assert len(segment["rows"]) == 1
    assert segment["rows"][0]["value"] == 0.726
    assert segment["rows"][0]["sample_count"] == 770

    seeded = owner.get(path, params={"method": "random", "scenario": "overall",
                                     "metric": "mean_reward", "scope": "seed"}).json()
    assert len(seeded["rows"]) == 5
    assert {row["seed"] for row in seeded["rows"]} == {17, 29, 43, 71, 97}

    missing = owner.get(path, params={"metric": "recommendation_consistency"}).json()
    assert missing["rows"] == []
    assert "not measured" in missing["unmeasured_reason"].lower()
    assert owner.get(path, params={"metric": "made_up"}).status_code == 422
    assert owner.get(path, params={"scenario": "made_up"}).status_code == 422
    assert anonymous.get(path).status_code == 401
    assert other.get(path).status_code == 404

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Experiment)) == 1
        assert db.scalar(select(func.count()).select_from(ExperimentRun)) == 20
        assert db.scalar(select(func.count()).select_from(ExperimentMetric)) == 104
        assert db.scalar(select(func.count()).select_from(AnalysisSession)) == 0


def test_dashboard_handles_database_with_no_experiment(dashboard_clients):
    owner, _, _, _ = dashboard_clients
    user_id = _signup(owner, "empty-dashboard@example.org")
    response = owner.get(f"/users/{user_id}/research/experiments/latest/metrics")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
