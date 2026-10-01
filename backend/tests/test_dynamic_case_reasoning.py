"""The optional narrator may explain a case but cannot change its decisions or numbers."""

import json

import pytest

from app.rl.dynamic_case_reasoning import explain_case
from app.rl.dynamic_cases import inspect_case
from app.rl.dynamic_experiment import run_paired_experiment
from app.rl.dynamic_scenarios import build_dynamic_episode_splits


class BudgetOnlyPolicy:
    def predict(self, observation, deterministic):
        return 0, None


@pytest.fixture(scope="module")
def case():
    episodes = build_dynamic_episode_splits(
        training_users=2, validation_users=2, test_users=2, months=1,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.2,
    ).test
    report = run_paired_experiment(episodes, model=BudgetOnlyPolicy(), random_seed=17)
    return inspect_case(report["rows"], report["manifest"], episodes,
                        synthetic_id=episodes[0].profile.synthetic_id, month_index=1)


def test_no_request_or_missing_key_uses_unchanged_deterministic_case(case, monkeypatch):
    from app.rl import dynamic_case_reasoning as reasoning

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "_provider_request",
                        lambda *_args: pytest.fail("Provider was called without an explicit request"))
    original = json.dumps(case, sort_keys=True)
    skipped = explain_case(case, "trained_rl")
    assert skipped["source"] == "deterministic"
    assert skipped["fallback_reason"] == "not_requested"
    assert skipped["narrative"].startswith(" ".join(case["methods"]["trained_rl"]["explanation"]))
    first_finding = case["methods"]["trained_rl"]["agent_outputs"][0]["findings"][0]
    assert first_finding["reason"] in skipped["narrative"]
    assert case["methods"]["trained_rl"]["recommendation"]["summary"]["text"] in skipped["narrative"]
    assert "feature causes are not available" in skipped["narrative"]
    assert "conflicts were not assessed" in skipped["narrative"]
    assert skipped["deterministic"]["reward_components"] == case["methods"]["trained_rl"]["reward_components"]
    assert skipped["deterministic"]["recommendation"] == case["methods"]["trained_rl"]["recommendation"]
    assert json.dumps(case, sort_keys=True) == original

    monkeypatch.delenv("OPENAI_API_KEY")
    missing = explain_case(case, "trained_rl", use_llm=True)
    assert missing["source"] == "deterministic"
    assert missing["fallback_reason"] == "not_configured"


def test_provider_receives_only_recorded_synthetic_evidence_and_cannot_change_facts(case, monkeypatch):
    from app.rl import dynamic_case_reasoning as reasoning

    captured = {}
    narrative = "The selected specialists found liquidity pressure. The coordinated plan remains partial because required checks did not run."

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, *_args):
            return json.dumps({"status": "completed", "output": [{"type": "message",
                "content": [{"type": "output_text", "text": narrative}]}]}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "urlopen", fake_urlopen)
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "llm"
    assert answer["narrative"] == narrative
    assert answer["fallback_reason"] is None
    assert answer["deterministic"]["action"] == case["methods"]["trained_rl"]["action"]
    assert answer["deterministic"]["agent_outputs"] == case["methods"]["trained_rl"]["agent_outputs"]
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["body"]["store"] is False
    facts = json.loads(captured["body"]["input"][1]["content"])
    assert facts["selected_agents"] == case["methods"]["trained_rl"]["selected_agents"]
    assert facts["agent_findings"]
    assert facts["conflicts_status"] == "not_assessed"
    assert "synthetic_id" not in facts and "user_state" not in facts and "email" not in str(facts)


@pytest.mark.parametrize("unsafe", [
    "The investment return will improve by 25%.",
    "The DQN selected Budget because income fell.",
    "Income fell and caused the DQN to choose Budget.",
    "There are no conflicts in this plan.",
    "A complete coordinated plan was produced from these findings.",
])
def test_unsupported_provider_claims_fall_back(case, monkeypatch, unsafe):
    from app.rl import dynamic_case_reasoning as reasoning

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "_provider_request", lambda *_args: unsafe)
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "deterministic"
    assert answer["fallback_reason"] == "invalid_output"
    assert unsafe not in answer["narrative"]


def test_provider_failure_falls_back_and_unknown_method_is_rejected(case, monkeypatch):
    from app.rl import dynamic_case_reasoning as reasoning

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "_provider_request",
                        lambda *_args: (_ for _ in ()).throw(TimeoutError()))
    answer = explain_case(case, "random", use_llm=True)
    assert answer["source"] == "deterministic"
    assert answer["fallback_reason"] == "provider_error"
    with pytest.raises(ValueError, match="method"):
        explain_case(case, "not_a_policy", use_llm=True)
