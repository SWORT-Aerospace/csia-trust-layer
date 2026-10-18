"""The independent-validation seed partitions.

The prior phase's blocks were hand-written. These are derived from a committed
domain string, so the manifest hash pins the seeds and a quiet reroll is
impossible without changing the hash.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from csia_independent_validation import partitions as pt


def test_manifest_hash_is_pinned():
    assert pt.manifest_hash() == (
        "b293e30f30a767c13b29d1abfa9ac4c3bdc49580f3224d037252513801786731")


def test_partitions_are_disjoint():
    pt.assert_disjoint()
    everything = [s for values in pt.PARTITIONS.values() for s in values]
    assert len(everything) == len(set(everything))
    assert len(everything) == sum(pt.SIZES.values())


def test_sizes_match_the_manifest():
    for phase, size in pt.SIZES.items():
        assert len(pt.PARTITIONS[phase]) == size


def test_seeds_are_reproducible_from_the_domain_string():
    """Recompute the first seed of each partition by hand from the domain."""
    for phase in pt.SIZES:
        digest = hashlib.sha256(f"{pt.DOMAIN}|{phase}|0".encode()).digest()
        expected = int.from_bytes(digest[:4], "big") & ((1 << 31) - 1)
        # Index 0 survives unless it collided with an earlier partition.
        assert expected in pt.PARTITIONS[phase] or expected in {
            s for other, values in pt.PARTITIONS.items()
            for s in values if other != phase}


def test_the_final_partition_is_sealed():
    assert pt.SEALED == ("final",)
    with pytest.raises(PermissionError):
        pt.seeds("final")


def test_opening_the_seal_requires_spelling_it_out():
    opened = pt.seeds("final", i_am_opening_the_sealed_partition=True)
    assert len(opened) == pt.SIZES["final"]


def test_unsealed_partitions_hand_out_freely():
    for phase in ("development", "calibration", "validation"):
        assert len(pt.seeds(phase)) == pt.SIZES[phase]


def test_unknown_partition_is_an_error():
    with pytest.raises(KeyError):
        pt.seeds("locked")


def test_manifest_hash_changes_if_the_domain_changes(monkeypatch):
    """The property the whole scheme rests on."""
    before = pt.manifest_hash()
    manifest = pt.manifest()
    manifest["domain"] = manifest["domain"] + "x"
    after = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    assert before != after


def test_no_iv_seed_collides_with_a_prior_phase_seed():
    """Development must not accidentally reuse a previously locked seed."""
    from csia_active_evidence import partitions as old
    prior = {s for values in old.PARTITIONS.values() for s in values}
    ours = {s for values in pt.PARTITIONS.values() for s in values}
    assert not (prior & ours)
