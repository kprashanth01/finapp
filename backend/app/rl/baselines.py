"""Comparable, reproducible research selections on the same action catalogue."""

from typing import Protocol

import numpy as np

from app.advisory.state import PlanningState
from app.rl.selection import ActionCatalog, agents_for, rule_action


class BaselinePolicy(Protocol):
    def choose_action(self, state: PlanningState, catalog: ActionCatalog) -> int: ...


class RuleBaseline:
    def choose_action(self, state: PlanningState, catalog: ActionCatalog) -> int:
        return catalog.action_for(agents_for(rule_action(state)))


class RandomBaseline:
    def __init__(self, *, seed: int):
        self._rng = np.random.default_rng(seed)

    def choose_action(self, state: PlanningState, catalog: ActionCatalog) -> int:
        return int(self._rng.integers(catalog.action_count))
