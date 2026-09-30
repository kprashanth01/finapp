"""Gymnasium episodes over exogenous synthetic months and advisory selections."""

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
import json
from collections.abc import Sequence

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from app.advisory.dynamic import build_dynamic_planning_state
from app.advisory.recommendations import priority_actions
from app.advisory.registry import AgentRegistry
from app.advisory.state import GoalSnapshot
from app.rl.dynamic_reward import DYNAMIC_REWARD_VERSION, audit_dynamic_reward
from app.rl.dynamic_state import (
    DYNAMIC_FEATURE_NAMES, DYNAMIC_OBSERVATION_VERSION,
    DynamicFinancialState, encode_dynamic_observation,
)
from app.rl.population import SyntheticProfile
from app.rl.selection import AGENT_IDS, ActionCatalog


DYNAMIC_ENVIRONMENT_VERSION = "dynamic-agent-selection-v1"


@dataclass(frozen=True)
class DynamicEpisode:
    """One user's ordered observed months; goals are fixed experimental inputs."""

    profile: SyntheticProfile
    months: tuple[DynamicFinancialState, ...]
    as_of_date: date
    goals: tuple[GoalSnapshot, ...] = ()

    def __post_init__(self):
        months = tuple(self.months)
        object.__setattr__(self, "months", months)
        object.__setattr__(self, "goals", tuple(self.goals))
        if not months or any(not isinstance(month, DynamicFinancialState) for month in months):
            raise ValueError("An episode needs at least one synthetic monthly state.")
        for index, month in enumerate(months):
            if (month.synthetic_id != self.profile.synthetic_id
                    or month.persona != self.profile.persona
                    or month.dataset_split != self.profile.dataset_split
                    or month.base_monthly_income != self.profile.base_monthly_income):
                raise ValueError("Episode month identity or split does not match its profile.")
            if month.month_index < 1:
                raise ValueError("Episode month indices must be positive.")
            if index and month.month_index != months[index - 1].month_index + 1:
                raise ValueError("Episode months must be consecutive and ordered.")


class DynamicAgentSelectionEnv(gym.Env):
    """Run one agent-subset action per month, then reveal the next generated month.

    The next financial state is precomputed and independent of the action. This
    environment measures selection adaptation, not advice uptake or improvement.
    """

    metadata = {"render_modes": []}

    def __init__(self, episodes: DynamicEpisode | Sequence[DynamicEpisode],
                 registry: AgentRegistry | None = None, catalog: ActionCatalog | None = None):
        super().__init__()
        self.episodes = ((episodes,) if isinstance(episodes, DynamicEpisode)
                         else tuple(episodes))
        if not self.episodes or any(not isinstance(item, DynamicEpisode) for item in self.episodes):
            raise ValueError("Supply at least one dynamic episode.")
        if len({episode.profile.dataset_split for episode in self.episodes}) != 1:
            raise ValueError("Do not mix train and test users in one environment split.")
        self.registry = registry or AgentRegistry.default()
        self.catalog = catalog or ActionCatalog.from_agents(self.registry.agent_ids)
        if (not set(self.catalog.agent_ids).issubset(self.registry.agent_ids)
                or not set(self.catalog.agent_ids).issubset(AGENT_IDS)):
            raise ValueError("The action catalogue must use registered research agents.")
        self.action_space = spaces.Discrete(self.catalog.action_count)
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(len(DYNAMIC_FEATURE_NAMES),), dtype=np.float32,
        )
        self._episode_index: int | None = None
        self._position = 0
        self._done = True

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if options and set(options) != {"episode_index"}:
            raise ValueError("Only episode_index may be supplied in reset options.")
        if not options:
            self._episode_index = int(self.np_random.integers(len(self.episodes)))
        else:
            index = options["episode_index"]
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.episodes):
                raise ValueError("episode_index is outside this environment.")
            self._episode_index = index
        self._position = 0
        self._done = False
        episode = self.episodes[self._episode_index]
        month = episode.months[0]
        return encode_dynamic_observation(month), {
            "episode_index": self._episode_index,
            "synthetic_id": episode.profile.synthetic_id,
            "dataset_split": episode.profile.dataset_split,
            "month_index": month.month_index,
            "observation_version": DYNAMIC_OBSERVATION_VERSION,
        }

    def step(self, action):
        if self._done or self._episode_index is None:
            raise RuntimeError("Reset the environment before another selection.")
        if isinstance(action, bool) or not self.action_space.contains(action):
            raise ValueError("Action is outside the discrete agent-selection space.")
        episode = self.episodes[self._episode_index]
        month = episode.months[self._position]
        state = build_dynamic_planning_state(
            episode.profile, month,
            as_of_date=episode.as_of_date + timedelta(days=30 * self._position),
            goals=episode.goals,
        )
        selected = self.catalog.agents_for(int(action))
        results = [self.registry.get(agent_id).analyze(state) for agent_id in selected]
        audit = audit_dynamic_reward(state, selected)
        suggestions = priority_actions(results)
        self._position += 1
        terminated = self._position == len(episode.months)
        self._done = terminated
        next_month = None if terminated else episode.months[self._position]
        next_observation = encode_dynamic_observation(next_month or month)
        return next_observation, float(audit.total), terminated, False, {
            "episode_index": self._episode_index,
            "synthetic_id": episode.profile.synthetic_id,
            "dataset_split": episode.profile.dataset_split,
            "month_index": month.month_index,
            "next_month_index": next_month.month_index if next_month else None,
            "transition_source": "precomputed_exogenous_trajectory",
            "action": int(action), "action_version": self.catalog.version,
            "observation_version": DYNAMIC_OBSERVATION_VERSION,
            "reward_version": DYNAMIC_REWARD_VERSION,
            "selected_agents": list(selected),
            "agent_results": [result.model_dump(mode="json") for result in results],
            "priority_actions": [item.model_dump(mode="json") for item in suggestions],
            "reward_components": audit.components,
            "reward_audit": audit.to_dict(),
            "state_fingerprint": state.fingerprint(),
        }


