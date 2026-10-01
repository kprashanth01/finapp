"""The website demo must reproduce a real held-out monthly DQN decision."""

from app.rl.monthly_demo import build_monthly_demo


def test_salaried_income_drop_changes_trained_selection_and_keeps_provenance():
    demo = build_monthly_demo()

    assert demo["source"]["dataset_split"] == "test"
    assert demo["source"]["scenario"] == "B"
    assert demo["source"]["model_version"] == "dynamic-dqn-monthly-v1"
    assert demo["persona"] == "salaried_with_loan"
    first, second = demo["months"]
    assert first["monthly_state"]["monthly_income"] == "168744.03"
    assert second["monthly_state"]["monthly_income"] == "62867.67"
    assert first["methods"]["trained_rl"]["action"] == 20
    assert second["methods"]["trained_rl"]["action"] == 22
    assert second["methods"]["trained_rl"]["selected_agents"] == [
        "budget", "debt", "emergency", "risk",
    ]
    assert second["methods"]["trained_rl"]["reward"] > second["methods"]["rule_based"]["reward"]
    assert second["methods"]["trained_rl"]["reward_audit"]["missed_critical_agents"] == []
    assert any(action["title"] == "Review this month's budget" for action in
               second["methods"]["trained_rl"]["priority_actions"])
    assert second["methods"]["trained_rl"]["recommendation"]["status"] == "partial"
    assert "synthetic" in " ".join(demo["limitations"]).lower()
