"""Local monthly answers must cite saved facts and reject invented hardship."""

from io import BytesIO
import json

from app.rl import account_months_chat as chat


REPORT = {
    "month": {"period": "2026-09-01", "monthly_income": "0.00", "monthly_expenses": "3500.00",
              "fixed_expenses": "2500.00", "scheduled_emi": "500.00", "paid_emi": "500.00",
              "outstanding_debt": "10000.00", "savings": "7000.00", "emergency_fund": "4500.00",
              "unfunded_expenses": "0.00"},
    "context": {"previous_recorded_period": "2026-08-01", "previous_month_income": "6000.00",
                "recent_income_change_ratio": "-1", "recent_income_change_percent": "-100.00",
                "income_volatility": "1", "usual_income_reference": "6000.00",
                "net_cash_flow": "-3500.00"},
    "methods": {name: {"action": 1, "selected_agents": ["budget", "emergency"],
                        "reward_audit": {"missed_critical_agents": ["debt"]},
                        "recommendation": {"status": "partial"},
                        "priority_actions": [{"agent_id": "budget", "title": "Review this month's budget",
                                              "reason": "Scheduled expenses exceed current income."}]}
                for name in ("trained_rl", "rule_based")},
    "focused_review": None, "limitations": ["Synthetic training does not establish account outcomes."],
    "state_fingerprint": "a" * 64,
}


def test_question_uses_verified_local_evidence_and_rejects_unfunded_claim(monkeypatch):
    monkeypatch.setattr(chat, "_model_available", lambda model: True)

    def provider(answer):
        draft = {"answer": answer, "evidence_ids": ["month:scheduled_emi"]}
        payload = {"message": {"content": json.dumps(draft)}}
        return BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(chat, "urlopen", lambda *args, **kwargs: provider("Review the scheduled loan payment recorded for this month."))
    accepted = chat.answer_month_question(REPORT, "What about my loan?")
    assert accepted["source"] == "local_model"
    assert accepted["evidence"][0]["id"] == "month:scheduled_emi"

    monkeypatch.setattr(chat, "urlopen", lambda *args, **kwargs: provider("Your expenses are unfunded and the loan payment was missed."))
    rejected = chat.answer_month_question(REPORT, "What about my loan?")
    assert rejected["source"] == "unavailable"
    assert rejected["answer"] is None
    assert not any(item.id.startswith("user:") for item in chat._evidence(REPORT))
