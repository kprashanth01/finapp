"""Read-only answers assembled from one saved Advisor result."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.advisory.planning_types import AdvisoryResultV2, ExplanationMetric, ExplanationRecommendation


Topic = Literal['overview', 'recommendation', 'emergency', 'debt', 'budget', 'goal', 'risk',
                'investment', 'selection', 'limitations', 'state', 'unsupported']
AGENT_TOPICS = {'emergency': 'emergency', 'debt': 'debt', 'budget': 'budget',
                'goal': 'goal', 'risk': 'risk', 'investment': 'investment'}
AGENT_NAMES = {'emergency': 'Emergency fund', 'debt': 'Debt', 'budget': 'Budget',
               'goal': 'Goal planning', 'risk': 'Risk assessment', 'investment': 'Investment readiness'}


class ChatQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=500, pattern=r'\S')
    context_topic: Topic | None = None
    use_model: bool = False
    history: list['ChatTurn'] = Field(default_factory=list, max_length=6)


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1, max_length=1200)


class ChatEvidence(BaseModel):
    id: str
    label: str
    detail: str


class ChatAnswer(BaseModel):
    source: Literal['saved_run', 'llm'] = 'saved_run'
    fallback_reason: Literal['not_configured', 'provider_error', 'invalid_output'] | None = None
    model: str | None = None
    session_id: int
    state_fingerprint: str
    topic: Topic
    answer: str
    evidence: list[ChatEvidence]


def _topic(question: str, context: Topic | None) -> Topic:
    text = question.lower().strip()
    if re.search(r'\b(ignore|override|guarantee\w*|predict\w*|forecast\w*|buy|sell|trade|stock|crypto|bitcoin)\b', text) or re.search(r'\bhow much should\b', text):
        return 'unsupported'
    if context and context != 'unsupported' and re.fullmatch(r'(why|how|what about that|tell me more)[?.!\s]*', text):
        return context
    if re.search(r'\b(how much|what (?:is|was|are|were) my|show (?:my|the) (?:saved )?(?:amount|number))\b', text) and re.search(
            r'\b(income|expense\w*|saving\w*|debt|emergency fund|balance|risk tolerance|investment horizon)\b', text):
        return 'state'
    for topic, pattern in (
        ('emergency', r'\b(emergency|reserve|liquidity)\b'),
        ('debt', r'\b(debt|loan|repayment)\b'),
        ('budget', r'\b(budget|spend\w*|expense\w*)\b'),
        ('goal', r'\b(goal|target|saving for)\b'),
        ('risk', r'\b(risk|tolerance)\b'),
        ('investment', r'\b(invest\w*|portfolio)\b'),
        ('selection', r'\b(orchestrat\w*|select\w*|chosen|choose|agent|arrive\w*|decid\w*)\b'),
        ('limitations', r'\b(limit\w*|missing|assum\w*|uncertain\w*)\b'),
        ('state', r'\b(income|balance|amount|number\w*|profile|financial state)\b'),
        ('recommendation', r'\b(recommend\w*|priorit\w*|focus|attention|next|why|how)\b'),
    ):
        if re.search(pattern, text):
            return topic
    if re.search(r'\b(run|analysis|session|report)\b', text) and re.search(
            r'\b(contain\w*|includ\w*|show\w*|cover\w*|summari\w*|overview|inside|in|find\w*|found|record\w*)\b', text):
        return 'overview'
    return 'unsupported'


def _metric(metric: ExplanationMetric) -> ChatEvidence:
    unit = 'profile currency' if metric.unit == 'currency' else metric.unit
    value = 'unavailable' if metric.value is None else f'{metric.value}{unit if unit == "%" else " " + unit if unit else ""}'
    return ChatEvidence(id=f'metric:{metric.key}', label=metric.label, detail=value.strip())


def _recommendation(rec: ExplanationRecommendation, index: int, include_decision: bool,
                    result: AdvisoryResultV2) -> tuple[str, list[ChatEvidence]]:
    detail = rec.explainability
    what = detail.what if detail else f'{rec.title}: {rec.text}'
    why = detail.why if detail else ' '.join(item.finding.reason for item in rec.findings)
    answer = ' '.join(filter(None, [what, why if why and why not in what else None,
                                    detail.orchestration if include_decision and detail else None]))
    evidence = [ChatEvidence(id=f'recommendation:{index}', label=rec.title, detail=rec.text)]
    evidence.extend(_metric(item) for item in (detail.evidence if detail else rec.context)[:5])
    for item in rec.findings[:2]:
        if not any(card.label == item.finding.title and card.detail == item.finding.reason for card in evidence):
            evidence.append(ChatEvidence(id=f'finding:{item.agent_id}:{item.finding.code}',
                                         label=item.finding.title, detail=item.finding.reason))
    if include_decision:
        evidence.append(ChatEvidence(id='decision', label='Agent selection',
                                     detail=result.explanation.policy_explanation))
    return answer, evidence


def answer_saved_question(result: AdvisoryResultV2, session_id: int, request: ChatQuestion) -> ChatAnswer:
    trace = result.explanation
    if trace is None:
        raise ValueError('This saved run has no explanation trace.')
    topic = _topic(request.question, request.context_topic)
    evidence: list[ChatEvidence] = []
    if topic == 'overview':
        findings = [(agent.agent_id, finding) for agent in result.agent_results for finding in agent.findings]
        summary = result.advice.summary
        capacity = result.advice.monthly_plan.capacity
        answer = (f'This saved run contains your financial snapshot from {result.state.as_of_date.isoformat()}, '
                  f'the {result.decision.method.replace("_", "-")} agent selection and findings, '
                  f'the recommendation “{summary.title}”, a proposed monthly plan, '
                  'and the evidence and limitations behind it.')
        evidence = [
            ChatEvidence(id='state:as_of_date', label='Saved financial snapshot',
                         detail=result.state.as_of_date.isoformat()),
            ChatEvidence(id='state:monthly_income', label='Gross monthly income',
                         detail=f'{result.state.monthly_income} (profile currency)'),
            ChatEvidence(id='state:monthly_expenses', label='Monthly expenses',
                         detail=f'{result.state.monthly_expenses} (profile currency)'),
            ChatEvidence(id='state:emergency_fund', label='Emergency fund',
                         detail=f'{result.state.emergency_fund} (profile currency)'),
            ChatEvidence(id='decision', label='Agent selection',
                         detail=f'Action {trace.action}; {trace.policy_explanation}'),
            ChatEvidence(id='recommendation:summary', label=summary.title, detail=summary.text),
            ChatEvidence(id='plan:capacity', label='Monthly savings budget',
                         detail='not supplied' if capacity is None else f'{capacity} (profile currency)'),
        ]
        if findings:
            agent_id, finding = findings[0]
            evidence.append(ChatEvidence(id=f'finding:{agent_id}:{finding.code}',
                                         label=finding.title, detail=finding.reason))
        if trace.limitations:
            evidence.append(ChatEvidence(id='limitation:0', label='Recorded limitation',
                                         detail=trace.limitations[0]))
    elif topic in AGENT_TOPICS or topic == 'recommendation':
        agent = AGENT_TOPICS.get(topic)
        matches = [(index, rec) for index, rec in enumerate(trace.recommendations)
                   if agent is None or agent in (rec.explainability.agents if rec.explainability else
                                                 [finding.agent_id for finding in rec.findings])]
        if agent:
            matches.sort(key=lambda pair: pair[1].kind == 'summary')
        if matches:
            index, rec = matches[0]
            answer, evidence = _recommendation(rec, index, topic == 'recommendation', result)
        elif agent:
            selection = next((item for item in trace.selections if item.agent_id == agent), None)
            if selection:
                answer = (f'This saved run recorded no {AGENT_NAMES[agent].lower()} recommendation. '
                          f'{AGENT_NAMES[agent]} was {"run" if selection.selected else "skipped"}. {selection.basis}')
                evidence = [ChatEvidence(id=f'selection:{agent}', label=f'{AGENT_NAMES[agent]} selection',
                                         detail=selection.basis)]
            else:
                answer = f'This saved run has no {AGENT_NAMES[agent].lower()} finding to explain.'
        else:
            answer = 'This saved run recorded no recommendation. Review its agent findings and limits.'
    elif topic == 'selection':
        ran = [AGENT_NAMES.get(item.agent_id, item.agent_id) for item in trace.selections if item.selected]
        answer = f'{trace.policy_explanation} Agents run: {", ".join(ran) if ran else "none"}.'
        evidence = [ChatEvidence(id='decision', label='Stored orchestrator decision',
                                 detail=f'Action {trace.action}; {trace.policy_explanation}')]
        if 'recommendation' in request.question.lower() and trace.recommendations:
            rec_answer, rec_evidence = _recommendation(trace.recommendations[0], 0, False, result)
            answer = f'{rec_answer} {answer}'
            evidence = rec_evidence + evidence
    elif topic == 'limitations':
        answer = ' '.join(trace.limitations[:3]) if trace.limitations else 'No additional limitation was recorded for this run.'
        evidence = [ChatEvidence(id=f'limitation:{index}', label='Recorded limitation', detail=value)
                    for index, value in enumerate(trace.limitations[:3])]
    elif topic == 'state':
        lower = request.question.lower()
        selected = []
        if re.search(r'\bincome\b', lower):
            selected.append(('monthly_income', 'Gross monthly income', 'profile currency'))
        if re.search(r'\b(expense\w*|spend\w*)\b', lower):
            selected.append(('monthly_expenses', 'Monthly expenses', 'profile currency'))
        if re.search(r'\b(saving\w*|contribution)\b', lower):
            selected.append(('monthly_savings_contribution', 'Monthly savings contribution', 'profile currency')
                            if re.search(r'\b(monthly|contribution)\b', lower) else
                            ('savings', 'Savings balance', 'profile currency'))
        if re.search(r'\b(debt|repayment\w*)\b', lower):
            selected.append(('monthly_debt_payments', 'Monthly debt payments', 'profile currency')
                            if re.search(r'\b(payment\w*|repayment\w*)\b', lower) else
                            ('existing_debt', 'Outstanding debt', 'profile currency'))
        if re.search(r'\b(emergency fund|reserve)\b', lower):
            selected.append(('emergency_fund', 'Emergency fund', 'profile currency'))
        if re.search(r'\brisk tolerance\b', lower):
            selected.append(('risk_tolerance', 'Risk tolerance', ''))
        if re.search(r'\binvestment horizon\b', lower):
            selected.append(('investment_horizon_years', 'Investment horizon', 'years'))
        if not selected:
            selected = [('monthly_income', 'Gross monthly income', 'profile currency'),
                        ('monthly_expenses', 'Monthly expenses', 'profile currency'),
                        ('monthly_savings_contribution', 'Monthly savings contribution', 'profile currency')]
        evidence = [ChatEvidence(id=f'state:{key}', label=label,
                                 detail='not supplied' if getattr(result.state, key) is None else
                                 f'{getattr(result.state, key)}{f" ({unit})" if unit else ""}')
                    for key, label, unit in selected[:3]]
        answer = 'The saved run recorded ' + '; '.join(f'{item.label}: {item.detail}' for item in evidence) + '.'
    else:
        answer = ('I can answer questions about this saved run’s recommendation, agent selection, '
                  'financial inputs, and recorded limitations. This run cannot support a prediction '
                  'or a product-specific instruction.')
    return ChatAnswer(session_id=session_id, state_fingerprint=trace.state_fingerprint,
                      topic=topic, answer=answer, evidence=evidence)
