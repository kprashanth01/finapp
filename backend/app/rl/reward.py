"""Versioned proxy score and its inspectable, state-based decisions."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal

from app.advisory.state import PlanningState
from app.rl.selection import AGENT_IDS

REWARD_VERSION = "selection-proxy-v1"
RESERVE_TARGET_MONTHS = Decimal("3")
HIGH_DEBT_PAYMENT_PERCENT = Decimal("20")


@dataclass(frozen=True)
class RewardCheck:
    agent_id: str
    label: str
    metric: str
    value: str | None
    unit: str
    operator: str
    threshold: str
    input_status: Literal["available", "unavailable", "not_applicable"]
    critical: bool
    selected: bool
    note: str


@dataclass(frozen=True)
class RewardAudit:
    version: str
    components: dict[str, float]
    relevant_agents: tuple[str, ...]
    critical_agents: tuple[str, ...]
    missed_critical_agents: tuple[str, ...]
    unneeded_agents: tuple[str, ...]
    checks: tuple[RewardCheck, ...]

    @property
    def total(self) -> float:
        return sum(self.components.values())

    def to_dict(self) -> dict:
        return asdict(self)


def _targets(state: PlanningState) -> tuple[set[str], set[str]]:
    """Keep the v1 criteria separate from the rule policy's action choice."""
    relevant = {"budget", "emergency", "risk", "investment"}
    has_debt = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
    if has_debt:
        relevant.add("debt")
    if state.goals:
        relevant.add("goal")
    critical = set()
    if (state.monthly_expenses > 0 and state.emergency_fund_months is not None
            and state.emergency_fund_months < RESERVE_TARGET_MONTHS):
        critical.add("emergency")
    if has_debt and (state.debt_to_income_percent is None
                     or state.debt_to_income_percent >= HIGH_DEBT_PAYMENT_PERCENT):
        critical.add("debt")
    if any(goal.target_amount > goal.saved_amount for goal in state.goals):
        critical.add("goal")
    return relevant, critical


def _components(selected: set[str], relevant: set[str], critical: set[str]) -> dict[str, float]:
    return {
        "relevant_coverage": float(len(selected & relevant)),
        "critical_coverage": float(2 * len(selected & critical)),
        "missed_critical_penalty": float(-3 * len(critical - selected)),
        "unneeded_agent_penalty": float(-0.75 * len(selected - relevant)),
        "agent_call_penalty": float(-0.15 * len(selected)),
    }


def reward_components(state: PlanningState, selected_agents: tuple[str, ...]) -> dict[str, float]:
    selected = set(selected_agents)
    relevant, critical = _targets(state)
    return _components(selected, relevant, critical)


def audit_reward(state: PlanningState, selected_agents: tuple[str, ...]) -> RewardAudit:
    """Explain the existing v1 score; this does not assess financial outcomes."""
    selected = set(selected_agents)
    relevant, critical = _targets(state)
    coverage = state.emergency_fund_months
    dti = state.debt_to_income_percent
    has_debt = "debt" in relevant
    unfinished = sum(goal.target_amount > goal.saved_amount for goal in state.goals)
    checks = (
        RewardCheck(
            agent_id="emergency", label="Emergency reserve coverage",
            metric="emergency_fund_months", value=str(coverage) if coverage is not None else None,
            unit="months", operator="<", threshold=str(RESERVE_TARGET_MONTHS),
            input_status=("not_applicable" if state.monthly_expenses <= 0 else
                          "unavailable" if coverage is None else "available"),
            critical="emergency" in critical, selected="emergency" in selected,
            note=("No positive monthly expenses, so reserve coverage cannot be calculated."
                  if state.monthly_expenses <= 0 else
                  "Reserve coverage is unavailable."
                  if coverage is None else
                  "Below the illustrative three-month reserve target."
                  if "emergency" in critical else
                  "At or above the illustrative three-month reserve target."),
        ),
        RewardCheck(
            agent_id="debt", label="Debt payment ratio", metric="debt_to_income_percent",
            value=str(dti) if has_debt and dti is not None else None,
            unit="%", operator=">=", threshold=str(HIGH_DEBT_PAYMENT_PERCENT),
            input_status=("not_applicable" if not has_debt else
                          "unavailable" if dti is None else "available"),
            critical="debt" in critical, selected="debt" in selected,
            note=("No saved debt balance or payment; the Debt agent is not relevant to this proxy."
                  if not has_debt else
                  "Debt exists, but the payment ratio is unavailable; this proxy treats the Debt check as critical."
                  if dti is None else
                  "At or above the illustrative 20% debt-payment threshold."
                  if "debt" in critical else
                  "Below the illustrative 20% debt-payment threshold."),
        ),
        RewardCheck(
            agent_id="goal", label="Unfinished goals", metric="unfinished_goal_count",
            value=str(unfinished) if state.goals else None,
            unit="goals", operator=">", threshold="0",
            input_status="available" if state.goals else "not_applicable",
            critical="goal" in critical, selected="goal" in selected,
            note=("No active goals are saved." if not state.goals else
                  "At least one active goal has money still to save."
                  if unfinished else "All active goals are fully saved."),
        ),
    )
    return RewardAudit(
        version=REWARD_VERSION, components=_components(selected, relevant, critical),
        relevant_agents=tuple(agent for agent in AGENT_IDS if agent in relevant),
        critical_agents=tuple(agent for agent in AGENT_IDS if agent in critical),
        missed_critical_agents=tuple(agent for agent in AGENT_IDS if agent in critical - selected),
        unneeded_agents=tuple(agent for agent in AGENT_IDS if agent in selected - relevant),
        checks=checks,
    )
