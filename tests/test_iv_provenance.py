"""The independent-validation phase's provenance gate, as executable tests.

Section 0 of the new preregistration makes four corrections to how the prior
locked result was written down. Prose corrections rot. These tests recompute
each one from the immutable raw artifact, so that if someone later "tidies" a
number the suite goes red.

They also pin the two things that must never move: the prior partition manifest
(recorded inside the locked artifact) and the frozen-core digest.
"""
from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import statistics

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCKED = (ROOT / "research/active_evidence/realized_current/results"
          / "RCEC_LOCKED_CAMPAIGN.json")
PROVENANCE = (ROOT / "research/active_evidence/independent_validation"
              / "BASE_PROVENANCE.json")


@pytest.fixture(scope="module")
def locked() -> dict:
    return json.loads(LOCKED.read_text())


@pytest.fixture(scope="module")
def rows(locked) -> list:
    return locked["rows"]


def _margin_positive(row) -> bool:
    return row["M_R"] is not None and row["M_R"] > 0


def _certified_and_positive(row) -> bool:
    return row["state"] == "CERTIFIED_IN_MODEL" and _margin_positive(row)


def _frontier(rows, plant, drift, arm, predicate):
    for magnitude in sorted({r["r0_delta"] for r in rows}):
        sub = [r for r in rows if r["plant"] == plant
               and r["drift_state"] == drift and r["arm"] == arm
               and r["r0_delta"] == magnitude]
        if sub and sum(predicate(r) for r in sub) / len(sub) >= 0.90:
            return magnitude
    return None


# --- the raw artifact itself --------------------------------------------

def test_locked_artifact_is_the_one_that_was_sealed(locked):
    assert locked["n_rows"] == 8640
    assert len(locked["rows"]) == 8640
    assert locked["locked_partition"] == "amended_locked"
    assert locked["partition_manifest_sha256"] == (
        "e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2")


def test_prior_partition_manifest_is_untouched():
    from csia_active_evidence import partitions as old
    assert old.manifest_hash() == (
        "e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2")


def test_frozen_core_digest_and_its_derivation():
    baseline = json.loads((ROOT / "docs/v1/FROZEN_BASELINE.json").read_text())
    files = baseline["files"]
    assert len(files) == 12
    for rel, expected in files.items():
        want = expected if isinstance(expected, str) else expected["sha256"]
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, rel
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()).hexdigest()
    assert digest == (
        "b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8")


# --- section 0.1: the frontier predicate ---------------------------------

PUBLISHED_FRONTIER = {
    "P0_passive": None, "P1_palindromic": 0.02, "P2_compensated": 0.006,
    "P3_shaped": 0.01, "P4_feedback": 0.01, "P5_random_safe": 0.02,
    "P6_mission": None, "P7_oracle": 0.04,
}

#: The same arms scored by the predicate a reader would assume from the words
#: "resolution frontier": the certificate actually issued.
CERTIFIED_FRONTIER = {
    "P0_passive": None, "P1_palindromic": 0.04, "P2_compensated": 0.01,
    "P3_shaped": 0.02, "P4_feedback": 0.02, "P5_random_safe": 0.04,
    "P6_mission": None, "P7_oracle": None,
}


@pytest.mark.parametrize("arm", sorted(PUBLISHED_FRONTIER))
def test_published_frontier_reproduces_under_margin_positive(rows, arm):
    assert _frontier(rows, "one_rc", "nominal", arm,
                     _margin_positive) == PUBLISHED_FRONTIER[arm]


@pytest.mark.parametrize("arm", sorted(CERTIFIED_FRONTIER))
def test_frontier_is_strictly_worse_when_certification_is_required(rows, arm):
    assert _frontier(rows, "one_rc", "nominal", arm,
                     _certified_and_positive) == CERTIFIED_FRONTIER[arm]


def test_the_old_p7_never_certifies_anywhere_on_the_grid(rows):
    """It was called an oracle. It never issued a single certificate."""
    assert not any(r["state"] == "CERTIFIED_IN_MODEL"
                   for r in rows if r["arm"] == "P7_oracle")


# --- section 0.2: the false-certificate check could not fail -------------

def test_certify_only_returns_certified_when_the_margin_is_positive():
    """The premise that makes the old false-certificate count vacuous."""
    import inspect

    from csia_active_evidence import rcec
    source = inspect.getsource(rcec.certify)
    # The certified return is guarded by the same comparison the old check
    # used, with the sense reversed, so the two can never disagree.
    assert "if achieved >= margin:" in source
    assert source.rstrip().endswith("budget=budget.to_dict())")


def test_no_locked_row_can_be_certified_with_a_negative_margin(rows):
    """Empty by construction, which is exactly the complaint."""
    bad = [r for r in rows
           if r["state"] == "CERTIFIED_IN_MODEL"
           and r["M_R"] is not None and r["M_R"] < 0]
    assert bad == []


def test_the_locked_campaign_never_scored_against_plant_truth(rows):
    """No row carries a true resistance, so no row could have been scored."""
    truth_like = {"r0_true", "R_0_true", "true_r0", "r_true", "ground_truth"}
    assert not (truth_like & set(rows[0]))


