"""Trained monthly actions must pass through registered agents before advice and reward."""

from datetime import date
import json

import pytest

pytest.importorskip("stable_baselines3")

from app.rl.dynamic_environment import DynamicEpisode
from app.rl.dynamic_integration import run_trained_dynamic_episode
from app.rl.dynamic_state import build_dynamic_financial_state
from app.advisory.registry import AgentRegistry
from app.rl.population import generate_population
from app.rl.selection import ActionCatalog
from app.rl.splits import assign_user_splits
from app.rl.trajectories import ShockConfig, generate_trajectory


@pytest.fixture(scope="module")
def test_episode():
    profile = next(item for item in assign_user_splits(generate_population(seed=91), seed=92)
                   if item.dataset_split == "test")
    months = tuple(build_dynamic_financial_state(profile, month) for month in
                   generate_trajectory(profile, months=3, seed=94,
                                       shock_config=ShockConfig(probability=0.2)))
    return DynamicEpisode(profile, months, date(2026, 10, 1))


def test_committed_dqn_runs_only_mapped_agents_and_writes_a_trace(test_episode, tmp_path):
    trace_path = tmp_path / "trained-agent-trace.jsonl"
    original = [month.model_dump(mode="json") for month in test_episode.months]
    report = run_trained_dynamic_episode(test_episode, trace_path=trace_path)
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert rows == report["steps"]
    assert report["policy"]["model_version"] == "dynamic-dqn-monthly-v1"
    assert report["episode"]["dataset_split"] == "test"
    assert len(rows) == 3
    catalog = ActionCatalog.from_agents(("budget", "debt", "emergency", "goal", "risk", "investment"))
    for index, row in enumerate(rows):
        assert row["month_index"] == index + 1
        assert len(row["observation"]) == 19
        assert row["financial_state"]["synthetic_id"] == test_episode.profile.synthetic_id
        assert row["selected_agents"] == list(catalog.agents_for(row["action"]))
        assert [item["agent_id"] for item in row["agent_results"]] == row["selected_agents"]
        assert all(item["agent_id"] in row["selected_agents"]
                   for item in row["recommendation"]["priority_actions"])
        assert row["reward"] == pytest.approx(sum(row["reward_components"].values()))
        assert row["transition_source"] == "precomputed_exogenous_trajectory"
        assert row["state_fingerprint"]
    assert [month.model_dump(mode="json") for month in test_episode.months] == original


def test_recommendation_is_gated_by_actual_selected_agent_results(test_episode, tmp_path, monkeypatch):
    class FixedModel:
        def __init__(self, action):
            self.action = action

        def predict(self, observation, deterministic):
            assert deterministic is True and observation.shape == (19,)
            return self.action, None

    real_registry = AgentRegistry.default()
    calls = []

    class RecordingRegistry:
        agent_ids = real_registry.agent_ids

        def get(self, agent_id):
            calls.append(agent_id)
            return real_registry.get(agent_id)

    monkeypatch.setattr(AgentRegistry, "default", classmethod(lambda cls: RecordingRegistry()))
    partial = run_trained_dynamic_episode(test_episode, model=FixedModel(0))
    assert all(row["selected_agents"] == ["budget"] for row in partial["steps"])
    assert calls == ["budget"] * 3
    assert all(row["recommendation"]["status"] == "partial" and
               row["recommendation"]["coordinated_plan"] is None for row in partial["steps"])
    calls.clear()
    complete = run_trained_dynamic_episode(test_episode, model=FixedModel(62))
    assert all(len(row["agent_results"]) == 6 for row in complete["steps"])
    assert calls == list(real_registry.agent_ids) * 3
    assert all(row["recommendation"]["status"] == "complete" and
               row["recommendation"]["coordinated_plan"] is not None for row in complete["steps"])
    assert complete["policy"]["source"] == "supplied_policy"

    with pytest.raises(ValueError, match="Action"):
        run_trained_dynamic_episode(test_episode, model=FixedModel(63),
                                    trace_path=tmp_path / "invalid.jsonl")
    assert not (tmp_path / "invalid.jsonl").exists()
    with pytest.raises(ValueError, match="discrete integer"):
        run_trained_dynamic_episode(test_episode, model=FixedModel(1.5))
