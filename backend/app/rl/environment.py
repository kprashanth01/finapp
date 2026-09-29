"""One advisory selection is one episode; advice cannot change balances."""

from collections.abc import Sequence

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.advisory.registry import AgentRegistry
from app.advisory.state import PlanningState
from app.rl.observation import FEATURE_NAMES, encode_observation
from app.rl.reward import reward_components
from app.rl.selection import ActionCatalog, assess_plan_readiness


class AgentSelectionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, state: PlanningState | Sequence[PlanningState],
                 registry: AgentRegistry | None = None, catalog: ActionCatalog | None = None):
        super().__init__()
        self._states = (state,) if isinstance(state, PlanningState) else tuple(state)
        if not self._states or any(not isinstance(item, PlanningState) for item in self._states):
            raise ValueError("Supply at least one planning state.")
        self.registry = registry or AgentRegistry.default()
        self.catalog = catalog or ActionCatalog.from_agents(self.registry.agent_ids)
        if not set(self.catalog.agent_ids).issubset(self.registry.agent_ids):
            raise ValueError("The action catalogue names an unregistered agent.")
        self.state = self._states[0]
        self.action_space = spaces.Discrete(self.catalog.action_count)
        self.observation_space = spaces.Box(low=0, high=2, shape=(len(FEATURE_NAMES),), dtype=np.float32)
        self._done = False

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._done = False
        if len(self._states) > 1:
            self.state = self._states[int(self.np_random.integers(len(self._states)))]
        return encode_observation(self.state), {}

    def step(self, action):
        if self._done:
            raise RuntimeError("Reset the environment before another selection.")
        if not self.action_space.contains(action):
            raise ValueError("Action is outside the discrete agent-selection space.")
        selected = self.catalog.agents_for(int(action))
        results = [self.registry.get(agent_id).analyze(self.state) for agent_id in selected]
        components = reward_components(self.state, selected)
        self._done = True
        return encode_observation(self.state), sum(components.values()), True, False, {
            "selected_agents": list(selected),
            "action_version": self.catalog.version,
            "plan_readiness": assess_plan_readiness(self.state, selected),
            "reward_components": components,
            "agent_results": [result.model_dump(mode="json") for result in results],
        }
