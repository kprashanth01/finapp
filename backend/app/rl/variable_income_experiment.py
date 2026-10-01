"""Controlled, paired monthly policy experiments over editable synthetic scenarios."""

import argparse
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.advisory.state import GoalSnapshot
from app.rl.dynamic_environment import DynamicEpisode
from app.rl.dynamic_experiment import (METHODS, _write_atomic,
                                       load_committed_test_episodes,
                                       run_paired_experiment, write_experiment)
from app.rl.dynamic_metrics import summarize_metrics
from app.rl.dynamic_model_management import load_model
from app.rl.dynamic_state import build_dynamic_financial_state
from app.rl.population import CENT, SyntheticDebt, validate_profile
from app.rl.trajectories import EventType, ShockConfig, generate_trajectory


CONTROLLED_VERSION = "variable-income-experiment-v1"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "experiments" / "variable-income-scenarios.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / CONTROLLED_VERSION
ANNUAL_INTEREST = Decimal("0.08")


class ControlledScenario(BaseModel):
    """Financial ratios apply to every member of the same held-out test cohort."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    description: str = Field(min_length=1)
    income_volatility: float = Field(ge=0, le=1)
    shock_probability: float = Field(ge=0, le=1)
    shock_magnitude: float = Field(ge=0, le=1)
    debt_to_annual_income: float = Field(ge=0, le=3)
    emi_to_monthly_income: float = Field(ge=0, le=0.6)
    expenses_to_monthly_income: float = Field(ge=0, le=2)
    emergency_fund_months: float = Field(ge=0, le=12)
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    investment_horizon_years: int = Field(ge=0, le=80)
    goal_horizon_months: int | None = Field(default=None, ge=1, le=120)
    goal_amount: Decimal | None = Field(default=None, gt=0)
    forced_events: tuple[tuple[int, EventType], ...] = ()

    @model_validator(mode="after")
    def check_finances(self):
        if self.expenses_to_monthly_income < self.emi_to_monthly_income:
            raise ValueError("Total expenses must include the scheduled EMI.")
        if (self.debt_to_annual_income == 0) != (self.emi_to_monthly_income == 0):
            raise ValueError("Debt principal and EMI must either both be zero or both be positive.")
        if self.emi_to_monthly_income <= self.debt_to_annual_income * float(ANNUAL_INTEREST):
            if self.debt_to_annual_income:
                raise ValueError("The scheduled EMI must exceed monthly interest.")
        if (self.goal_horizon_months is None) != (self.goal_amount is None):
            raise ValueError("Goal amount and horizon must be supplied together.")
        if self.goal_amount is not None and self.goal_amount != self.goal_amount.quantize(CENT):
            raise ValueError("Goal amount must use cents.")
        ShockConfig(probability=self.shock_probability, magnitude=self.shock_magnitude,
                    income_volatility_override=self.income_volatility,
                    forced_events=self.forced_events)
        return self


def load_scenarios(path: Path = DEFAULT_CONFIG) -> tuple[ControlledScenario, ...]:
    """Read a complete, ordered scenario matrix from editable JSON."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Scenario configuration must be a nonempty JSON array.")
    scenarios = tuple(ControlledScenario.model_validate(item) for item in payload)
    if len({item.name for item in scenarios}) != len(scenarios):
        raise ValueError("Scenario names must be unique.")
    return scenarios


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def build_scenario_episodes(base_episodes: tuple[DynamicEpisode, ...],
                            scenario: ControlledScenario, *, months: int,
                            trajectory_seed: int) -> tuple[DynamicEpisode, ...]:
    """Hold identities and random draws fixed while changing specified financial inputs."""
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 120:
        raise ValueError("months must be between 1 and 120")
    if any(month > months for month, _ in scenario.forced_events):
        raise ValueError("Forced event falls outside the requested horizon.")
    config = ShockConfig(probability=scenario.shock_probability,
                         magnitude=scenario.shock_magnitude,
                         income_volatility_override=scenario.income_volatility,
                         forced_events=scenario.forced_events)
    episodes = []
    for base in base_episodes:
        if base.profile.dataset_split != "test":
            raise ValueError("Controlled scenarios require held-out test users only.")
        original = base.profile
        income = original.base_monthly_income
        emi = _money(income * Decimal(str(scenario.emi_to_monthly_income)))
        principal = _money(income * 12 * Decimal(str(scenario.debt_to_annual_income)))
        total_expenses = _money(income * Decimal(str(scenario.expenses_to_monthly_income)))
        non_debt = total_expenses - emi
        fixed = _money(non_debt * Decimal("0.65"))
        reserve = _money(total_expenses * Decimal(str(scenario.emergency_fund_months)))
        debts = ((SyntheticDebt("personal", principal, ANNUAL_INTEREST, emi, 120),)
                 if principal else ())
        profile = replace(
            original, monthly_expenses=total_expenses, monthly_debt_payments=emi,
            existing_debt=principal, monthly_savings_contribution=Decimal("0.00"),
            emergency_fund=reserve, savings=reserve,
            risk_tolerance=scenario.risk_tolerance,
            investment_horizon_years=scenario.investment_horizon_years,
            income_volatility=Decimal(str(scenario.income_volatility)),
            fixed_monthly_expenses=fixed, variable_monthly_expenses=non_debt - fixed,
            debts=debts,
        )
        validate_profile(profile)
        generated = generate_trajectory(profile, months=months, seed=trajectory_seed,
                                        shock_config=config)
        goals = (() if scenario.goal_horizon_months is None else (
            GoalSnapshot(id=1, name="Controlled research goal",
                         target_amount=scenario.goal_amount,
                         saved_amount=Decimal("0.00"),
                         target_date=base.as_of_date + timedelta(days=30 * scenario.goal_horizon_months),
                         priority="medium"),
        ))
        episodes.append(DynamicEpisode(
            profile=profile,
            months=tuple(build_dynamic_financial_state(profile, month) for month in generated),
            as_of_date=base.as_of_date, goals=goals,
        ))
    return tuple(episodes)


