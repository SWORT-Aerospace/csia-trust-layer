"""Phase 4 — the ANALYSIS PIPELINE, end to end.

WHY THIS FILE EXISTS SEPARATELY FROM `test_phase4_detectors.py`
----------------------------------------------------------------
`test_phase4_detectors.py` tests the evaluator's pieces. Five Phase-3.2
mutants survived precisely because the pieces were tested and the assembled
`build()` never was, and FL-032 is the record of that gap. So this file runs
the pipeline whole: on a small fixture where the answer is known by hand, and
on the real committed artifacts, where it must reproduce the sealed result
byte for byte.

THE CANARIES ARE SYNTHETIC ON PURPOSE
--------------------------------------
Some properties cannot be tested on the real data. Every operating point in
the Phase-4 locked run selects cleanly at the primary target, so on THIS
dataset selecting on the locked partition instead of development happens to
give the same answer -- which means the real data cannot tell a correct
selection rule from a broken one. A canary is therefore built in which the
choice DECIDES the verdict, and the test is verified in both directions: it
must fail under the corresponding mutant and pass unmutated.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P4 = ROOT / "research" / "phase4"
sys.path.insert(0, str(P4))

import campaign4 as c4                                    # noqa: E402
import evaluate4 as ev4                                   # noqa: E402
import replay_check4 as rc4                               # noqa: E402

DEV = P4 / "results" / "PHASE4_RUNS_DEVELOPMENT.json"
LOCKED = P4 / "results" / "PHASE4_RUNS_LOCKED.json"
SEALED = P4 / "results" / "PHASE4_RESULTS_LOCKED.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ======================================================== FIXTURE CONSTRUCTION

def _alarm(first=None, after_settle=None, after_onset=None):
    return {"first": first, "after_settle": after_settle,
            "after_onset": after_onset}


def _fixture(*, grids=None, gains=(3.0,), onsets=(30.0,), seeds=(1, 2, 3, 4)):
    """A complete, well-formed campaign document over a tiny grid.

    Every seed carries the full `nominal + gain x onset` cross, so the intake
    classification has nothing to report and any classification a test sees
    is one that test put there.
    """
    grids = grids or {"CSIA": [0.9, 0.5], "CUSUM": [200.0, 5.0],
                      "BINST": [0.1, 0.01]}
    runs = []
    for seed in seeds:
        cells = [(None, None)] + [(g, o) for g in gains for o in onsets]
        for gain, onset in cells:
            alarms = {}
            for det, thrs in grids.items():
                alarms[det] = {repr(t): _alarm() for t in thrs}
            runs.append({"seed": seed, "gain": gain, "onset_s": onset,
                         "nominal": gain is None, "ticks": 1500,
                         "alarms": alarms, "cusum_max": 0.0,
                         "trust_min": 1.0, "active_ticks": 1500,
                         "ns_total": 1000})
    return {"schema": "csia.phase4.detector_runs/1", "partition": "fixture",
            "runs": runs, "seeds": list(seeds), "settle_s": 10.0,
            "horizon_s": 60.0, "grids": grids,
            "environment_specific_fields": ["runs[].ns_total"],
            "fault": {"gain_grid": list(gains), "onset_grid": list(onsets)}}


def _set(doc, det, thr, *, nominal, value):
    """Write one alarm record into every run of the requested kind."""
    for r in doc["runs"]:
        if bool(r["nominal"]) is bool(nominal):
            r["alarms"][det][repr(thr)] = value


# ================================================================ END TO END

def test_build_runs_end_to_end_on_a_fixture():
    dev = _fixture()
    locked = _fixture(seeds=(11, 12, 13, 14))
    # One detector detects everything, one second after onset, no false alarms.
    _set(dev, "CSIA", 0.9, nominal=False,
         value=_alarm(31.0, 31.0, 31.0))
    _set(locked, "CSIA", 0.9, nominal=False,
         value=_alarm(31.0, 31.0, 31.0))
    out = ev4.build(dev, locked)

    assert out["schema"] == "csia.phase4.detector_results/1"
    assert out["pooled_with_consequence_phases"] is False
    assert out["intake"]["development"]["all_seeds_complete"] is True
    assert out["intake"]["locked"]["all_seeds_complete"] is True
    row = out["operating_points"]["0.00|CSIA"]
    assert row["status"] == "SELECTED" and row["threshold"] == 0.9
    assert row["miss_rate"] == 0.0 and row["median_delay_s"] == 1.0
    # Every declared grid point is reported, not only the matched ones.
    assert len(out["full_grid_locked"]) == 6
    assert set(row["by_gain"]) == {"3.0"} and set(row["by_onset"]) == {"30.0"}


def test_build_reproduces_the_sealed_result_from_the_committed_runs():
    """The real pipeline, on the real artifacts, byte for byte.

    This is the test whose absence let five Phase-3.2 mutants live.
    """
    rebuilt = ev4.build(_load(DEV), _load(LOCKED))
    text = json.dumps(rebuilt, indent=1, sort_keys=True) + "\n"
    assert text == SEALED.read_text(encoding="utf-8")


def test_the_sealed_result_is_pinned_by_hash():
    digest = hashlib.sha256(SEALED.read_bytes()).hexdigest()
    assert digest == _SEALED_SHA256


def test_the_locked_runs_are_pinned_by_hash():
    assert hashlib.sha256(LOCKED.read_bytes()).hexdigest() == _LOCKED_SHA256


def test_reordering_the_runs_changes_no_reported_number():
    """Order is not an input, asserted on the real artifact and not in prose.

    Compared against the SEALED file rather than against a second `build()`
    of the unshuffled runs. That is one build instead of two, and it is the
    stronger claim: the shuffled input must reproduce the committed artifact,
    not merely agree with a sibling call that could be wrong in the same way.

    This test is how FL-037 was found -- the bootstrap resampled by index, so
    the reported interval depended on the order the runs sat in the file.
    """
    dev, locked = _load(DEV), _load(LOCKED)
    shuffled = copy.deepcopy(locked)
    random.Random(4242).shuffle(shuffled["runs"])
    assert shuffled["runs"] != locked["runs"]
    rebuilt = ev4.build(dev, shuffled)
    text = json.dumps(rebuilt, indent=1, sort_keys=True) + "\n"
    assert text == SEALED.read_text(encoding="utf-8")


# ============================================== REFUSAL AND CLASSIFICATION

@pytest.mark.parametrize("key", ev4.REQUIRED_KEYS)
def test_a_document_missing_a_required_key_is_refused(key):
    doc = _fixture()
    del doc[key]
    with pytest.raises(ev4.DocumentError, match=key):
        ev4.validate(doc)


def test_a_nominal_run_that_carries_a_fault_is_refused():
    doc = _fixture()
    doc["runs"][0]["gain"] = 3.0
    with pytest.raises(ev4.DocumentError, match="flagged nominal"):
        ev4.validate(doc)


def test_a_faulted_run_without_an_onset_is_refused():
    doc = _fixture()
    doc["runs"][1]["onset_s"] = None
    with pytest.raises(ev4.DocumentError, match="has no onset"):
        ev4.validate(doc)


def test_a_gain_outside_the_declared_grid_is_refused():
    doc = _fixture()
    doc["runs"][1]["gain"] = 99.0
    with pytest.raises(ev4.DocumentError, match="not in the declared grid"):
        ev4.validate(doc)


def test_an_onset_outside_the_declared_grid_is_refused():
    doc = _fixture()
    doc["runs"][1]["onset_s"] = 99.0
    with pytest.raises(ev4.DocumentError, match="not in the.*declared grid"):
        ev4.validate(doc)


def test_a_missing_alarm_time_is_refused():
    doc = _fixture()
    del doc["runs"][0]["alarms"]["CSIA"]["0.9"]["after_settle"]
    with pytest.raises(ev4.DocumentError, match="after_settle"):
        ev4.validate(doc)


def test_a_missing_detector_is_refused():
    doc = _fixture()
    del doc["runs"][0]["alarms"]["CUSUM"]
    with pytest.raises(ev4.DocumentError, match="no CUSUM alarms"):
        ev4.validate(doc)


def test_an_incomplete_seed_is_classified_and_named_not_silently_dropped():
    doc = _fixture()
    doc["runs"] = [r for r in doc["runs"]
                   if not (r["seed"] == 2 and r["gain"] == 3.0)]
    intake = ev4.validate(doc)
    assert intake["all_seeds_complete"] is False
    assert intake["incomplete_seeds"] == [
        {"seed": 2, "missing_cells": [(3.0, 30.0)]}]


def test_a_declared_cell_with_no_runs_at_all_is_reported():
    doc = _fixture()
    doc["runs"] = [r for r in doc["runs"] if r["nominal"]]
    intake = ev4.validate(doc)
    assert intake["empty_declared_cells"] == [[3.0, 30.0]]


# ================================================== CHERRY-PICK CANARIES
#
# Each canary is a dataset in which the property under test DECIDES the
# answer. The real Phase-4 data cannot do this: every matched point selects
# cleanly there, so the real data would pass whether or not the rule is
# correct.

#: Twenty seeds, so one false alarm is a rate of 0.05 and lands strictly
#: between the primary target (0.00) and the loosest secondary one (0.10).
#: With four seeds the coarsest possible non-zero rate is 0.25 and no
#: fixture can separate the targets at all.
CANARY_DEV_SEEDS = tuple(range(1, 21))
CANARY_LOCKED_SEEDS = tuple(range(101, 121))


def _canary_pair():
    """Development and locked partitions that disagree about CUSUM.

    On DEVELOPMENT, `h = 200` is clean and `h = 5` raises one false alarm in
    twenty nominal runs (0.05), so the zero-false-alarm rule must select 200
    and must report a 2.0 s delay. On LOCKED the false alarm is absent, so a
    rule that selected on the LOCKED partition would pick the more sensitive
    `h = 5` and report 0.1 s. The two answers are not close and neither is a
    rounding artefact.
    """
    dev = _fixture(seeds=CANARY_DEV_SEEDS)
    locked = _fixture(seeds=CANARY_LOCKED_SEEDS)
    for doc in (dev, locked):
        _set(doc, "CUSUM", 5.0, nominal=False, value=_alarm(30.1, 30.1, 30.1))
        _set(doc, "CUSUM", 200.0, nominal=False, value=_alarm(32.0, 32.0, 32.0))
    one = next(r for r in dev["runs"] if r["nominal"])
    one["alarms"]["CUSUM"]["5.0"] = _alarm(11.0, 11.0, None)
    return dev, locked


def test_thresholds_selected_on_locked_instead_of_development_change_the_verdict():
    dev, locked = _canary_pair()
    row = ev4.build(dev, locked)["operating_points"]["0.00|CUSUM"]
    assert row["threshold"] == 200.0, "selection must come from development"
    assert row["median_delay_s"] == 2.0
    # And the canary is a real canary: selecting on locked gives the other
    # answer, so this test can distinguish the two rules.
    wrong = ev4.match_operating_points(locked)["0.00|CUSUM"]
    assert wrong["threshold"] == 5.0


def test_the_primary_target_is_the_zero_false_alarm_point():
    """At 0.10 the canary's `h = 5` becomes eligible and the answer flips."""
    dev, locked = _canary_pair()
    out = ev4.build(dev, locked)
    assert out["primary_target_far"] == 0.00
    assert out["operating_points"]["0.00|CUSUM"]["threshold"] == 200.0
    assert out["operating_points"]["0.10|CUSUM"]["threshold"] == 5.0


