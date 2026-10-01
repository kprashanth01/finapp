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


def valid_sections():
    return {
        "summary": "Selected specialists reported liquidity pressure in this synthetic case.",
        "key_findings": ["The selected Budget check reported a recorded concern."],
        "priority_actions": ["Review the existing deterministic recommendation."],
        "reasoning": ["The observed action selected the recorded specialists."],
        "agent_contributions": ["Budget supplied a finding for this case."],
        "limitations": ["The coordinated plan and conflicts were not assessed."],
    }


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
    assert skipped["reasoning_version"] == "monthly-case-reasoning-v3"
    assert skipped["source"] == "deterministic"
    assert skipped["fallback_reason"] == "not_requested"
    assert set(skipped["sections"]) == set(valid_sections())
    assert skipped["sections"]["key_findings"]
    assert skipped["sections"]["limitations"]
    explanations = skipped["recommendation_explanations"]
    assert [item["key"] for item in explanations] == [
        "summary", *[f"priority:{item['agent_id']}:{item['finding_code']}"
                     for item in case["methods"]["trained_rl"]["priority_actions"]]]
    for item in explanations:
        assert set(item) == {"key", "what", "why", "evidence", "agents", "orchestration", "limitations"}
        assert item["orchestration"].startswith("trained_rl selected action ")
        assert "feature causes are not available" in item["orchestration"]
    if case["methods"]["trained_rl"]["priority_actions"]:
        action = case["methods"]["trained_rl"]["priority_actions"][0]
        explained = explanations[1]
        assert explained["agents"] == [action["agent_id"]]
        assert explained["evidence"] == action["evidence"]
        assert explained["why"] == action["reason"]
    assert skipped["narrative"].startswith(" ".join(case["methods"]["trained_rl"]["explanation"]))
    first_finding = case["methods"]["trained_rl"]["agent_outputs"][0]["findings"][0]
    assert first_finding["reason"] in skipped["narrative"]
    priority = case["methods"]["trained_rl"]["priority_actions"]
    if priority:
        assert priority[0]["title"] in skipped["sections"]["priority_actions"][0]
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
    sections = valid_sections()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, *_args):
            return json.dumps({"status": "completed", "output": [{"type": "message",
                "content": [{"type": "output_text", "text": json.dumps(sections)}]}]}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "urlopen", fake_urlopen)
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "llm"
    assert answer["sections"] == sections
    assert answer["fallback_reason"] is None
    assert answer["deterministic"]["action"] == case["methods"]["trained_rl"]["action"]
    assert answer["deterministic"]["agent_outputs"] == case["methods"]["trained_rl"]["agent_outputs"]
    assert answer["recommendation_explanations"] == explain_case(case, "trained_rl")["recommendation_explanations"]
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["body"]["store"] is False
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True
    facts = json.loads(captured["body"]["input"][1]["content"])
    assert facts["selected_agents"] == case["methods"]["trained_rl"]["selected_agents"]
    assert facts["agent_findings"]
    assert facts["priority_actions"] == [
        {"agent_id": item["agent_id"], "title": item["title"], "reason": item["reason"]}
        for item in case["methods"]["trained_rl"]["priority_actions"]
    ]
    assert facts["conflicts_status"] == "not_assessed"
    assert "synthetic_id" not in facts and "user_state" not in facts and "email" not in str(facts)


def test_safe_json_fence_is_accepted(case, monkeypatch):
    from app.rl import dynamic_case_reasoning as reasoning

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "_provider_request",
                        lambda *_args: "```json\n" + json.dumps(valid_sections()) + "\n```")
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "llm"
    assert answer["sections"] == valid_sections()


@pytest.mark.parametrize("altered", [
    '{"summary": "unterminated',
    "Here are your results: " + json.dumps(valid_sections()),
    json.dumps({**valid_sections(), "extra": "unsupported"}),
    json.dumps({**valid_sections(), "priority_actions": "not a list"}),
    json.dumps({**valid_sections(), "agent_contributions": []}),
    json.dumps(valid_sections())[:-1] + ', "summary": "Overwritten by a duplicate key."}',
])
def test_malformed_or_invalid_structure_falls_back(case, monkeypatch, altered):
    from app.rl import dynamic_case_reasoning as reasoning

    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setattr(reasoning, "_provider_request", lambda *_args: altered)
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "deterministic"
    assert answer["fallback_reason"] == "invalid_output"
    assert set(answer["sections"]) == set(valid_sections())
    assert answer["deterministic"]["action"] == case["methods"]["trained_rl"]["action"]


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
    monkeypatch.setattr(reasoning, "_provider_request",
                        lambda *_args: json.dumps({**valid_sections(), "reasoning": [unsafe]}))
    answer = explain_case(case, "trained_rl", use_llm=True)
    assert answer["source"] == "deterministic"
    assert answer["fallback_reason"] == "invalid_output"
    assert unsafe not in json.dumps(answer["sections"])


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


def test_recommendation_explanation_rejects_a_mismatched_finding(case):
    changed = json.loads(json.dumps(case))
    method = next(name for name, detail in changed["methods"].items()
                  if detail["priority_actions"])
    changed["methods"][method]["priority_actions"][0]["finding_code"] = "made_up"
    with pytest.raises(ValueError, match="priority action"):
        explain_case(changed, method)


def test_summary_evidence_includes_nonpriority_selected_findings(case):
    detail = case["methods"]["rule_based"]
    priority_metrics = [metric for action in detail["priority_actions"] for metric in action["evidence"]]
    nonpriority_metric = next(metric for result in detail["agent_outputs"]
                              for finding in result["findings"] for metric in finding["evidence"]
                              if metric not in priority_metrics)
    summary = explain_case(case, "rule_based")["recommendation_explanations"][0]
    assert nonpriority_metric in summary["evidence"]
