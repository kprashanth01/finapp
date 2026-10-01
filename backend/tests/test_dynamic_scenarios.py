"""Monthly DQN datasets must split whole synthetic users, never monthly rows."""

import pytest

from app.rl.dynamic_scenarios import build_dynamic_episode_splits


def test_persona_stratified_episode_splits_are_disjoint_and_repeatable():
    kwargs = dict(training_users=20, validation_users=8, test_users=8, months=3,
                  population_seed=91, split_seed=92, selection_seed=93,
                  trajectory_seed=94, shock_probability=0.2)
    first = build_dynamic_episode_splits(**kwargs)
    second = build_dynamic_episode_splits(**kwargs)
    groups = (first.training, first.validation, first.test)
    assert [len(group) for group in groups] == [20, 8, 8]
    ids = [set(episode.profile.synthetic_id for episode in group) for group in groups]
    assert all(a.isdisjoint(b) for index, a in enumerate(ids) for b in ids[index + 1:])
    assert all(episode.profile.dataset_split == "train" for group in groups[:2] for episode in group)
    assert all(episode.profile.dataset_split == "test" for episode in groups[2])
    assert all(len(episode.months) == 3 and
               all(month.synthetic_id == episode.profile.synthetic_id for month in episode.months)
               for group in groups for episode in group)
    assert first.summary == second.summary
    assert [[episode.months[0].monthly_income for episode in group] for group in groups] == [
        [episode.months[0].monthly_income for episode in group]
        for group in (second.training, second.validation, second.test)
    ]
    for role in ("training", "validation", "test"):
        assert set(first.summary["persona_counts"][role]) == {
            "gig_worker", "salaried_with_loan", "student_fresh_graduate", "near_retiree",
        }
        assert sum(first.summary["persona_counts"][role].values()) == kwargs[f"{role}_users"]


def test_split_builder_rejects_overlapping_or_impossible_requests():
    with pytest.raises(ValueError, match="positive"):
        build_dynamic_episode_splits(training_users=0, validation_users=2, test_users=2)
    with pytest.raises(ValueError, match="available"):
        build_dynamic_episode_splits(training_users=9600, validation_users=1, test_users=2)
