"""Natural what-if questions use the temporary event engine, never model arithmetic."""

from tests.test_event_scenario import account, client


def ask(client, user_id, question, **extra):
    return client.post(f'/users/{user_id}/current-chat', json={
        'question': question, 'use_model': True, **extra,
    })


def test_absolute_and_relative_income_questions_return_calculated_previews(client):
    user_id, _ = account(client)
    absolute = ask(client, user_id, 'What if I earn 2000 next month?')
    assert absolute.status_code == 200, absolute.text
    data = absolute.json()
    assert data['topic'] == 'scenario'
    assert data['source'] == 'current_picture'
    assert data['scenario']['event']['kind'] == 'income_decrease'
    assert data['scenario']['event']['amount'] == '3000.00'
    assert data['scenario']['before']['spending']['gross_cash_flow']['value'] == '2000.00'
    assert data['scenario']['after']['spending']['gross_cash_flow']['value'] == '-1000.00'
    assert data['before_priority'] and data['after_priority']
    assert data['before_priority'] != data['after_priority']
    assert 'not saved' in data['answer'].lower()
    assert any('planning date' in note.lower() and 'not moved' in note.lower()
               for note in data['scenario']['limitations'])

    relative = ask(client, user_id, 'What if my income falls by 1500?').json()
    assert relative['scenario']['event']['amount'] == '1500.00'
    assert relative['scenario']['after']['income']['expected_monthly']['value'] == '3500.00'
    rupee = ask(client, user_id, 'What if my income drops to ₹2,000?').json()
    assert rupee['scenario']['after']['income']['expected_monthly']['value'] == '2000.00'
    compact = ask(client, user_id, 'What if I earn ₹20k next month?').json()
    assert compact['scenario']['after']['income']['expected_monthly']['value'] == '20000.00'
    indian_grouping = ask(client, user_id, 'What if I earn ₹1,00,000 next month?').json()
    assert indian_grouping['scenario']['after']['income']['expected_monthly']['value'] == '100000.00'
    assert client.get(f'/users/{user_id}').json()['monthly_income'] == '5000.00'


def test_extra_one_time_money_is_not_added_to_recurring_income(client):
    user_id, _ = account(client)
    response = ask(client, user_id, 'What if I get ₹1500 extra?')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['topic'] == 'scenario'
    assert data['scenario']['event']['kind'] == 'one_time_income'
    assert data['scenario']['one_time_cash_inflow'] == '1500.00'
    assert data['scenario']['after']['income']['expected_monthly']['value'] == '5000.00'
    assert data['scenario']['illustrative_current_month_cash_after_event'] == '3500.00'
    assert data['before_priority'] == data['after_priority']
    assert 'one-time' in data['answer'].lower()
    future = ask(client, user_id, 'What if I get ₹1500 extra next month?').json()
    assert future['topic'] == 'scenario_input'
    assert 'current planning month' in future['answer'].lower()


def test_stopping_named_saved_subscription_uses_its_amount_without_saving(client):
    user_id, _ = account(client)
    details = client.put(f'/users/{user_id}/financial-details', json={
        'income_pattern': 'stable', 'guaranteed_monthly_income': None,
        'recurring_expenses': [{'name': 'Streaming', 'monthly_amount': '100', 'category': 'discretionary'}],
        'loans': [], 'planned_expenses': [],
    })
    assert details.status_code == 200, details.text
    response = ask(client, user_id, 'What if I stop Streaming?')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['scenario']['event']['kind'] == 'subscription_reduction'
    assert data['scenario']['event']['amount'] == '100.00'
    assert data['scenario']['after']['spending']['monthly_total']['value'] == '2900.00'
    assert data['scenario']['after']['spending']['gross_cash_flow']['value'] == '2100.00'
    assert client.get(f'/users/{user_id}/financial-details').json()['recurring_expenses'][0]['monthly_amount'] == '100.00'
    ambiguous = ask(client, user_id, 'What if I stop this subscription?').json()
    assert ambiguous['topic'] == 'scenario_input'
    assert ambiguous['scenario'] is None
    assert 'name' in ambiguous['answer'].lower()
    malformed = ask(client, user_id, 'What if I stop Streaming for ₹1,2?').json()
    assert malformed['topic'] == 'scenario_input'
    assert malformed['scenario'] is None


def test_missing_or_ambiguous_change_asks_for_details_instead_of_guessing(client):
    user_id, _ = account(client)
    missing = ask(client, user_id, 'What if my income falls?').json()
    assert missing['topic'] == 'scenario_input'
    assert missing['scenario'] is None
    assert 'amount' in missing['answer'].lower()
    no_subscription = ask(client, user_id, 'What if I stop my subscription?').json()
    assert no_subscription['topic'] == 'scenario_input'
    assert no_subscription['scenario'] is None
    impossible = ask(client, user_id, 'What if my income falls by 6000?').json()
    assert impossible['topic'] == 'scenario_input'
    assert impossible['scenario'] is None
    assert '5000' not in impossible['answer'] or 'saved' in impossible['answer'].lower()
    follow_up = ask(client, user_id, 'to 2000', history=[
        {'question': 'What if my income falls?', 'answer': missing['answer']},
    ]).json()
    assert follow_up['scenario']['after']['income']['expected_monthly']['value'] == '2000.00'
    recurring_or_once = ask(client, user_id, 'What if I get 1500 extra per month?').json()
    assert recurring_or_once['topic'] == 'scenario_input'
    assert 'one-time' in recurring_or_once['answer'].lower()
    malformed = ask(client, user_id, 'What if I get ₹1,2 extra?').json()
    assert malformed['topic'] == 'scenario_input'
    assert malformed['scenario'] is None


def test_conversational_preview_is_owned_and_does_not_use_the_language_model(client, monkeypatch):
    from app.services import current_chat

    first, _ = account(client, email='first-conversation@example.org')
    second, _ = account(client, email='second-conversation@example.org')
    monkeypatch.setattr(current_chat, '_provider_request',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('model must not calculate the event')))
    assert ask(client, first, 'What if I get 500 extra?').status_code == 404
    result = ask(client, second, 'What if I get 500 extra?')
    assert result.status_code == 200, result.text
    assert result.json()['scenario']['one_time_cash_inflow'] == '500.00'