def test_a_threshold_above_the_target_false_alarm_rate_is_not_eligible():
    """One nominal false alarm in four runs is 0.25, and 0.25 > 0.10."""
    dev = _fixture()
    dev["runs"][0]["alarms"]["CUSUM"]["5.0"] = _alarm(11.0, 11.0, None)
    chosen = ev4.match_operating_points(dev, targets=[0.00, 0.10])
    assert chosen["0.00|CUSUM"]["threshold"] == 200.0
    assert chosen["0.10|CUSUM"]["threshold"] == 200.0


def test_sorting_the_declared_grid_changes_the_selected_threshold():
    """The grid is declared coarse-to-fine, and sorting reverses the ties.

    Phase 3.1 measured crossing time to be non-monotone in fault rate, so a
    sorted grid is not a cosmetic difference; this canary makes the cost
    visible by making the sort change the answer.
    """
    dev = _fixture(grids={"CSIA": [0.9, 0.5], "CUSUM": [200.0, 5.0],
                          "BINST": [0.1, 0.01]})
    # Both CUSUM thresholds are clean, so the tie-break decides, and the
    # tie-break is "more sensitive", which for CUSUM is the LOWER h.
    assert ev4._thresholds(dev, "CUSUM") == ["200.0", "5.0"]
    assert ev4.match_operating_points(dev)["0.00|CUSUM"]["threshold"] == 5.0
    # CSIA is the opposite direction, so the same data selects the HIGHER.
    assert ev4.match_operating_points(dev)["0.00|CSIA"]["threshold"] == 0.9


