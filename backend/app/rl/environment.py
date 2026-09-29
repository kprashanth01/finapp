"""One advisory selection is one episode; advice cannot change balances."""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.advisory.registry import AgentRegistry
from app.advisory.state import PlanningState
from app.rl.observation import FEATURE_NAMES, encode_observation
from app.rl.reward import reward_components
from app.rl.selection import ACTION_COUNT, agents_for


class AgentSelectionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, state: PlanningState):
        super().__init__()
        self.state = state
        self.action_space = spaces.Discrete(ACTION_COUNT)
        self.observation_space = spaces.Box(low=0, high=2, shape=(len(FEATURE_NAMES),), dtype=np.float32)
        self._done = False

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._done = False
        return encode_observation(self.state), {}

    def step(self, action):
        if self._done:
            raise RuntimeError("Reset the environment before another selection.")
        if not self.action_space.contains(action):
            raise ValueError("Action is outside the discrete agent-selection space.")
        selected = agents_for(int(action))
        registry = AgentRegistry.default()
        results = [registry.get(agent_id).analyze(self.state) for agent_id in selected]
        components = reward_components(self.state, selected)
        self._done = True
        return encode_observation(self.state), sum(components.values()), True, False, {
            "selected_agents": list(selected),
            "reward_components": components,
            "agent_results": [result.model_dump(mode="json") for result in results],
        }