def main() -> None:
    """Demonstrate a full synthetic monthly episode without saved account data."""
    from app.rl.dynamic_state import build_dynamic_financial_state
    from app.rl.population import DEFAULT_SEED as POPULATION_SEED, generate_population
    from app.rl.trajectories import DEFAULT_TRAJECTORY_SEED, ShockConfig, generate_trajectory

    parser = argparse.ArgumentParser(description="Run a dynamic Gymnasium advisory episode.")
    parser.add_argument("--synthetic-id", type=int, default=1)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--population-seed", type=int, default=POPULATION_SEED)
    parser.add_argument("--seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--selected", nargs="+", choices=AGENT_IDS,
                        default=["budget", "emergency", "risk"])
    parser.add_argument("--shocks", action="store_true")
    parser.add_argument("--shock-probability", type=float)
    parser.add_argument("--income-volatility", type=float)
    args = parser.parse_args()
    profile = next((item for item in generate_population(seed=args.population_seed)
                    if item.synthetic_id == args.synthetic_id), None)
    if profile is None:
        parser.error("synthetic-id is outside the generated population")
    use_shocks = args.shocks or args.shock_probability is not None or args.income_volatility is not None
    config = ShockConfig(
        probability=args.shock_probability if args.shock_probability is not None else
        0.10 if args.shocks else 0,
        income_volatility_override=args.income_volatility,
    ) if use_shocks else None
    raw_months = generate_trajectory(profile, months=args.months, seed=args.seed, shock_config=config)
    episode = DynamicEpisode(
        profile=profile,
        months=tuple(build_dynamic_financial_state(
            profile, month, income_volatility_override=args.income_volatility,
        ) for month in raw_months),
        as_of_date=date(2026, 10, 1),
    )
    environment = DynamicAgentSelectionEnv(episode)
    _, reset_info = environment.reset(seed=args.seed)
    action = environment.catalog.action_for(args.selected)
    steps = []
    for month in episode.months:
        _, score, terminated, _, info = environment.step(action)
        steps.append({
            "month_index": month.month_index,
            "monthly_income": str(month.monthly_income),
            "net_cash_flow": str(month.net_cash_flow),
            "action": int(action), "selected_agents": info["selected_agents"],
            "priority_actions": info["priority_actions"],
            "reward": score, "reward_components": info["reward_components"],
            "critical_agents": info["reward_audit"]["critical_agents"],
            "next_month_index": info["next_month_index"], "terminated": terminated,
        })
    print(json.dumps({
        "environment": DYNAMIC_ENVIRONMENT_VERSION,
        "population_seed": args.population_seed, "trajectory_seed": args.seed,
        "synthetic_id": profile.synthetic_id,
        "observation_version": DYNAMIC_OBSERVATION_VERSION,
        "action_version": environment.catalog.version,
        "reward_version": DYNAMIC_REWARD_VERSION,
        "transition_source": "precomputed_exogenous_trajectory",
        "reset": reset_info, "steps": steps,
    }, indent=2))


if __name__ == "__main__":
    main()