# --- section 0.3: the paired denominators are per-plant ------------------

def _paired(rows, a, b, plant=None):
    index = collections.defaultdict(dict)
    for r in rows:
        index[r["arm"]][(r["plant"], r["drift_state"],
                         r["r0_delta"], r["seed"])] = r
    diffs = []
    for key, ra in index[a].items():
        if plant is not None and key[0] != plant:
            continue
        rb = index[b].get(key)
        if rb is None or ra["M_R"] is None or rb["M_R"] is None:
            continue
        diffs.append(ra["M_R"] - rb["M_R"])
    return diffs


def test_published_paired_wins_are_the_one_rc_slice(rows):
    versus_mission = _paired(rows, "P2_compensated", "P6_mission", "one_rc")
    versus_naive = _paired(rows, "P2_compensated", "P1_palindromic", "one_rc")
    assert len(versus_mission) == 140
    assert all(d > 0 for d in versus_mission)
    assert statistics.median(versus_mission) == pytest.approx(0.0391840889,
                                                              abs=1e-9)
    assert len(versus_naive) == 240
    assert all(d > 0 for d in versus_naive)
    assert statistics.median(versus_naive) == pytest.approx(0.0060570044,
                                                            abs=1e-9)


def test_campaign_wide_denominators_are_larger_and_still_unanimous(rows):
    versus_mission = _paired(rows, "P2_compensated", "P6_mission")
    versus_naive = _paired(rows, "P2_compensated", "P1_palindromic")
    assert len(versus_mission) == 420
    assert len(versus_naive) == 726
    assert all(d > 0 for d in versus_mission + versus_naive)


def test_energy_cost_of_the_winning_arm(rows):
    def energy(arm):
        return sorted({round(r["energy_as"], 5)
                       for r in rows if r["arm"] == arm})
    assert energy("P2_compensated") == [45.85341]
    assert energy("P1_palindromic") == [40.74283]
    assert energy("P3_shaped") == [20.37016]


# --- section 0.4: the margin cannot see the plant ------------------------

def test_certificate_margin_is_bit_identical_across_plants(rows):
    cells = collections.defaultdict(dict)
    for r in rows:
        cells[(r["arm"], r["drift_state"],
               r["r0_delta"], r["seed"])][r["plant"]] = r["M_R"]
    full = [c for c in cells.values()
            if len(c) == 3 and all(v is not None for v in c.values())]
    assert len(full) == 2012
    assert all(len(set(c.values())) == 1 for c in full)


# --- section 0.5: everything that verified unchanged ---------------------

def test_certificate_confusion_counts(locked, rows):
    expected = {"MODEL_MISMATCH_LIMITED": 4723, "INSUFFICIENT_EXCITATION": 1440,
                "CERTIFIED_IN_MODEL": 1320, "UNKNOWN_OR_MODEL_MISMATCH": 620,
                "DRIFT_COUPLED": 537}
    assert locked["certificate_confusion"] == expected
    assert dict(collections.Counter(r["state"] for r in rows)) == expected
    assert sum(expected.values()) == 8640


def test_execution_and_unknown_fault_ablations(locked):
    assert locked["ablations"]["execution"] == {
        "aborted": "ABORTED_INCOMPLETE",
        "clipped": "CLIPPED_CERTIFICATE_INVALID",
        "full": "CERTIFIED_IN_MODEL"}
    routing = locked["ablations"]["unmodelled_fault_routing"]
    assert routing["0.4"] == "UNKNOWN_OR_MODEL_MISMATCH"
    assert routing["0.1"] == "CERTIFIED_IN_MODEL"


def test_only_the_exact_lag_certifies_and_underestimate_flips_the_sign(locked):
    lag = locked["ablations"]["lag_error"]
    certified = [k for k, v in lag.items()
                 if v["state"] == "CERTIFIED_IN_MODEL"]
    assert certified == ["1.0"]
    assert lag["0.25"]["lever_sign"] == 1
    assert all(lag[k]["lever_sign"] == -1 for k in ("0.5", "1.0", "2.0", "4.0"))


def test_elevated_drift_collapses_p2_and_p3_but_not_p4(rows):
    for arm, absent, elevated in (("P2_compensated", 0.006, None),
                                  ("P3_shaped", 0.01, None),
                                  ("P4_feedback", 0.01, 0.01)):
        assert _frontier(rows, "one_rc", "absent", arm,
                         _margin_positive) == absent
        assert _frontier(rows, "one_rc", "elevated", arm,
                         _margin_positive) == elevated


# --- the provenance artifact agrees with all of the above ----------------

def test_provenance_artifact_is_current(rows):
    doc = json.loads(PROVENANCE.read_text())
    assert doc["frozen_core"]["matches_claim"] is True
    assert doc["frozen_core"]["per_file_mismatches"] == []
    assert doc["partitions"]["agrees"] is True
    assert all(doc["git"]["ancestors_verified"].values())
    assert doc["locked_campaign"]["n_rows_recounted"] == 8640
    assert (doc["recomputed"]["plant_margin_identity"]["bit_identical"]
            == 2012)
