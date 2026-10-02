"""Current chat uses the same owned picture and ranked decisions as Dashboard."""

from datetime import date, timedelta

from tests.test_advisory_api import client, create_profile


def test_current_chat_uses_current_recommendations_without_a_saved_run(client):
    user, profile = create_profile(client)
    user_id = user['id']
    due = (date.today() + timedelta(days=5)).isoformat()
    detail = {'income_pattern': 'stable', 'guaranteed_monthly_income': None,
              'recurring_expenses': [], 'loans': [],
              'planned_expenses': [{'name': 'Insurance', 'estimated_amount': '800',
                                    'amount_reserved': '100', 'due_date': due, 'is_essential': True}]}
    assert client.put(f'/users/{user_id}/financial-details', json=detail).status_code == 200
    path = f'/users/{user_id}/current-chat'

    first = client.post(path, json={'question': 'What should I prioritize?'}).json()
    assert first['source'] == 'current_picture'
    assert first['topic'] == 'priorities'
    assert first['answer']
    assert first['evidence'][0]['id'] == 'recommendation:1'
    assert 'Insurance' in first['evidence'][0]['detail']
    assert client.get(f'/users/{user_id}/advisory-sessions').json()['items'] == []

    expense = client.post(path, json={'question': 'Can I afford Insurance?'}).json()
    assert expense['topic'] == 'affordability'
    assert 'Insurance' in expense['answer']
    assert any(item['id'].startswith('obligation:planned_expense:') for item in expense['evidence'])
    assert 'cannot confirm' in expense['answer'].lower()

    profile['emergency_fund'] = '9000.00'
    assert client.put(f'/users/{user_id}/financial-profile', json=profile).status_code == 200
    changed = client.post(path, json={'question': 'Why should I save?'}).json()
    assert changed['topic'] == 'why'
    assert changed['source'] == 'current_picture'
    assert changed['as_of_date'] == first['as_of_date']
    assert any('9000.00' in item['detail'] for item in changed['evidence'] if item['id'] == 'reserve:balance')


def test_current_chat_previews_new_cash_and_requires_an_owned_profile(client):
    user, _ = create_profile(client)
    path = f"/users/{user['id']}/current-chat"
    extra = client.post(path, json={'question': 'I got 10000 extra. What should I do?'}).json()
    assert extra['topic'] == 'scenario'
    assert extra['scenario']['event']['kind'] == 'one_time_income'
    assert extra['scenario']['one_time_cash_inflow'] == '10000.00'
    assert 'not automatically assigned' in extra['answer'].lower()
    affordable = client.post(path, json={'question': 'Can I afford a trip?'}).json()
    assert affordable['topic'] == 'affordability'
    assert 'cost' in affordable['answer'].lower()
    reserve = client.post(path, json={'question': 'How much emergency fund do I have?'}).json()
    assert reserve['topic'] == 'state'
    assert [item['id'] for item in reserve['evidence']] == ['reserve:balance', 'reserve:coverage', 'reserve:gap']
    assert '4000.00' in reserve['answer']
    available = client.post(path, json={'question': 'I have 20000 available. Should I save or pay my loan?'}).json()
    assert available['topic'] == 'extra_money'
    assert '20000' not in available['answer']
    assert client.post(path, json={'question': 'a'}).status_code == 422

    other, _ = create_profile(client, email='other-current-chat@example.org')
    assert client.post(path, json={'question': 'What should I prioritize?'}).status_code == 404
    assert client.post(f"/users/{other['id']}/current-chat", json={'question': 'What should I prioritize?'}).status_code == 200


def test_current_chat_model_gets_structured_context_and_rejects_invented_numbers(client, monkeypatch):
    from app.services import current_chat

    user, _ = create_profile(client)
    path = f"/users/{user['id']}/current-chat"
    monkeypatch.setattr(current_chat, '_model_available', lambda _model: True)
    seen = {}

    def provider(catalog, question, history, model, feedback=None):
        seen.update(catalog=catalog, question=question, history=history, model=model)
        if feedback is None:
            return {'answer': 'Set aside 999999.00 profile currency for the reserve.',
                    'evidence_ids': ['reserve:gap']}
        return {'answer': 'Review the current reserve gap before assigning extra money to a goal.',
                'evidence_ids': ['reserve:gap', 'recommendation:1']}

    monkeypatch.setattr(current_chat, '_provider_request', provider)
    answer = client.post(path, json={'question': 'Why should I save instead of investing?', 'use_model': True,
                                     'history': [{'question': 'What matters first?', 'answer': 'Check my reserve.'}]}).json()
    assert answer['source'] == 'llm'
    assert answer['fallback_reason'] is None
    assert answer['topic'] == 'why'
    assert [item['id'] for item in answer['evidence']] == ['reserve:gap', 'recommendation:1']
    assert seen['history'][0].question == 'What matters first?'
    assert all(item.id != 'user:email' for item in seen['catalog'])

    monkeypatch.setattr(current_chat, '_model_available', lambda _model: False)
    fallback = client.post(path, json={'question': 'What should I prioritize?', 'use_model': True}).json()
    assert fallback['source'] == 'current_picture'
    assert fallback['fallback_reason'] == 'not_configured'


def test_current_chat_does_not_ask_a_model_to_decide_an_uncalculated_scenario(client, monkeypatch):
    from app.services import current_chat

    user, _ = create_profile(client)
    monkeypatch.setattr(current_chat, '_model_available', lambda _model: True)
    monkeypatch.setattr(current_chat, '_provider_request',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('model should not decide a scenario')))
    path = f"/users/{user['id']}/current-chat"
    for question in ('I received 10000 extra. What should I do?', 'What if my income falls?',
                     'Can I afford a new trip?'):
        response = client.post(path, json={'question': question, 'use_model': True})
        assert response.status_code == 200, response.text
        assert response.json()['source'] == 'current_picture'


def test_current_chat_retry_tells_model_to_keep_citation_numbers_out_of_prose(client, monkeypatch):
    from app.services import current_chat

    user, _ = create_profile(client)
    monkeypatch.setattr(current_chat, '_model_available', lambda _model: True)
    feedback_seen = []

    def provider(_catalog, _question, _history, _model, feedback=None):
        feedback_seen.append(feedback)
        if feedback is None:
            return {'answer': 'Review the emergency reserve [1].', 'evidence_ids': ['recommendation:1']}
        return {'answer': 'Review the emergency reserve because it is below the illustrative target.',
                'evidence_ids': ['recommendation:1']}

    monkeypatch.setattr(current_chat, '_provider_request', provider)
    response = client.post(f"/users/{user['id']}/current-chat",
                           json={'question': 'Why should I review my reserve?', 'use_model': True})
    assert response.status_code == 200, response.text
    assert response.json()['source'] == 'llm'
    assert 'bracketed citation' in feedback_seen[1]


def test_current_chat_short_follow_up_uses_the_previous_topic(client):
    user, _ = create_profile(client)
    path = f"/users/{user['id']}/current-chat"
    answer = client.post(path, json={
        'question': 'What about that?',
        'history': [{'question': 'What should I prioritize?', 'answer': 'Review the reserve.'}],
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()['topic'] == 'priorities'
    assert answer.json()['evidence'][0]['id'] == 'recommendation:1'