# ============================================================== STATISTICS

def test_the_bootstrap_is_reproducible_from_the_committed_seed(monkeypatch):
    """Two claims, because one of them is not enough.

    Stability across calls is necessary but weak: on many samples an
    UNSEEDED bootstrap also lands on the same interval twice, so a test that
    only compares two calls would pass on a detector whose intervals are not
    reproducible at all. So the draw sequence is reproduced here from the
    declared seed by an independent reimplementation, AND the seed the
    evaluator actually passes to `random.Random` is recorded and checked.
    """
    values = [1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 3.0, 5.0, 8.0, 40.0]
    assert len(values) == ev4.MIN_DETECTIONS_FOR_CI

    seeds_used = []
    real = random.Random

    class Recording(real):
        def __init__(self, x=None):
            seeds_used.append(x)
            super().__init__(x)

    monkeypatch.setattr(ev4.random, "Random", Recording)
    got = ev4.bootstrap_ci(values, 0.90)
    assert seeds_used == [ev4.BOOTSTRAP_SEED], (
        "the bootstrap must be seeded from the declared constant")
    assert ev4.bootstrap_ci(values, 0.90) == got

    monkeypatch.setattr(ev4.random, "Random", real)
    rng = real(ev4.BOOTSTRAP_SEED)
    n = len(values)
    stats = [ev4.quantile([values[rng.randrange(n)] for _ in range(n)], 0.90)
             for _ in range(ev4.BOOTSTRAP_B)]
    assert got == [ev4.quantile(stats, 0.025), ev4.quantile(stats, 0.975)]


