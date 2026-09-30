"""Versioned action catalogue for research-only agent selection."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from app.advisory.state import PlanningState

ACTION_VERSION = "agent-subset-v1"
AGENT_IDS = ("budget", "debt", "emergency", "goal", "risk", "investment")


@dataclass(frozen=True)
class ActionCatalog:
    """Stable integer actions for a configured ordered set of registered agents.

    The default catalogue retains the v1 bitmask mapping used by model.json.
    Custom configurations receive a content-derived version and never change v1.
    """

    agent_ids: tuple[str, ...]
    actions: tuple[tuple[str, ...], ...]
    version: str

    @classmethod
    def from_agents(cls, agent_ids: Iterable[str], *,
                    allowed_selections: Iterable[Iterable[str]] | None = None) -> "ActionCatalog":
        ordered = tuple(agent_ids)
        if not ordered or len(set(ordered)) != len(ordered) or any(not name for name in ordered):
            raise ValueError("Agent IDs must be unique, nonempty names.")
        if allowed_selections is None:
            masks = tuple(range(1, 1 << len(ordered)))
        else:
            configured = []
            for selection in allowed_selections:
                names = tuple(selection)
                if not names or len(set(names)) != len(names) or not set(names).issubset(ordered):
                    raise ValueError("Each allowed action needs distinct registered agents.")
                configured.append(sum(1 << index for index, name in enumerate(ordered) if name in names))
            if not configured or len(set(configured)) != len(configured):
                raise ValueError("Allowed actions must be nonempty and distinct.")
            masks = tuple(sorted(configured))
        actions = tuple(tuple(name for index, name in enumerate(ordered) if mask & (1 << index))
                        for mask in masks)
        if ordered == AGENT_IDS and masks == tuple(range(1, 1 << len(AGENT_IDS))):
            version = ACTION_VERSION
        else:
            canonical = json.dumps({"agents": ordered, "actions": actions}, separators=(",", ":"))
            version = f"agent-catalog-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
        return cls(agent_ids=ordered, actions=actions, version=version)

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def agents_for(self, action: int) -> tuple[str, ...]:
        if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < self.action_count:
            raise ValueError(f"Action must be an integer from 0 to {self.action_count - 1}.")
        return self.actions[action]

    def action_for(self, agent_ids: Iterable[str]) -> int:
        selected = tuple(agent_ids)
        if not selected or len(set(selected)) != len(selected) or not set(selected).issubset(self.agent_ids):
            raise ValueError("Select distinct registered agents.")
        canonical = tuple(name for name in self.agent_ids if name in selected)
        try:
            return self.actions.index(canonical)
        except ValueError as error:
            raise ValueError("This agent combination is not an allowed action.") from error

    def describe(self) -> dict:
        """Expose the exact mapping used by this catalogue, including custom ones."""
        return {
            "action_version": self.version,
            "action_count": self.action_count,
            "selection_semantics": "one_step_subset",
            "agents": list(self.agent_ids),
            "actions": [
                {"id": action, "agents": list(names)}
                for action, names in enumerate(self.actions)
            ],
        }


DEFAULT_CATALOG = ActionCatalog.from_agents(AGENT_IDS)
ACTION_COUNT = DEFAULT_CATALOG.action_count


def agents_for(action: int) -> tuple[str, ...]:
    return DEFAULT_CATALOG.agents_for(action)


def action_for(agent_ids: Iterable[str]) -> int:
    return DEFAULT_CATALOG.action_for(agent_ids)


def rule_action(state: PlanningState) -> int:
    """Match the existing coordinator's selected-agent set."""
    selected = {"budget", "emergency", "risk", "investment"}
    if state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0:
        selected.add("debt")
    if state.goals:
        selected.add("goal")
    return action_for(selected)


def assess_plan_readiness(state: PlanningState, selected_agents: Iterable[str]) -> dict:
    """Report fact coverage; this function does not generate a recommendation."""
    selected = set(selected_agents)
    required = agents_for(rule_action(state))
    missing = [name for name in required if name not in selected]
    return {
        "can_build_full_plan": not missing,
        "required_agents": list(required),
        "missing_agents": missing,
    }


if __name__ == "__main__":
    print(json.dumps(DEFAULT_CATALOG.describe(), indent=2))
