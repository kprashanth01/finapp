"""The research database preserves measured evaluations without user data."""

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Experiment, ExperimentMetric, ExperimentRun
from app.rl.evaluation import read_evaluation_report
from app.rl.evaluation_store import import_evaluation_report


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_import_preserves_method_scenario_scope_and_measured_values(session):
    saved = read_evaluation_report()
    assert saved["status"] == "available"
    report = saved["report"]

    experiment = import_evaluation_report(session)
    assert experiment.id is not None
    assert experiment.model_version == report["model_sha256"]
    assert experiment.scenario_version == report["scenario_version"]
    assert experiment.cohort_sha256 == report["cohort"]["sha256"]
    assert session.scalar(select(func.count()).select_from(ExperimentRun)) == 20

    rl = session.scalar(select(ExperimentRun).where(
        ExperimentRun.experiment_id == experiment.id,
        ExperimentRun.method == "rl", ExperimentRun.scenario == "overall",
        ExperimentRun.scope == "aggregate",
    ))
    assert rl.case_count == 256
    assert rl.sample_count == 256
    value = session.scalar(select(ExperimentMetric.value).where(
        ExperimentMetric.run_id == rl.id, ExperimentMetric.name == "mean_reward",
    ))
    assert value == Decimal(str(report["methods"]["rl"]["metrics"]["mean_reward"]))

    random_segment = session.scalar(select(ExperimentRun).where(
        ExperimentRun.experiment_id == experiment.id,
        ExperimentRun.method == "random", ExperimentRun.scenario == "low_reserve",
    ))
    assert random_segment.case_count == 154
    assert random_segment.sample_count == 154 * 5
    assert session.scalar(select(func.count()).select_from(ExperimentMetric).where(
        ExperimentMetric.run_id == random_segment.id,
    )) == 2
    assert experiment.recorded_at is not None
    assert random_segment.recorded_at is not None


def test_import_is_idempotent_and_rejects_stale_report(session, tmp_path):
    first = import_evaluation_report(session)
    second = import_evaluation_report(session)
    assert second.id == first.id
    assert session.scalar(select(func.count()).select_from(Experiment)) == 1
    assert session.scalar(select(func.count()).select_from(ExperimentRun)) == 20

    report = read_evaluation_report()["report"]
    report["model_sha256"] = "stale"
    path = tmp_path / "stale.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or does not match"):
        import_evaluation_report(session, path)
    assert session.scalar(select(func.count()).select_from(Experiment)) == 1


def test_null_metric_is_not_stored_as_zero(session, tmp_path, monkeypatch):
    report = read_evaluation_report()["report"]
    report["methods"]["rl"]["metrics"]["goal_alignment_rate"] = None
    monkeypatch.setattr("app.rl.evaluation_store.read_evaluation_report", lambda _: {
        "status": "available", "report": report,
    })
    experiment = import_evaluation_report(session, tmp_path / "unused.json")
    rl = session.scalar(select(ExperimentRun).where(
        ExperimentRun.experiment_id == experiment.id,
        ExperimentRun.method == "rl", ExperimentRun.scenario == "overall",
    ))
    names = set(session.scalars(select(ExperimentMetric.name).where(ExperimentMetric.run_id == rl.id)))
    assert "goal_alignment_rate" not in names
