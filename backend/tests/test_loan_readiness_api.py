"""A saved loan scenario updates against the account without claiming approval."""

from datetime import date

from tests.test_advisory_api import client, create_profile


def scenario(**overrides):
    return {'name': 'Work vehicle', 'loan_type': 'vehicle', 'lender_name': 'Example lender',
            'amount': '200000', 'annual_interest_rate_percent': '12', 'tenure_months': 24,
            'criteria': [], **overrides}


def test_saved_scenario_assessment_updates_and_records_a_change(client):
    user, profile = create_profile(client)
    user_id = user['id']
    path = f'/users/{user_id}/loan-readiness/scenarios'
    created = client.post(path, json=scenario())
    assert created.status_code == 201, created.text
    scenario_id = created.json()['id']
    assert client.get(path).json()[0]['id'] == scenario_id

    assessed = client.post(f'{path}/{scenario_id}/assess', json={})
    assert assessed.status_code == 200, assessed.text
    first = assessed.json()
    assert first['estimated_emi'] == '9414.69'
    assert first['emi_source'] == 'calculated'
    assert first['scenario_id'] == scenario_id
    assert first['evaluated_at']
    assert first['changes_since_previous'] == []
    assert 'not a lender policy' in first['requirements'][0]['source_label']

    profile['emergency_fund'] = '0'
    assert client.put(f'/users/{user_id}/financial-profile', json=profile).status_code == 200
    changed = client.post(f'{path}/{scenario_id}/assess', json={}).json()
    assert changed['reserve_coverage_months'] == '0.00'
    assert any('reserve' in item.lower() for item in changed['changes_since_previous'])
    assert changed['input_fingerprint'] != first['input_fingerprint']

    again = client.post(f'{path}/{scenario_id}/assess', json={}).json()
    assert again['input_fingerprint'] == changed['input_fingerprint']
    assert again['changes_since_previous'] == changed['changes_since_previous']

    profile['existing_debt'] = '5000'
    assert client.put(f'/users/{user_id}/financial-profile', json=profile).status_code == 200
    debt_change = client.post(f'{path}/{scenario_id}/assess', json={}).json()
    assert any('existing debt balance' in item.lower() for item in debt_change['changes_since_previous'])


def test_preview_and_chat_use_saved_assessment_without_mutation(client):
    user, profile = create_profile(client)
    user_id = user['id']
    path = f'/users/{user_id}/loan-readiness/scenarios'
    created = client.post(path, json=scenario())
    assert created.status_code == 201, created.text
    scenario_id = created.json()['id']
    preview = client.post(f'{path}/{scenario_id}/preview', json={'income_next_month': '12000'})
    assert preview.status_code == 200, preview.text
    assert preview.json()['after']['current_month']['income'] == '12000.00'
    assert preview.json()['after']['current_month']['remaining_before_savings'] < '0'
    assert client.get(f'/users/{user_id}').json()['monthly_income'] == user['monthly_income']

    chat = client.post(f'{path}/{scenario_id}/chat', json={'question': 'Can I afford this EMI?'})
    assert chat.status_code == 200, chat.text
    assert '9,414.69' in chat.json()['answer']
    assert chat.json()['assessment']['scenario_id'] == scenario_id
    assert chat.json()['evidence']
    current = client.post(f'/users/{user_id}/current-chat', json={'question': 'Am I ready for this loan?'})
    assert current.status_code == 200, current.text
    assert current.json()['topic'] == 'loan_readiness'
    assert '9,414.69' in current.json()['answer']


def test_scenario_is_owned_and_user_criteria_are_not_presented_as_verified(client):
    owner, _ = create_profile(client)
    path = f"/users/{owner['id']}/loan-readiness/scenarios"
    created = client.post(path, json=scenario(criteria=[{
        'kind': 'minimum_history_months', 'value': 6,
        'source_name': 'Offer sheet', 'source_url': 'https://example.org/offer',
    }]))
    assert created.status_code == 201, created.text
    scenario_id = created.json()['id']
    assessment = client.post(f'{path}/{scenario_id}/assess', json={}).json()
    criterion = next(item for item in assessment['requirements'] if item['key'] == 'minimum_history_months')
    assert criterion['status'] == 'NOT_MET'
    assert criterion['source_type'] == 'user_entered'
    assert 'unverified' in criterion['source_label']
    assert 'Offer sheet' in criterion['source_label']

    other, _ = create_profile(client, email='other-loan-readiness@example.org')
    assert client.get(path).status_code == 404
    assert client.post(f'{path}/{scenario_id}/assess', json={}).status_code == 404
    assert client.get(f"/users/{other['id']}/loan-readiness/scenarios/{scenario_id}").status_code == 404


def test_missing_rate_can_be_saved_and_explained(client):
    user, _ = create_profile(client)
    path = f"/users/{user['id']}/loan-readiness/scenarios"
    saved = client.post(path, json=scenario(annual_interest_rate_percent=None))
    assert saved.status_code == 201, saved.text
    result = client.post(f"{path}/{saved.json()['id']}/assess", json={}).json()
    assert result['estimated_emi'] is None
    assert any(item['key'] == 'repayment_capacity' and item['status'] == 'UNKNOWN'
               for item in result['requirements'])
    assert not any(item['source_type'] == 'user_entered' for item in result['requirements'])
