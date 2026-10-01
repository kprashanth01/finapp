"""Explain actual actions and findings without inventing model causality."""

from decimal import Decimal as D

import pytest

from app.advisory.explain import build_explanation
from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.planning_types import AdvisoryResultV2
from app.advisory.registry import AgentRegistry
from app.rl.reward import audit_reward
from app.rl.selection import action_for
from test_planning_agents import goal, state


def test_saved_plan_links_allocations_and_actions_to_real_findings_and_values():
    snapshot = state([goal()], emergency_fund=D('4000'), existing_debt=D('10000'),
                     monthly_debt_payments=D('1000'))
    result = RuleBasedOrchestrator().run(snapshot, AgentRegistry.default())
    trace = result.explanation
    assert trace.method == 'rule_based'
    assert trace.state_fingerprint == snapshot.fingerprint()
    assert trace.action == action_for(item.agent_id for item in result.decision.selections if item.selected)
    assert trace.missing_agents == []
    assert trace.reward_components == audit_reward(snapshot, tuple(item.agent_id for item in result.agent_results)).components
    assert sum(trace.reward_components.values()) == audit_reward(snapshot, tuple(item.agent_id for item in result.agent_results)).total
    summary = next(item for item in trace.recommendations if item.kind == 'summary')
    assert summary.explainability.what == f'{result.advice.summary.title}: {result.advice.summary.text}'
    assert {'budget', 'emergency'} <= set(summary.explainability.agents)
    reserve = next(item for item in trace.recommendations if item.kind == 'reserve')
    assert '500.00' in reserve.text
    assert {item.agent_id for item in reserve.findings} == {'budget', 'emergency'}
    assert any(item.key == 'emergency_fund' and item.value == '4000' for item in reserve.context)
    assert any(f.finding.code == 'emergency_gap' and any(e.label == 'Gap to illustrative target' and e.value == D('5000')
               for e in f.finding.evidence) for f in reserve.findings)
    allocation = next(item for item in trace.recommendations if item.kind == 'goal')
    assert '0.00 assigned' in allocation.text and '500.00 monthly funding gap' in allocation.text
    assert {item.agent_id for item in allocation.findings} == {'budget', 'goal'}
    assert all(f.finding.code in {finding.code for result in result.agent_results for finding in result.findings}
               for rec in trace.recommendations for f in rec.findings)
    for item in trace.recommendations:
        explained = item.explainability
        assert explained.what == f'{item.title}: {item.text}'
        assert explained.why == ' '.join(f.finding.reason for f in item.findings)
        assert explained.agents == list(dict.fromkeys(f.agent_id for f in item.findings))
        assert explained.orchestration
        assert explained.evidence
        assert explained.limitations == item.limitations
        assert any('not validated financial outcomes' in limit for limit in explained.limitations)
    assert any(metric.label == 'Emergency fund balance' and metric.value == '4000'
               for metric in reserve.explainability.evidence)


def test_explanation_rejects_unresolved_recommendation_reference():
    result = RuleBasedOrchestrator().run(state(emergency_fund=D('1000')), AgentRegistry.default())
    changed = result.advice.model_copy(deep=True)
    changed.priority_actions[0].source_refs[0].finding_code = 'made_up'
    with pytest.raises(ValueError, match='Unresolved recommendation evidence'):
        build_explanation(result.state, result.decision, result.explanation.action,
                          result.agent_results, changed)


def test_rule_explanation_rejects_an_action_that_the_rule_would_not_choose():
    result = RuleBasedOrchestrator().run(state(), AgentRegistry.default())
    changed = result.decision.model_copy(deep=True)
    next(item for item in changed.selections if item.agent_id == 'investment').selected = False
    selected_results = [item for item in result.agent_results if item.agent_id != 'investment']
    with pytest.raises(ValueError, match='explicit selection rule'):
        build_explanation(result.state, changed,
                          action_for(item.agent_id for item in changed.selections if item.selected),
                          selected_results, None)


def test_partial_dqn_trace_reports_context_as_observation_not_cause(monkeypatch):
    from app.rl import orchestration

    class OnlyEmergency:
        def choose_action(self, snapshot, catalog):
            return catalog.action_for(('emergency',))

    monkeypatch.setattr(orchestration, 'get_policy', lambda mode, seed: OnlyEmergency())
    run = orchestration.run_orchestration(state([goal()], emergency_fund=D('4000')),
                                          mode='rl', seed=42)
    trace = run['explanation']
    assert run['advice'] is None
    assert trace['method'] == 'rl'
    assert 'do not establish which inputs caused' in trace['policy_explanation']
    assert trace['missing_agents']
    assert [item['agent_id'] for item in trace['selections'] if item['selected']] == ['emergency']
    assert any(item['key'] == 'emergency_fund' and item['value'] == '4000'
               for item in trace['selections'][2]['context'])
    assert all(all(f['agent_id'] == 'emergency' for f in rec['findings'])
               for rec in trace['recommendations'])
    assert all('feature influence is unavailable' in rec['explainability']['orchestration']
               for rec in trace['recommendations'])
    assert all(any('coordinated plan was withheld' in limit for limit in rec['explainability']['limitations'])
               for rec in trace['recommendations'])
    assert trace['reward_components'] == run['reward_components']


def test_missing_inputs_and_prior_saved_snapshots_remain_explicit():
    result = RuleBasedOrchestrator().run(
        state([goal()], monthly_savings_contribution=None, investment_horizon_years=None,
              existing_debt=D('1000'), monthly_debt_payments=None), AgentRegistry.default())
    trace = result.explanation
    assert any(item.value is None and item.key == 'monthly_savings_contribution'
               for selection in trace.selections for item in selection.context)
    assert any('Monthly savings contribution is unavailable' in item for item in trace.limitations)
    payload = result.model_dump(mode='json')
    payload.pop('explanation')
    assert AdvisoryResultV2.model_validate(payload).explanation is None
