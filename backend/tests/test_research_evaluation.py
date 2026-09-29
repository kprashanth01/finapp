"""A fixed cohort must be shared by the three actual selector policies."""

import json

import pytest

from app.rl.evaluation import evaluate_cohort, read_evaluation_report
from app.rl.scenarios import generate_scenarios


class FixedModel:
    def predict(self, observation, deterministic=True):
        assert deterministic is True
        return 0, None


def test_evaluation_uses_identical_cases_and_repeatable_random_seeds():
    states = generate_scenarios(16, seed=8103)
    first = evaluate_cohort(states, FixedModel(), scenario_seed=8103, random_seeds=(7, 11))
    second = evaluate_cohort(states, FixedModel(), scenario_seed=8103, random_seeds=(7, 11))
    assert first['cohort']['fingerprints'] == second['cohort']['fingerprints']
    assert first['cohort']['case_count'] == 16
    assert set(first['methods']) == {'random', 'rule_based', 'rl'}
    assert first['methods']['random']['run_count'] == 2
    assert first['methods']['rule_based']['run_count'] == 1
    for name in first['methods']:
        for key, value in first['methods'][name]['metrics'].items():
            if key != 'mean_execution_ms':
                assert value == second['methods'][name]['metrics'][key]
    assert first['methods']['random']['runs'][0]['seed'] == 7
    assert first['methods']['random']['runs'][1]['seed'] == 11
    assert first['methods']['rl']['metrics']['mean_agent_calls'] == 1
    assert first['methods']['rl']['metrics']['full_plan_rate'] == 0
    assert first['methods']['rule_based']['metrics']['full_plan_rate'] == 1
    assert first['limitations']['recommendation_consistency'] == 'not measured'


def test_evaluation_report_rejects_stale_model_and_malformed_metrics(tmp_path):
    from app.rl.dqn_artifact import DEFAULT_ARTIFACT_DIR, verified_metadata

    report = evaluate_cohort(generate_scenarios(4, seed=8104), FixedModel(),
                             scenario_seed=8104, random_seeds=(7,))
    report['model_sha256'] = verified_metadata(DEFAULT_ARTIFACT_DIR)['artifact_sha256']
    path = tmp_path / 'evaluation_report.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    assert read_evaluation_report(path)['status'] == 'available'
    report['model_sha256'] = 'stale'
    path.write_text(json.dumps(report), encoding='utf-8')
    assert read_evaluation_report(path)['status'] == 'unavailable'
    report['model_sha256'] = verified_metadata(DEFAULT_ARTIFACT_DIR)['artifact_sha256']
    report['methods']['rl']['metrics']['mean_reward'] = 'unknown'
    path.write_text(json.dumps(report), encoding='utf-8')
    assert read_evaluation_report(path)['status'] == 'unavailable'


def test_evaluation_requires_distinct_random_seeds():
    with pytest.raises(ValueError, match='distinct'):
        evaluate_cohort(generate_scenarios(2, seed=1), FixedModel(),
                        scenario_seed=1, random_seeds=(7, 7))


def test_committed_report_reproduces_measured_selection_metrics():
    pytest.importorskip('stable_baselines3')
    from app.rl.dqn_artifact import load_dqn_artifact

    saved = read_evaluation_report()
    assert saved['status'] == 'available'
    report = saved['report']
    measured = evaluate_cohort(
        generate_scenarios(report['cohort']['case_count'], seed=report['cohort']['seed']),
        load_dqn_artifact(), scenario_seed=report['cohort']['seed'],
        random_seeds=tuple(report['random_seeds']),
    )
    assert measured['cohort']['sha256'] == report['cohort']['sha256']
    assert measured['paired_rl_vs_rule'] == report['paired_rl_vs_rule']
    for name in ('random', 'rule_based', 'rl'):
        for key, value in measured['methods'][name]['metrics'].items():
            if key != 'mean_execution_ms':
                assert value == report['methods'][name]['metrics'][key]
        for segment, metrics in measured['methods'][name]['segments'].items():
            assert metrics == report['methods'][name]['segments'][segment]
