from decimal import Decimal
from types import SimpleNamespace

from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.registry import AgentRegistry
from app.advisory.state import FinancialState
from app.services.financial_analysis import FinancialAnalysisService


def saved(income="5000", expenses="3000", savings="500", payments="200", debt="1000", fund="4000"):
    user = SimpleNamespace(monthly_income=Decimal(income))
    profile = SimpleNamespace(
        monthly_expenses=Decimal(expenses),
        savings=Decimal("8000"),
        monthly_savings_contribution=Decimal(savings) if savings is not None else None,
        monthly_debt_payments=Decimal(payments) if payments is not None else None,
        existing_debt=Decimal(debt),
        emergency_fund=Decimal(fund),
        risk_tolerance="moderate",
        financial_goal=None,
        investment_horizon_years=None,
    )
    analysis = FinancialAnalysisService.analyze(user, profile)
    return FinancialState.from_saved(user, profile, analysis)


def run(state):
    return RuleBasedOrchestrator().run(state, AgentRegistry.default())


def test_existing_profile_prioritizes_only_emergency_gap():
    result = run(saved())
    assert result.state.schema_version == "financial-state-v1"
    assert [action.agent_id for action in result.priority_actions] == ["emergency"]
    assert result.priority_actions[0].evidence[0].value == Decimal("1.33")
    assert result.priority_actions[0].evidence[1].value == Decimal("5000")
    assert [selection.agent_id for selection in result.decision.selections if selection.selected] == [
        "budget", "debt", "emergency"
    ]


def test_priority_order_is_emergency_then_debt_then_budget():
    result = run(saved(expenses="4250", payments="1250", fund="1000"))
    assert [action.agent_id for action in result.priority_actions] == [
        "emergency", "debt", "budget"
    ]
    assert result.priority_actions[1].evidence[0].value == Decimal("25.00")
    assert result.priority_actions[2].evidence[0].value == Decimal("85.00")


def test_missing_payment_and_savings_remain_unavailable():
    result = run(saved(savings=None, payments=None))
    budget, debt, emergency = result.agent_results
    assert budget.status == "limited"
    assert debt.status == "limited"
    assert budget.findings[0].evidence[1].value is None
    assert debt.findings[0].evidence[0].value is None
    assert [action.agent_id for action in result.priority_actions] == ["emergency"]


def test_zero_denominators_do_not_break_analysis():
    result = run(saved(income="0", expenses="0", payments=None))
    assert all(agent.status == "limited" for agent in result.agent_results)
    assert result.priority_actions == []


def test_no_debt_skips_agent_and_records_reason():
    result = run(saved(debt="0", payments="0", fund="20000"))
    assert [agent.agent_id for agent in result.agent_results] == ["budget", "emergency"]
    debt_selection = next(s for s in result.decision.selections if s.agent_id == "debt")
    assert debt_selection.selected is False
    assert "no outstanding debt" in debt_selection.reason.lower()
    assert result.priority_actions == []


def test_thresholds_use_unrounded_saved_amounts():
    below_expense_and_debt = run(saved(expenses="3999.99", payments="999.99", fund="20000"))
    assert below_expense_and_debt.priority_actions == []

    below_emergency_target = run(saved(expenses="1000", payments="0", debt="0", fund="2999.99"))
    assert [action.agent_id for action in below_emergency_target.priority_actions] == ["emergency"]
    assert below_emergency_target.priority_actions[0].evidence[1].value == Decimal("0.01")
