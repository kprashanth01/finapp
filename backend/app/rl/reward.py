"""Transparent proxy score for agent selection, never a financial outcome."""

from app.advisory.state import PlanningState
from app.rl.selection import AGENT_IDS

REWARD_VERSION = "selection-proxy-v1"


def reward_components(state: PlanningState, selected_agents: tuple[str, ...]) -> dict[str, float]:
    selected = set(selected_agents)
    relevant = {"budget", "emergency", "risk", "investment"}
    if state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0:
        relevant.add("debt")
    if state.goals:
        relevant.add("goal")
    critical = set()
    if state.monthly_expenses > 0 and state.emergency_fund_months is not None and state.emergency_fund_months < 3:
        critical.add("emergency")
    if "debt" in relevant and (state.debt_to_income_percent is None or state.debt_to_income_percent >= 20):
        critical.add("debt")
    if any(goal.target_amount > goal.saved_amount for goal in state.goals):
        critical.add("goal")
    return {
        "relevant_coverage": float(len(selected & relevant)),
        "critical_coverage": float(2 * len(selected & critical)),
        "missed_critical_penalty": float(-3 * len(critical - selected)),
        "unneeded_agent_penalty": float(-0.75 * len(selected - relevant)),
        "agent_call_penalty": float(-0.15 * len(selected)),
    }
