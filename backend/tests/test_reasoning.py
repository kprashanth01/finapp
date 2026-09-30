"""The optional provider can narrate evidence but cannot alter financial facts."""

import json

from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.reasoning import SECTION_NAMES, evidence_for, explain_run
from app.advisory.registry import AgentRegistry
from test_planning_agents import state


def _run():
    result = RuleBasedOrchestrator().run(state(), AgentRegistry.default())
    return result.explanation, result.advice.summary.model_dump()


def _valid_draft(evidence):
    ids = [item.id for item in evidence]
    lookup = {
        'financial_overview': next(item for item in ids if item.startswith('metric:')),
        'agent_analysis': next(item for item in ids if item.startswith('finding:')),
        'orchestration_decision': 'decision',
        'final_recommendation': next(item for item in ids if item.startswith('recommendation:')),
        'why_this_recommendation': next(item for item in ids if item.startswith('recommendation:')),
        'limitations': next(item for item in ids if item.startswith('limitation:')),
    }
    return {name: {'text': 'The linked evidence supports this educational explanation.',
                   'evidence_ids': [lookup[name]]} for name in SECTION_NAMES}


def test_provider_request_is_explicit_minimal_and_successful(monkeypatch):
    from app.advisory import reasoning

    trace, summary = _run()
    evidence = evidence_for(trace, summary)
    draft = _valid_draft(evidence)
    captured = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def read(self, *_args):
            return json.dumps({'status': 'completed', 'output': [{'type': 'message',
                'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]}).encode()

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['timeout'] = timeout
        captured['body'] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(reasoning, 'urlopen', fake_urlopen)
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-key')
    answer = explain_run(trace, summary)
    assert answer.source == 'llm'
    assert answer.sections.agent_analysis.text == draft['agent_analysis']['text']
    assert answer.fallback_reason is None
    assert captured['url'] == 'https://api.openai.com/v1/responses'
    assert captured['body']['store'] is False
    assert captured['body']['text']['format']['strict'] is True
    provider_facts = json.loads(captured['body']['input'][1]['content'])
    assert provider_facts['reward_components'] == trace.reward_components
    assert provider_facts['orchestration_decision']['id'] == 'decision'
    assert provider_facts['agent_results']
    assert 'email' not in captured['body']['input'][1]['content']


def test_unlinked_or_invented_content_falls_back(monkeypatch):
    from app.advisory import reasoning

    trace, summary = _run()
    evidence = evidence_for(trace, summary)
    valid = _valid_draft(evidence)
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-key')
    monkeypatch.setattr(reasoning, '_provider_request', lambda *_args: {
        **valid, 'final_recommendation': {'text': 'A guaranteed return of 20% follows.',
                                          'evidence_ids': valid['final_recommendation']['evidence_ids']}})
    answer = explain_run(trace, summary)
    assert answer.source == 'deterministic'
    assert answer.fallback_reason == 'invalid_output'
    assert 'guaranteed return' not in str(answer)
    monkeypatch.setattr(reasoning, '_provider_request', lambda *_args: {
        **valid, 'agent_analysis': {'text': 'The linked evidence supports this educational explanation.',
                                    'evidence_ids': ['finding:made-up:unknown']}})
    assert explain_run(trace, summary).fallback_reason == 'invalid_output'