def _behavior_change(reference: dict, current: dict) -> dict:
    base_rows = {(row["synthetic_id"], row["month_index"], row["method"]): row
                 for row in reference["rows"]}
    current_rows = {(row["synthetic_id"], row["month_index"], row["method"]): row
                    for row in current["rows"]}
    if set(base_rows) != set(current_rows):
        raise ValueError("Scenarios must compare identical test users, months, and methods.")
    decisions = len(base_rows) // len(METHODS)
    reference_rows = [base_rows[key] for key in base_rows if key[2] == METHODS[0]]
    changed_states = sum(
        row["state_fingerprint"] != current_rows[(row["synthetic_id"], row["month_index"], METHODS[0])]["state_fingerprint"]
        for row in reference_rows
    )
    changed_observations = sum(
        row["observation"] != current_rows[(row["synthetic_id"], row["month_index"], METHODS[0])]["observation"]
        for row in reference_rows
    )
    result = {"changed_states": changed_states,
              "changed_observations": changed_observations,
              "paired_decisions": decisions,
              "methods": {}}
    for method in METHODS:
        keys = [key for key in base_rows if key[2] == method]
        changed = sum(base_rows[key]["action"] != current_rows[key]["action"] for key in keys)
        result["methods"][method] = {"changed_actions": changed,
                                      "change_rate": round(changed / decisions, 6)}
    return result


def _scenario_diagnostics(rows: list[dict]) -> dict:
    distributions = {}
    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        counts = Counter(row["action"] for row in method_rows)
        agents = {row["action"]: row["selected_agents"] for row in method_rows}
        distributions[method] = [
            {"action": action, "selected_agents": agents[action], "count": count}
            for action, count in sorted(counts.items())
        ]
    events = Counter(row["financial_state"]["simulated_event_type"]
                     for row in rows if row["method"] == METHODS[0] and
                     row["financial_state"]["simulated_event_type"] is not None)
    return {"action_distribution": distributions,
            "observed_event_months": dict(sorted(events.items()))}


