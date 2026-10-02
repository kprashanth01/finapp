"""The product comparison runs both selectors on one owned, current snapshot."""

from tests.test_advisory_api import client, create_profile


def test_approaches_keep_rule_plan_when_experimental_runtime_is_unavailable(client, monkeypatch):
    from app.rl import orchestration

    user, _ = create_profile(client)
    def unavailable():
        raise orchestration.ModelUnavailableError('model missing')
    monkeypatch.setattr(orchestration, 'cached_dqn_model', unavailable)

    path = f"/users/{user['id']}/advice-approaches"
    response = client.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['source'] == 'saved_profile'
    assert data['rule_based']['status'] == 'complete'
    assert data['rule_based']['first_action']['title']
    assert data['trained_rl']['status'] == 'unavailable'
    assert data['trained_rl']['first_action'] is None
    assert data['rule_based']['state_fingerprint'] == data['state_fingerprint']
    assert client.get(f"/users/{user['id']}/advisory-sessions").json()['items'] == []

    other, _ = create_profile(client, email='other-approaches@example.org')
    assert client.get(path).status_code == 404
    assert client.get(f"/users/{other['id']}/advice-approaches").status_code == 200


def test_approaches_withhold_experimental_plan_when_required_checks_are_missing(client, monkeypatch):
    from app.rl import orchestration

    user, _ = create_profile(client)
    class BudgetOnlyModel:
        def predict(self, _observation, deterministic=True):
            return 0, None
    monkeypatch.setattr(orchestration, 'cached_dqn_model', lambda: BudgetOnlyModel())

    data = client.get(f"/users/{user['id']}/advice-approaches").json()
    assert data['rule_based']['status'] == 'complete'
    assert data['trained_rl']['status'] == 'partial'
    assert data['trained_rl']['selected_agents'] == ['budget']
    assert 'emergency' in data['trained_rl']['missing_agents']
    assert data['trained_rl']['first_action'] is None
    assert data['trained_rl']['state_fingerprint'] == data['state_fingerprint']
    assert data['rule_based']['as_of_date'] == data['trained_rl']['as_of_date']


def test_approaches_show_a_complete_model_plan_when_all_checks_run(client, monkeypatch):
    from app.rl import orchestration

    user, _ = create_profile(client)
    class AllChecksModel:
        def predict(self, _observation, deterministic=True):
            return 62, None
    monkeypatch.setattr(orchestration, 'cached_dqn_model', lambda: AllChecksModel())

    data = client.get(f"/users/{user['id']}/advice-approaches").json()
    assert data['trained_rl']['status'] == 'complete'
    assert data['trained_rl']['first_action']['title']
    assert len(data['trained_rl']['selected_agents']) == 6
    assert data['trained_rl']['missing_agents'] == []
    assert data['trained_rl']['state_fingerprint'] == data['rule_based']['state_fingerprint']


def test_standard_comparison_matches_a_saved_run_on_the_same_detailed_inputs(client, monkeypatch):
    from app.advisory.state import PlanningState
    from app.rl import orchestration

    user, _ = create_profile(client)
    user_id = user['id']
    details = {
        'income_pattern': 'stable', 'guaranteed_monthly_income': None,
        'recurring_expenses': [{'name': 'Streaming', 'monthly_amount': '100', 'category': 'discretionary'}],
        'loans': [], 'planned_expenses': [],
    }
    assert client.put(f'/users/{user_id}/financial-details', json=details).status_code == 200
    monkeypatch.setattr(orchestration, 'cached_dqn_model',
                        lambda: (_ for _ in ()).throw(orchestration.ModelUnavailableError('missing')))

    comparison = client.get(f'/users/{user_id}/advice-approaches').json()
    saved = client.post(f'/users/{user_id}/advisory-sessions').json()['result']
    assert comparison['state_fingerprint'] == PlanningState.model_validate(saved['state']).fingerprint()
    assert comparison['rule_based']['first_action']['title'] == saved['advice']['summary']['title']
    assert comparison['rule_based']['selected_agents'] == [item['agent_id'] for item in saved['agent_results']]


def test_a_complete_plan_without_a_priority_does_not_invent_a_first_action():
    from app.services.advice_approaches import _project

    projected = _project({
        'plan_readiness': {'can_build_full_plan': True, 'missing_agents': []},
        'advice': {'summary': {'title': 'Your monthly plan is ready', 'text': 'Allocations are available.'},
                   'priority_actions': []},
        'as_of_date': '2026-10-03', 'state_fingerprint': 'a' * 64,
        'selected_agents': ['budget', 'emergency'],
    })
    assert projected.first_action is None
    assert projected.detail == 'Allocations are available.'