def test_the_full_grid_reports_misses_and_pre_onset_alarms_for_every_point():
    dev, locked = _canary_pair()
    grid = ev4.build(dev, locked)["full_grid_locked"]
    assert len(grid) == 6
    for key, row in grid.items():
        assert row["miss_rate"] is not None
        assert "pre_onset_alarms_on_faulted_runs" in row
    # A detector that never alarms is reported as missing everything, not
    # as having no delay data.
    assert grid["CSIA|0.9"]["miss_rate"] == 1.0
    assert grid["CUSUM|5.0"]["miss_rate"] == 0.0


def test_a_pre_onset_alarm_on_a_faulted_run_is_counted_and_surfaced():
    dev, locked = _fixture(), _fixture(seeds=(11, 12, 13, 14))
    _set(locked, "BINST", 0.1, nominal=False, value=_alarm(12.0, 12.0, None))
    grid = ev4.build(dev, locked)["full_grid_locked"]
    assert grid["BINST|0.1"]["pre_onset_alarms_on_faulted_runs"] == 4
    assert grid["BINST|0.1"]["miss_rate"] == 1.0


# ================================================== THE CAMPAIGN ITSELF

def test_the_settling_window_and_dwell_come_from_the_frozen_failsafe():
    from csia.runtime.failsafe import FailsafeConfig
    cfg = FailsafeConfig()
    assert c4.SETTLE_S == float(cfg.arm_time)
    assert c4.DWELL_TICKS == int(round(cfg.dwell_up * c4.TICK_HZ))