def run_controlled_experiment(base_episodes: tuple[DynamicEpisode, ...],
                              scenarios: tuple[ControlledScenario, ...], *, model,
                              months: int = 12, trajectory_seed: int = 20261001,
                              random_seed: int = 313,
                              model_metadata: dict | None = None) -> dict:
    """Run all policies on each scenario, pairing methods and source users."""
    base_episodes = tuple(base_episodes)
    scenarios = tuple(scenarios)
    if not base_episodes or not scenarios or len({s.name for s in scenarios}) != len(scenarios):
        raise ValueError("Supply test users and distinct scenarios.")
    if isinstance(trajectory_seed, bool) or not isinstance(trajectory_seed, int) or trajectory_seed < 0:
        raise ValueError("trajectory_seed must be a nonnegative integer.")
    raw_reports = {}
    summaries = []
    reference = None
    for scenario in scenarios:
        episodes = build_scenario_episodes(base_episodes, scenario, months=months,
                                           trajectory_seed=trajectory_seed)
        report = run_paired_experiment(episodes, model=model, random_seed=random_seed,
                                       model_metadata=model_metadata)
        metrics = summarize_metrics(report["rows"], report["manifest"])
        if reference is None:
            reference = report
        raw_reports[scenario.name] = report
        summaries.append({
            "scenario": scenario.model_dump(mode="json"),
            "trace": report["manifest"],
            "metrics": metrics["methods"],
            "behavior_vs_first_scenario": _behavior_change(reference, report),
            **_scenario_diagnostics(report["rows"]),
        })
    ids = ",".join(str(item.profile.synthetic_id) for item in base_episodes)
    summary = {
        "experiment_version": CONTROLLED_VERSION,
        "dataset_split": "test", "user_count": len(base_episodes),
        "months_per_user": months, "trajectory_seed": trajectory_seed,
        "random_seed": random_seed,
        "source_user_id_sha256": sha256(ids.encode("ascii")).hexdigest(),
        "source_model": (raw_reports[scenarios[0].name]["manifest"]["model"]),
        "reference_scenario": scenarios[0].name,
        "scenarios": summaries,
        "interpretation": (
            "Action-change rates compare the same held-out users and months with the first scenario. "
            "Random reuses its seed as a negative control. These are synthetic selection-proxy "
            "results, not financial outcomes or causal estimates."
        ),
        "limitations": [
            "Precomputed financial trajectories do not respond to selected actions.",
            "Scenarios change several inputs at once; action changes cannot be attributed to one input.",
            "The saved 19-feature DQN observation omits goal amount and goal deadline; its goal response cannot be evaluated from these inputs.",
            "Financial amounts are illustrative and are not calibrated to a real population.",
        ],
    }
    return {"summary": summary, "raw_reports": raw_reports}


def write_controlled_experiment(report: dict, output_dir: Path) -> Path:
    """Write per-scenario raw traces and a summary after all runs succeed."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in report["summary"]["scenarios"]:
        name = item["scenario"]["name"]
        write_experiment(report["raw_reports"][name], output_dir / f"{name}.jsonl")
    summary_path = output_dir / "summary.json"
    _write_atomic(summary_path, json.dumps(report["summary"], indent=2,
                                           allow_nan=False) + "\n")
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare policies under editable controlled financial scenarios.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--users", type=int, default=64)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--trajectory-seed", type=int, default=20261001)
    parser.add_argument("--random-seed", type=int, default=313)
    args = parser.parse_args()
    if not 1 <= args.users <= 64:
        parser.error("--users must be between 1 and 64 held-out users")
    scenarios = load_scenarios(args.config)
    base_episodes, metadata = load_committed_test_episodes()
    report = run_controlled_experiment(base_episodes[:args.users], scenarios,
                                       model=load_model(), months=args.months,
                                       trajectory_seed=args.trajectory_seed,
                                       random_seed=args.random_seed,
                                       model_metadata=metadata)
    summary_path = write_controlled_experiment(report, args.output_dir)
    print(json.dumps({"summary_path": str(summary_path.resolve()),
                      "user_count": report["summary"]["user_count"],
                      "scenarios": [
                          {"name": item["scenario"]["name"],
                           "behavior_vs_first_scenario": item["behavior_vs_first_scenario"],
                           "mean_reward": {method: values["average_reward"]
                                           for method, values in item["metrics"].items()}}
                          for item in report["summary"]["scenarios"]]}, indent=2))


if __name__ == "__main__":
    main()
