"""Trace observed selections and advice to the facts that produced them.

The trace never attributes a DQN choice to individual input features. It
describes the choice, then separately reports relevant saved context.
"""

from app.advisory.planning_types import (
    CoordinatedAdvice, EvidenceRef, ExplanationFinding, ExplanationMetric,
    ExplanationRecommendation, ExplanationSelection, ExplanationTrace,
    PlanningAgentResult,
)
from app.advisory.state import PlanningState
from app.advisory.types import OrchestratorDecision
from app.rl.reward import audit_reward
from app.rl.selection import AGENT_IDS, action_for, assess_plan_readiness, rule_action


METRICS = {
    'monthly_income': ('Gross monthly income', 'profile currency'),
    'monthly_expenses': ('Monthly expenses', 'profile currency'),
    'monthly_savings_contribution': ('Monthly savings contribution', 'profile currency'),
    'expense_to_income_percent': ('Expense-to-income ratio', '%'),
    'savings_rate_percent': ('Savings rate', '%'),
    'existing_debt': ('Outstanding debt', 'profile currency'),
    'monthly_debt_payments': ('Monthly debt payments', 'profile currency'),
    'debt_to_income_percent': ('Debt-to-income ratio', '%'),
    'emergency_fund': ('Emergency fund balance', 'profile currency'),
    'emergency_fund_months': ('Emergency fund coverage', 'months'),
    'risk_tolerance': ('Risk preference', ''),
    'investment_horizon_years': ('Investment horizon', 'years'),
    'active_goal_count': ('Active goals', 'goals'),
}

AGENT_METRICS = {
    'budget': ('monthly_income', 'monthly_expenses', 'monthly_savings_contribution',
               'expense_to_income_percent', 'savings_rate_percent'),
    'debt': ('existing_debt', 'monthly_debt_payments', 'debt_to_income_percent'),
    'emergency': ('monthly_expenses', 'emergency_fund', 'emergency_fund_months'),
    'goal': ('active_goal_count', 'monthly_savings_contribution'),
    'risk': ('risk_tolerance', 'investment_horizon_years'),
    'investment': ('monthly_income', 'monthly_savings_contribution',
                   'emergency_fund_months', 'debt_to_income_percent',
                   'investment_horizon_years'),
}


def _metrics(state: PlanningState, agent_ids) -> list[ExplanationMetric]:
    keys = dict.fromkeys(key for agent_id in agent_ids for key in AGENT_METRICS[agent_id])
    metrics = []
    for key in keys:
        value = len(state.goals) if key == 'active_goal_count' else getattr(state, key)
        label, unit = METRICS[key]
        metrics.append(ExplanationMetric(key=key, label=label,
                                         value=str(value) if value is not None else None,
                                         unit=unit))
    return metrics


def _rule_basis(agent_id: str, selected: bool) -> str:
    if agent_id == 'debt':
        return ('Selected because a saved debt balance or positive payment is present.' if selected else
                'Skipped because no debt balance or positive payment is recorded.')
    if agent_id == 'goal':
        return ('Selected because active goals are recorded.' if selected else
                'Skipped because no active goal is recorded.')
    return 'Selected by the explicit rule for every profile.'


