"""Import verified fixed-cohort evaluation evidence into research-only tables."""

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Experiment, ExperimentMetric, ExperimentRun
from app.rl.dqn_artifact import DEFAULT_ARTIFACT_DIR
from app.rl.evaluation import REPORT_FILENAME, read_evaluation_report


def _metrics(values: dict) -> list[ExperimentMetric]:
    stored = []
    for name, value in values.items():
        if value is None:
            continue  # Unmeasured is not zero.
        if not isinstance(name, str) or len(name) > 80 or isinstance(value, bool):
            raise ValueError("Evaluation contains an invalid metric.")
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Evaluation contains an invalid metric.") from exc
        if not number.is_finite() or number.adjusted() > 13:
            raise ValueError("Evaluation contains an invalid metric.")
        stored.append(ExperimentMetric(name=name, value=number))
    return stored


def _run(method: str, scenario: str, scope: str, seed: int | None,
         case_count: int, sample_count: int, metrics: dict) -> ExperimentRun:
    if (not isinstance(case_count, int) or isinstance(case_count, bool) or case_count <= 0 or
            not isinstance(sample_count, int) or sample_count < case_count or
            len(method) > 40 or len(scenario) > 80):
        raise ValueError("Evaluation contains an invalid run.")
    key = f"{method}:{scenario}:{scope}:{seed if seed is not None else 'all'}"
    return ExperimentRun(
        run_key=key, method=method, scenario=scenario, scope=scope,
        seed=seed, case_count=case_count, sample_count=sample_count,
        metrics=_metrics(metrics),
    )


def import_evaluation_report(session: Session,
                             path: Path = DEFAULT_ARTIFACT_DIR / REPORT_FILENAME) -> Experiment:
    """Verify and import once; rerunning the same report leaves existing rows intact."""
    result = read_evaluation_report(path)
    if result["status"] != "available":
        raise ValueError(result["reason"])
    report = result["report"]
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    existing = session.scalar(select(Experiment).where(Experiment.report_sha256 == digest))
    if existing is not None:
        return existing

    cohort = report["cohort"]
    experiment = Experiment(
        report_sha256=digest,
        evaluation_version=report["evaluation_version"],
        scenario_version=report["scenario_version"],
        model_version=report["model_sha256"],
        cohort_sha256=cohort["sha256"],
        details={
            "source": cohort["source"],
            "cohort_seed": cohort["seed"],
            "cohort_case_count": cohort["case_count"],
            "observation_version": report["observation_version"],
            "action_version": report["action_version"],
            "reward_version": report["reward_version"],
            "random_seeds": report["random_seeds"],
            "metric_definitions": report["metric_definitions"],
            "limitations": report["limitations"],
            "paired_rl_vs_rule": report["paired_rl_vs_rule"],
            "timestamp_meaning": "recorded_at is import time; source report has no measurement timestamp",
        },
    )
    for method, item in report["methods"].items():
        experiment.runs.append(_run(
            method, "overall", "aggregate", None, cohort["case_count"],
            item["evaluations"], item["metrics"],
        ))
        # A single rule/RL run equals its aggregate, so store only random seed detail.
        if method == "random":
            for run in item["runs"]:
                experiment.runs.append(_run(
                    method, "overall", "seed", run["seed"],
                    run["case_count"], run["case_count"], run["metrics"],
                ))
        for scenario, segment in item["segments"].items():
            experiment.runs.append(_run(
                method, scenario, "aggregate", None, segment["case_count"],
                segment["case_count"] * item["run_count"],
                {key: value for key, value in segment.items() if key != "case_count"},
            ))
    try:
        session.add(experiment)
        session.commit()
        return experiment
    except Exception:
        session.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the verified fixed-cohort research report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_ARTIFACT_DIR / REPORT_FILENAME)
    args = parser.parse_args()
    with Session(get_engine()) as session:
        experiment = import_evaluation_report(session, args.report)
        print(f"Experiment {experiment.id}: {len(experiment.runs)} runs; model {experiment.model_version}")


if __name__ == "__main__":
    main()