def test_the_csia_detector_needs_the_full_dwell_and_not_one_tick():
    """A dip shorter than the dwell is not an alarm; the dwell IS the detector."""
    n = 200
    t = [i / c4.TICK_HZ for i in range(n)]
    trust = [1.0] * n
    for k in range(50, 50 + c4.DWELL_TICKS - 1):       # one tick short
        trust[k] = 0.0
    s = {"t": _np(t), "trust": _np(trust), "gate": _np([1.0] * n),
         "lam": _np([0.0] * n)}
    assert c4.csia_alarms(s, None)["0.9"]["first"] is None
    trust[50 + c4.DWELL_TICKS - 1] = 0.0               # exactly the dwell
    s["trust"] = _np(trust)
    assert c4.csia_alarms(s, None)["0.9"]["first"] is not None


def test_gated_ticks_are_not_evidence_for_the_csia_detector():
    n = 200
    t = [i / c4.TICK_HZ for i in range(n)]
    s = {"t": _np(t), "trust": _np([0.0] * n), "gate": _np([0.0] * n),
         "lam": _np([0.0] * n)}
    assert c4.csia_alarms(s, None)["0.9"]["first"] is None
    s["gate"] = _np([1.0] * n)
    assert c4.csia_alarms(s, None)["0.9"]["first"] is not None


def test_gated_ticks_are_not_evidence_for_the_cusum_baseline():
    """The baseline is held to the same gating rule as CSIA.

    Giving CUSUM gated-off ticks would let it accumulate on absent evidence,
    which is not a fair baseline in either direction.
    """
    n = 400
    t = [i / c4.TICK_HZ for i in range(n)]
    hot = [10.0] * n                       # far above the in-control mean
    off = {"t": _np(t), "lam": _np(hot), "gate": _np([0.0] * n),
           "trust": _np([1.0] * n)}
    on = dict(off, gate=_np([1.0] * n))
    assert c4.cusum_alarms(off, None)[0]["5.0"]["first"] is None
    assert c4.cusum_alarms(on, None)[0]["5.0"]["first"] is not None