def build_explanation(state: PlanningState, decision: OrchestratorDecision, action: int,
                      results: list[PlanningAgentResult], advice: CoordinatedAdvice | None,
                      *, seed: int | None = None) -> ExplanationTrace:
    """Build a verifiable chain from one immutable state and real agent output."""
    selected = tuple(item.agent_id for item in decision.selections if item.selected)
    if (len(decision.selections) != len(AGENT_IDS) or
            {item.agent_id for item in decision.selections} != set(AGENT_IDS) or
            len(selected) != len(set(selected)) or
            set(selected) != {item.agent_id for item in results} or
            len(results) != len(selected) or action_for(selected) != action):
        raise ValueError('Explanation selection does not match the executed agents.')
    if advice is not None and not assess_plan_readiness(state, selected)['can_build_full_plan']:
        raise ValueError('A complete recommendation needs the required agent findings.')
    if decision.method == 'rule_based' and action != rule_action(state):
        raise ValueError('Rule explanation does not match the explicit selection rule.')
    if decision.method == 'random' and seed is None:
        raise ValueError('A random selection explanation needs its seed.')
    by_id = {item.agent_id: item for item in results}
    selected_set = set(selected)
    readiness = assess_plan_readiness(state, selected)

    if decision.method == 'rule_based':
        policy_explanation = ('The explicit rule selects Budget, Emergency Fund, Risk, and Investment for every profile; '
                              'it adds Debt when debt is recorded and Goal Planning when active goals exist.')
    elif decision.method == 'rl':
        policy_explanation = (f'The trained DQN predicted action {action}. The saved values below describe the context '
                              'and the agents that ran; they do not establish which inputs caused this model choice.')
    else:
        policy_explanation = (f'Seeded random selection produced action {action} with seed {seed}. '
                              'Saved financial values did not cause this selection.')

    selections = []
    for item in decision.selections:
        if decision.method == 'rule_based':
            basis = _rule_basis(item.agent_id, item.selected)
        elif decision.method == 'rl':
            basis = ('Selected' if item.selected else 'Skipped') + ' by the DQN; individual feature influence is unavailable.'
        else:
            basis = ('Selected' if item.selected else 'Skipped') + ' by the seeded random draw.'
        selections.append(ExplanationSelection(agent_id=item.agent_id, selected=item.selected,
                                                basis=basis, context=_metrics(state, [item.agent_id])))

    def recommendation(kind: str, title: str, text: str, refs: list[EvidenceRef],
                       limitations=()) -> ExplanationRecommendation:
        if not refs:
            raise ValueError('A recommendation needs at least one finding reference.')
        findings = []
        for ref in refs:
            agent = by_id.get(ref.agent_id)
            finding = next((item for item in agent.findings if item.code == ref.finding_code), None) if agent else None
            if finding is None:
                raise ValueError(f'Unresolved recommendation evidence: {ref.agent_id}/{ref.finding_code}.')
            findings.append(ExplanationFinding(agent_id=ref.agent_id, finding=finding))
        agents = tuple(dict.fromkeys(ref.agent_id for ref in refs))
        all_limits = list(dict.fromkeys([*limitations,
            *(limit for linked in findings for limit in linked.finding.limitations),
            *(limit for agent_id in agents for limit in by_id[agent_id].limitations)]))
        return ExplanationRecommendation(kind=kind, title=title, text=text,
                                         findings=findings, context=_metrics(state, agents),
                                         limitations=all_limits)

    recommendations = []
    if advice is None:
        for agent in results:
            for finding in agent.findings:
                if finding.priority:
                    recommendations.append(recommendation('partial_finding', finding.title, finding.reason,
                        [EvidenceRef(agent_id=agent.agent_id, finding_code=finding.code)], finding.limitations))
    else:
        for item in advice.priority_actions:
            recommendations.append(recommendation('priority', item.title, item.reason,
                                                   item.source_refs, item.limitations))
        plan = advice.monthly_plan
        if plan.emergency_allocation is not None and plan.emergency_allocation > 0:
            recommendations.append(recommendation(
                'reserve', 'Emergency reserve allocation',
                f'{plan.emergency_allocation:.2f} of the monthly savings budget is assigned to the emergency reserve.',
                [EvidenceRef(agent_id=agent_id, finding_code=by_id[agent_id].findings[0].code)
                 for agent_id in ('budget', 'emergency')]))
        for allocation in plan.goal_allocations:
            if allocation.requirement.status != 'future':
                continue
            recommendations.append(recommendation(
                'goal', f'Monthly allocation for {allocation.requirement.goal.name}',
                (f'{allocation.allocated_monthly:.2f} assigned per month; '
                 f'{allocation.funding_gap:.2f} monthly funding gap.'
                 if allocation.allocated_monthly is not None and allocation.funding_gap is not None else
                 'Monthly allocation is unavailable until a savings contribution is recorded.'),
                [EvidenceRef(agent_id='budget', finding_code=by_id['budget'].findings[0].code),
                 *allocation.source_refs]))
        if plan.hold_reason:
            hold_agent = 'emergency' if by_id['emergency'].facts.gap is None else 'debt'
            refs = [EvidenceRef(agent_id='budget', finding_code=by_id['budget'].findings[0].code)]
            if hold_agent in by_id:
                refs.append(EvidenceRef(agent_id=hold_agent, finding_code=by_id[hold_agent].findings[0].code))
            recommendations.append(recommendation('hold', 'Unassigned savings held for review',
                                                   plan.hold_reason, refs))
        recommendations.append(recommendation(
            'investment', 'Investment readiness',
            ('Ready to consider under the project prerequisites.' if advice.investment.status == 'ready_to_consider' else
             'Address recorded blockers first.' if advice.investment.status == 'deferred' else
             'More saved information is needed for this check.'),
            advice.investment.source_refs, advice.investment.reasons))

    limitations = ['This trace explains project rules and observed agent findings, not validated financial outcomes.']
    if decision.method == 'rl':
        limitations.append('DQN feature attribution is unavailable; saved context is not a causal model explanation.')
    if advice is None:
        limitations.append('A complete monthly plan was withheld because required agents did not run.')
    for agent in results:
        if agent.status == 'limited':
            limitations.extend(agent.limitations)
    for item in selections:
        if item.selected:
            limitations.extend(f'{metric.label} is unavailable.' for metric in item.context if metric.value is None)
    return ExplanationTrace(method=decision.method, action=action, seed=seed if decision.method == 'random' else None,
        state_fingerprint=state.fingerprint(), policy_explanation=policy_explanation,
        selections=selections, recommendations=recommendations,
        reward_components=audit_reward(state, selected).components,
        missing_agents=readiness['missing_agents'], limitations=list(dict.fromkeys(limitations)))
