"""Seeded, persona-stratified train/test assignment for synthetic users."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import random
from typing import Sequence

from app.rl.population import (
    DEFAULT_SEED as DEFAULT_POPULATION_SEED, PERSONAS, POPULATION_VERSION,
    SyntheticProfile, generate_population,
)


SPLIT_VERSION = "synthetic-user-split-v1"
DEFAULT_SPLIT_SEED = 20261002
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "user-splits-v1.jsonl"


def assign_user_splits(profiles: Sequence[SyntheticProfile], *, seed: int = DEFAULT_SPLIT_SEED
                       ) -> list[SyntheticProfile]:
    """Return copies with 80/20 membership sampled once per user within each persona."""
    ids = [profile.synthetic_id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError("synthetic_id must be unique before splitting")
    if any(profile.dataset_split is not None for profile in profiles):
        raise ValueError("input profiles must have unassigned dataset_split values")
    population_seeds = {profile.generation_seed for profile in profiles}
    if len(population_seeds) != 1:
        raise ValueError("profiles must belong to one generated population")
    population_seed = next(iter(population_seeds))
    groups = {spec.name: [] for spec in PERSONAS}
    for profile in profiles:
        if profile.persona not in groups:
            raise ValueError("unknown synthetic persona")
        groups[profile.persona].append(profile.synthetic_id)

    train_ids = set()
    for persona, group_ids in groups.items():
        group_ids.sort()
        identity = f"{population_seed}:{seed}:{persona}".encode("ascii")
        rng = random.Random(int.from_bytes(sha256(identity).digest(), "big"))
        rng.shuffle(group_ids)
        train_ids.update(group_ids[:len(group_ids) * 4 // 5])
    return [replace(profile, dataset_split="train" if profile.synthetic_id in train_ids else "test")
            for profile in profiles]


def export_split_manifest(path: Path, *, population_seed: int = DEFAULT_POPULATION_SEED,
                          split_seed: int = DEFAULT_SPLIT_SEED) -> dict:
    """Write one anonymous split assignment per synthetic user plus a digest summary."""
    profiles = assign_user_splits(generate_population(seed=population_seed), seed=split_seed)
    rows = ({"synthetic_id": profile.synthetic_id, "persona": profile.persona,
             "dataset_split": profile.dataset_split}
            for profile in sorted(profiles, key=lambda row: row.synthetic_id))
    payload = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    counts = Counter((profile.persona, profile.dataset_split) for profile in profiles)
    report = {
        "split_version": SPLIT_VERSION,
        "population_version": POPULATION_VERSION,
        "population_seed": population_seed,
        "split_seed": split_seed,
        "split_unit": "synthetic user; all months inherit the user's assignment",
        "train_fraction_per_persona": "0.80",
        "total_users": len(profiles),
        "train_users": sum(profile.dataset_split == "train" for profile in profiles),
        "test_users": sum(profile.dataset_split == "test" for profile in profiles),
        "sha256": sha256(payload).hexdigest(),
        "personas": {spec.name: {"train": counts[(spec.name, "train")],
                                 "test": counts[(spec.name, "test")]}
                     for spec in PERSONAS},
    }
    path.with_suffix(".summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a user-level synthetic train/test split manifest.")
    parser.add_argument("--population-seed", type=int, default=DEFAULT_POPULATION_SEED)
    parser.add_argument("--split-seed", type=int, default=DEFAULT_SPLIT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(export_split_manifest(args.output, population_seed=args.population_seed,
                                           split_seed=args.split_seed), indent=2))


if __name__ == "__main__":
    main()
