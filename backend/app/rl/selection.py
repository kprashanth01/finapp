"""One stable action mapping for comparing agent-selection policies."""

from collections.abc import Iterable

from app.advisory.state import PlanningState

ACTION_VERSION = "agent-subset-v1"
AGENT_IDS = ("budget", "debt", "emergency", "goal", "risk", "investment")
ACTION_COUNT = (1 << len(AGENT_IDS)) - 1  # Exclude the empty selection.


def agents_for(action: int) -> tuple[str, ...]:
    if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < ACTION_COUNT:
        raise ValueError(f"Action must be an integer from 0 to {ACTION_COUNT - 1}.")
    mask = action + 1
    return tuple(agent_id for position, agent_id in enumerate(AGENT_IDS) if mask & (1 << position))


def action_for(agent_ids: Iterable[str]) -> int:
    selected = set(agent_ids)
    if not selected or not selected.issubset(AGENT_IDS):
        raise ValueError("Select at least one known agent.")
    return sum(1 << position for position, agent_id in enumerate(AGENT_IDS) if agent_id in selected) - 1


def rule_action(state: PlanningState) -> int:
    """Match the existing coordinator's selected-agent set."""
    selected = {"budget", "emergency", "risk", "investment"}
    if state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0:
        selected.add("debt")
    if state.goals:
        selected.add("goal")
    return action_for(selected)