def test_the_campaign_runs_every_onset_for_every_gain_on_a_real_seed(tmp_path):
    """One real seed through the campaign's OWN entry point, start to finish.

    Deliberately `main()` and not a hand-written loop over the grids. A test
    that reproduces the campaign's nesting in its own body proves only that
    the test can nest two loops: prune the grid inside `main` and such a test
    still passes. Going through `main` is what makes the exhaustiveness the
    document claims an assertion about the code that wrote it.
    """
    out = tmp_path / "one_seed.json"
    assert c4.main(["--partition", "development", "--limit", "1",
                    "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))

    expected = {(None, None)} | {(g, o) for g in c4.GAIN_GRID
                                 for o in c4.ONSET_GRID}
    assert len(doc["runs"]) == len(expected) == 21
    assert {(r["gain"], r["onset_s"]) for r in doc["runs"]} == expected
    assert doc["fault"]["onsets_are_exhaustive_not_sampled"] is True
    assert ev4.validate(doc)["all_seeds_complete"] is True

    grids = {"CSIA": c4.THETA_GRID, "CUSUM": c4.H_GRID, "BINST": c4.TAU_GRID}
    for r in doc["runs"]:
        for det, grid in grids.items():
            assert set(r["alarms"][det]) == {repr(v) for v in grid}


# =============================================== THE REPRODUCTION CHECK

def test_the_replay_check_ignores_only_the_declared_timing_field():
    a = _fixture()
    b = copy.deepcopy(a)
    for r in b["runs"]:
        r["ns_total"] = r["ns_total"] * 7 + 1
    assert rc4.compare(a, b)["identical_after_declared_exclusions"] is True
    b["runs"][0]["alarms"]["CSIA"]["0.9"]["after_onset"] = 42.0
    report = rc4.compare(a, b)
    assert report["identical_after_declared_exclusions"] is False
    assert report["n_differing"] == 1


def test_the_replay_check_refuses_a_document_that_declares_nothing():
    doc = _fixture()
    del doc["environment_specific_fields"]
    with pytest.raises(SystemExit, match="does not declare"):
        rc4.compare(doc, doc)


def test_the_committed_locked_runs_declare_their_environment_specific_field():
    assert _load(LOCKED)["environment_specific_fields"] == [
        "runs[].ns_total", "runs[].ns_series_shared", "runs[].ns_cusum",
        "runs[].ns_csia", "runs[].ns_binst"]


def _np(values):
    import numpy as np
    return np.asarray(values, dtype=float)


# ================================================ MANIFEST AND MUTATION SCORE
#
# Both tests below are DESELECTED from the mutation selection, and the reason
# is in `tools/mutation/run_phase4_mutations.py`. A sha256 manifest guard
# fails for EVERY mutant because mutating a file changes its hash, which
# manufactures a perfect score (FL-033); and a test that pins this run's own
# score cannot sit inside the selection that run measures, because changing
# the code changes the score and the unmutated baseline then fails for a
# reason unrelated to any mutant. They belong in the suite, not in a mutation
# selection.

def test_the_manifest_matches_every_file_it_lists():
    manifest = json.loads((P4 / "SHA256_MANIFEST4.json").read_text("utf-8"))
    bad = [rel for rel, want in manifest["files"].items()
           if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want]
    assert bad == [], bad
    assert manifest["frozen_core"]["mismatches"] == []
    assert manifest["pooled_with_consequence_phases"] is False


def test_the_mutation_counts_match_the_write_up():
    """The score, the integrity conditions, and the write-up, pinned together.

    A mutation score means nothing without the conditions under which it was
    produced, so those are asserted here rather than trusted: the unmutated
    baseline passed, the canary died, every kill is attributed to a TEST
    NODE and none to a bare file, and nothing was recorded as invalid.
    """
    d = json.loads((P4 / "results" / "PHASE4_MUTATION_RESULTS.json")
                   .read_text("utf-8"))
    assert d["baseline_unmutated"]["returncode"] == 0
    assert d["canary"]["verdict"] == "KILLED"
    assert d["kills_attributed_to_a_bare_file"] == 0
    assert d["kills_attributed_to_a_test_node"] == d["killed"]
    assert d["invalid"] == 0
    assert (d["evaluated"], d["killed"], d["survived"]) == (17, 17, 0)

    text = (P4 / "PHASE4_RESULTS.md").read_text("utf-8")
    assert "17 evaluated, 17 killed, 0 survived" in text
    for mutant in d["results"]:
        assert mutant["id"] in text, f"{mutant['id']} is not in the write-up"


#: Filled in after the locked partition was opened and the result sealed.
_LOCKED_SHA256 = ("c8f3f94b7eefb1e005ac6fd86c3e624f"
                  "47d083ef18fc48b766351210cdda57f7")
_SEALED_SHA256 = ("6fff064168090336ec64e453c5f03d3b"
                  "dc6402752f859f047b974768e2926812")
