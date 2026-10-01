"""Read measured research metrics from the latest imported experiment."""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Experiment, ExperimentMetric, ExperimentRun

METHOD_ORDER = {"random": 0, "rule_based": 1, "rl": 2}


def latest_measurements(session: Session, *, method: str | None = None,
                        scenario: str | None = None, metric: str | None = None,
                        scope: Literal["aggregate", "seed"] = "aggregate") -> dict:
    experiment = session.scalar(select(Experiment).order_by(Experiment.id.desc()).limit(1))
    if experiment is None:
        return {"status": "unavailable", "reason": "No research experiment has been imported yet."}

    methods = sorted(set(session.scalars(select(ExperimentRun.method).where(
        ExperimentRun.experiment_id == experiment.id,
    ))), key=lambda name: (METHOD_ORDER.get(name, 3), name))
    scenarios = sorted(set(session.scalars(select(ExperimentRun.scenario).where(
        ExperimentRun.experiment_id == experiment.id,
    ))), key=lambda name: (name != "overall", name))
    measured = set(session.scalars(select(ExperimentMetric.name).join(ExperimentRun).where(
        ExperimentRun.experiment_id == experiment.id,
    )))
    limitations = experiment.details.get("limitations", {})
    unmeasured = {name for name, value in limitations.items() if value == "not measured"}
    metrics = sorted(measured | unmeasured)

    for name, choice, options in (("method", method, methods), ("scenario", scenario, scenarios),
                                   ("metric", metric, metrics)):
        if choice is not None and choice not in options:
            raise HTTPException(status_code=422, detail=f"Unknown {name} for this experiment.")

    statement = select(ExperimentMetric, ExperimentRun).join(ExperimentRun).where(
        ExperimentRun.experiment_id == experiment.id, ExperimentRun.scope == scope,
    )
    if method is not None:
        statement = statement.where(ExperimentRun.method == method)
    if scenario is not None:
        statement = statement.where(ExperimentRun.scenario == scenario)
    if metric is not None:
        statement = statement.where(ExperimentMetric.name == metric)
    statement = statement.order_by(ExperimentRun.method, ExperimentRun.scenario,
                                   ExperimentRun.seed, ExperimentMetric.name)
    rows = [{
        "run_id": run.id, "method": run.method, "scenario": run.scenario,
        "scope": run.scope, "seed": run.seed, "case_count": run.case_count,
        "sample_count": run.sample_count, "recorded_at": run.recorded_at.isoformat(),
        "metric": measured_value.name, "value": float(measured_value.value),
    } for measured_value, run in session.execute(statement)]
    rows.sort(key=lambda row: (METHOD_ORDER.get(row["method"], 3), row["method"],
                               row["scenario"] != "overall", row["scenario"],
                               row["seed"] if row["seed"] is not None else -1, row["metric"]))
    reason = (f"{metric.replace('_', ' ').capitalize()} was not measured. {limitations.get('reason', '')}"
              if metric in unmeasured else None)
    return {
        "status": "available",
        "experiment": {
            "id": experiment.id, "evaluation_version": experiment.evaluation_version,
            "scenario_version": experiment.scenario_version,
            "model_version": experiment.model_version,
            "cohort_sha256": experiment.cohort_sha256,
            "recorded_at": experiment.recorded_at.isoformat(),
            "case_count": experiment.details.get("cohort_case_count"),
            "source": experiment.details.get("source"),
            "metric_definitions": experiment.details.get("metric_definitions", {}),
            "limitations": limitations,
        },
        "filters": {
            "methods": methods, "scenarios": scenarios,
            "metrics": [{"name": name, "available": name in measured} for name in metrics],
        },
        "scope": scope, "rows": rows, "unmeasured_reason": reason,
    }
