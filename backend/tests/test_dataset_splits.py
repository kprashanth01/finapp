"""Train/test membership belongs to synthetic users, never individual months."""

from collections import Counter
from hashlib import sha256
import json

import pytest

from app.rl.population import generate_population
from app.rl.splits import assign_user_splits, export_split_manifest
from app.rl.trajectories import ShockConfig, export_trajectories


EXPECTED = {
    "gig_worker": {"train": 2880, "test": 720},
    "salaried_with_loan": {"train": 3360, "test": 840},
    "student_fresh_graduate": {"train": 1920, "test": 480},
    "near_retiree": {"train": 1440, "test": 360},
}


def test_stratified_user_split_has_exact_counts_and_no_overlap():
    originals = generate_population(seed=91)
    assigned = assign_user_splits(originals, seed=17)
    counts = Counter((profile.persona, profile.dataset_split) for profile in assigned)
    assert len(assigned) == 12_000
    assert all(profile.dataset_split is None for profile in originals)
    assert {profile.synthetic_id for profile in assigned} == set(range(1, 12_001))
    assert sum(profile.dataset_split == "train" for profile in assigned) == 9600
    assert sum(profile.dataset_split == "test" for profile in assigned) == 2400
    for persona, expected in EXPECTED.items():
        assert counts[(persona, "train")] == expected["train"]
        assert counts[(persona, "test")] == expected["test"]


def test_split_is_seeded_and_independent_of_input_order():
    originals = generate_population(seed=91)
    first = assign_user_splits(originals, seed=23)
    reversed_input = assign_user_splits(list(reversed(originals)), seed=23)
    changed = assign_user_splits(originals, seed=24)
    lookup = lambda rows: {profile.synthetic_id: profile.dataset_split for profile in rows}
    assert lookup(first) == lookup(reversed_input)
    assert lookup(first) != lookup(changed)


def test_manifest_records_all_users_and_a_matching_digest(tmp_path):
    path = tmp_path / "splits.jsonl"
    report = export_split_manifest(path, population_seed=91, split_seed=23)
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode().splitlines()]
    assert report["split_version"] == "synthetic-user-split-v1"
    assert report["total_users"] == 12_000
    assert report["train_users"] == 9600 and report["test_users"] == 2400
    assert report["personas"] == EXPECTED
    assert report["sha256"] == sha256(payload).hexdigest()
    assert len(rows) == len({row["synthetic_id"] for row in rows}) == 12_000
    assert json.loads(path.with_suffix(".summary.json").read_text()) == report
    assert export_split_manifest(path, population_seed=91, split_seed=23) == report
    assert path.read_bytes() == payload


def test_train_and_test_trajectory_files_have_whole_disjoint_users(tmp_path):
    train_path = tmp_path / "train.jsonl"
    test_path = tmp_path / "test.jsonl"
    train = export_trajectories(train_path, population_seed=91, split_seed=23,
                                selected_split="train", months=2)
    test = export_trajectories(test_path, population_seed=91, split_seed=23,
                               selected_split="test", months=2)
    train_rows = [json.loads(line) for line in train_path.read_text().splitlines()]
    test_rows = [json.loads(line) for line in test_path.read_text().splitlines()]
    train_ids = {row["synthetic_id"] for row in train_rows}
    test_ids = {row["synthetic_id"] for row in test_rows}
    assert train_ids.isdisjoint(test_ids)
    assert len(train_ids) == 9600 and len(test_ids) == 2400
    assert len(train_rows) == train["monthly_state_count"] == 19_200
    assert len(test_rows) == test["monthly_state_count"] == 4_800
    assert all(row["dataset_split"] == "train" for row in train_rows)
    assert all(row["dataset_split"] == "test" for row in test_rows)
    assert set(Counter(row["synthetic_id"] for row in train_rows).values()) == {2}
    assert set(Counter(row["synthetic_id"] for row in test_rows).values()) == {2}
    assert train["dataset_version"] == test["dataset_version"] == "synthetic-trajectories-v3"
    assert train["split_seed"] == test["split_seed"] == 23


def test_filter_requires_an_assigned_split(tmp_path):
    with pytest.raises(ValueError, match="split_seed"):
        export_trajectories(tmp_path / "invalid.jsonl", selected_split="train")


def test_shocked_months_inherit_their_users_assignment(tmp_path):
    profile = next(p for p in assign_user_splits(generate_population(seed=91), seed=23)
                   if p.dataset_split == "train")
    path = tmp_path / "shocked.jsonl"
    report = export_trajectories(
        path, population_seed=91, split_seed=23, synthetic_id=profile.synthetic_id,
        months=3, shock_config=ShockConfig(probability=1, event_types=("low_income",)),
    )
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert report["dataset_version"] == "synthetic-trajectories-v4"
    assert {row["dataset_split"] for row in rows} == {"train"}
    assert {row["event_type"] for row in rows} == {"low_income"}
    assert [row["month_index"] for row in rows] == [1, 2, 3]
