"""Phase 5 — the ANALYSIS PIPELINE, end to end.

WHY SEPARATELY FROM `test_phase5_hybrid.py`
--------------------------------------------
That file tests the modules. This one runs the evaluator whole: on a fixture
where the answer is known by hand, and on the real committed artifacts, where
it must reproduce the sealed result byte for byte. FL-032 is the record of
what happens when only the pieces are tested -- five mutants lived in the
gap between them.

THE CANARIES ARE SYNTHETIC ON PURPOSE
--------------------------------------
Some properties cannot be tested on the real data. If every operating point
happens to select the same way, the real data cannot tell a correct selection
rule from a broken one. Each canary below is a dataset in which the property
under test DECIDES the answer, and each is verified in both directions.
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
P5 = ROOT / "research" / "phase5"
sys.path.insert(0, str(P5))

import evaluate5 as ev5                                   # noqa: E402

DEV = P5 / "results" / "PHASE5_RUNS_DEVELOPMENT.json"
LOCKED = P5 / "results" / "PHASE5_RUNS_LOCKED.json"
SEALED = P5 / "results" / "PHASE5_RESULTS_LOCKED.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _have_locked():
    return LOCKED.exists() and SEALED.exists()


needs_locked = pytest.mark.skipif(
    not _have_locked(), reason="locked partition not yet opened")


# ============================================================ INDEPENDENCE

def test_the_evaluator_imports_no_csia_module():
    """Asserted in a FRESH interpreter, not in this one."""
    import subprocess
    code = ("import sys; sys.path.insert(0, %r); import evaluate5; "
            "print([m for m in sys.modules "
            "if m.startswith('csia') or m == 'numpy'])" % str(P5))
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


# ============================================================ FIXTURES

def _alarm(first=None, after_settle=None, after_onset=None):
    return {"first": first, "after_settle": after_settle,
            "after_onset": after_onset}


def _cons(conflict=False, safe=None, first=None):
    return {"time_to_first_response_s": first,
            "time_to_correct_response_s": None,
            "time_to_safe_state_s": safe,
            "reached_safe_state": safe is not None,
            "position_error_m": 0.0, "max_position_error_m": 0.0,
            "altitude_error_m": 0.0, "min_geofence_margin_m": 120.0,
            "geofence_breached": False, "energy_margin_frac": 1.0,
            "action_conflict": conflict, "false_escalation": False,
            "responses_seen": ["NONE"]}


def _fixture(*, seeds=(1, 2, 3, 4), identifiable_current=0.0,
             identifiable_corrected=1.0, b0_delay=2.5, fast_delay=0.2):
    theta, h, tau, hfast = [0.9, 0.5], [100.0, 200.0], [0.1, 0.2], [50.0, 100.0]
    msids = ["m1", "m2"]
    runs = []
    for seed in seeds:
        cells = [("EA", None, None, None, None),
                 ("EG", None, None, None, None)]
        for cond in ("EA", "EG"):
            cells.append((cond, "structural", "ABRUPT", 3.0, 30.0))
            cells.append((cond, "imu_isolation", "ABRUPT", 0.12, 30.0))
        for cond, fam, shape, mag, onset in cells:
            nominal = fam is None
            def det(delay):
                if nominal:
                    return _alarm()
                t = onset + delay
                return _alarm(t, t, t)
            runs.append({
                "seed": seed, "condition": cond, "family": fam,
                "shape": shape, "magnitude": mag, "onset_s": onset,
                "nominal": nominal, "ticks": 1500, "active_ticks": 1500,
                "trust_states": 1500,
                "detectors": {
                    "B0": {repr(v): det(b0_delay) for v in theta},
                    "B1": {repr(v): det(0.1) for v in h},
                    "B2": {repr(v): det(0.1) for v in tau},
                    "FAST": {repr(v): {"suspected": det(fast_delay * 0.5),
                                       "provisional": det(fast_delay)}
                             for v in hfast},
                    "B5": {m: {"per_scale": {}, "combined": det(0.3),
                               "winning_scale": "FAST", "resets": {}}
                           for m in msids},
                },
                "support": {
                    "current": {"identifiable_frac": identifiable_current,
                                "first_identifiable_s": None,
                                "ticks_airborne": 1000,
                                "ambiguous_frac": 0.0,
                                "non_identifiable_frac": 1.0,
                                "supported_frac": identifiable_current,
                                "separating_active_frac": 0.0,
                                "withdrawn_any": False},
                    "corrected": {"identifiable_frac": identifiable_corrected,
                                  "first_identifiable_s": 0.0,
                                  "ticks_airborne": 1000,
                                  "ambiguous_frac": 0.0,
                                  "non_identifiable_frac": 0.0,
                                  "supported_frac": identifiable_corrected,
                                  "separating_active_frac": 1.0,
                                  "withdrawn_any": False},
                },
                "decisions": {
                    "fault_family": "none" if nominal else "vibration_anomaly",
                    "correct_response": "NONE" if nominal else "PREPARE_LANDING",
                    "faulty_source": "vibration",
                    "p0": {"consequence": _cons(conflict=not nominal),
                           "responses": ["NONE"], "attributing_ticks": 0,
                           "correct_attribution_ticks": 0,
                           "incorrect_attribution_ticks": 0,
                           "any_response": False, "ticks_airborne": 1000},
                    "current": _dec(hfast, conflict=not nominal),
                    "corrected": _dec(hfast, conflict=not nominal),
                },
                "p0_levels": {}, "cusum_max": 0.0, "trust_min": 1.0,
                "ns_total": 1000,
            })
    return {"schema": "csia.phase5.hybrid_runs/1", "partition": "fixture",
            "runs": runs, "seeds": list(seeds), "settle_s": 10.0,
            "horizon_s": 60.0, "cells_per_seed": 6,
            "conditions": ["EA", "EG"], "invalid_runs": [],
            "families": {"structural": {}, "imu_isolation": {}},
            "multiscale_grid": [{"id": m} for m in msids],
            "grids": {"B0": theta, "B1": h, "B2": tau, "FAST": hfast,
                      "B5": msids}}


def _dec(hfast, conflict=False):
    return {
        "consequence_p2": _cons(conflict=conflict),
        "consequence_hybrid_by_hfast": {repr(v): _cons(conflict=conflict)
                                        for v in hfast},
        "p2_refusal_ticks": 0, "p2_false_refusal_ticks": 0,
        "p2_false_refusal_frac": 0.0, "p2_any_false_refusal": False,
        "hybrid_downgrade_ticks": 0, "hybrid_any_abstain": False,
        "hybrid_added_caution_ticks_all_hfast": 0,
        "unsupported_confident_ticks": 0, "unsupported_confident_frac": 0.0,
        "p2_responses": ["NONE"], "hybrid_responses": ["NONE"],
    }


# ============================================================ END TO END

def test_build_runs_end_to_end_on_a_fixture():
    dev, locked = _fixture(), _fixture(seeds=(11, 12, 13, 14))
    out = ev5.build(dev, locked)
    assert out["schema"] == "csia.phase5.hybrid_results/1"
    assert out["is_experimental"] is True
    assert out["pooled_with_earlier_phases"] is False
    assert out["intake"]["locked"]["runs_seen"] == len(locked["runs"])
    assert set(out["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert out["dominance"]["verdict"] in ev5.VERDICTS


def test_the_declared_verdict_vocabulary_is_closed():
    assert ev5.VERDICTS == (
        "HYBRID_DOMINATES_ON_DECLARED_SYSTEM_METRICS",
        "HYBRID_IMPROVES_LATENCY_ONLY",
        "HYBRID_IMPROVES_SUPPORT_ONLY",
        "HYBRID_IMPROVES_ACTIONABILITY_ONLY",
        "NO_HYBRID_DOMINANCE",
        "INCONCLUSIVE")


# ============================================================ REFUSALS

@pytest.mark.parametrize("key", ev5.REQUIRED_KEYS)
def test_a_document_missing_a_required_key_is_refused(key):
    doc = _fixture()
    del doc[key]
    with pytest.raises(ev5.DocumentError, match=key):
        ev5.validate(doc)


def test_a_duplicate_run_is_refused():
    doc = _fixture()
    doc["runs"].append(copy.deepcopy(doc["runs"][0]))
    with pytest.raises(ev5.DocumentError, match="duplicate run"):
        ev5.validate(doc)


def test_a_nominal_run_that_names_a_family_is_refused():
    doc = _fixture()
    nominal = next(r for r in doc["runs"] if r["nominal"])
    nominal["family"] = "structural"
    with pytest.raises(ev5.DocumentError, match="nominal but names a family"):
        ev5.validate(doc)


def test_a_faulted_run_without_an_onset_is_refused():
    doc = _fixture()
    faulted = next(r for r in doc["runs"] if not r["nominal"])
    faulted["onset_s"] = None
    with pytest.raises(ev5.DocumentError, match="has no onset"):
        ev5.validate(doc)


def test_a_missing_detector_is_refused():
    doc = _fixture()
    del doc["runs"][0]["detectors"]["B5"]
    with pytest.raises(ev5.DocumentError, match="no B5 alarms"):
        ev5.validate(doc)


# ============================================================ CANARIES

def test_the_hybrid_alarm_is_provisional_and_not_suspected():
    """Crediting the hybrid with SUSPECTED_CHANGE would flatter it.

    The canary makes the difference decide the number: suspected fires at
    half the provisional delay, so a pipeline reading the wrong series
    reports half the latency.
    """
    dev = _fixture(fast_delay=1.0)
    got = ev5.detections(dev, "B3", "50.0", family="structural")
    assert got["median_delay_s"] == pytest.approx(1.0)
    assert got["median_delay_s"] != pytest.approx(0.5)


def test_thresholds_are_selected_on_development_only():
    import inspect
    src = inspect.getsource(ev5.match_operating_points)
    assert "locked" not in src


def test_selecting_on_locked_instead_of_development_changes_the_verdict():
    """A canary where the two partitions disagree about the fast threshold."""
    dev = _fixture()
    locked = _fixture(seeds=(11, 12, 13, 14))
    # h_fast 50 false-alarms on development only.
    for r in dev["runs"]:
        if r["nominal"]:
            r["detectors"]["FAST"]["50.0"]["provisional"] = _alarm(11.0, 11.0)
    assert ev5.match_operating_points(dev)["0.00|B3"]["threshold"] == "100.0"
    assert ev5.match_operating_points(locked)["0.00|B3"]["threshold"] == "50.0"


def test_a_threshold_above_the_target_is_not_eligible():
    dev = _fixture(seeds=tuple(range(1, 21)))
    one = next(r for r in dev["runs"] if r["nominal"])
    one["detectors"]["FAST"]["50.0"]["provisional"] = _alarm(11.0, 11.0)
    chosen = ev5.match_operating_points(dev, targets=[0.00, 0.05])
    assert chosen["0.00|B3"]["threshold"] == "100.0"
    assert chosen["0.05|B3"]["threshold"] == "50.0"


def test_the_grid_is_read_in_declaration_order():
    doc = _fixture()
    doc["grids"]["B0"] = [0.9, 0.4, 0.7]
    assert ev5._thresholds(doc, "B0") == ["0.9", "0.4", "0.7"]
    import inspect
    assert "sorted(" not in inspect.getsource(ev5._thresholds)


def test_a_zero_false_alarm_count_is_labelled_as_a_count_not_a_probability():
    doc = _fixture()
    fa = ev5.false_alarms(doc, "B0", "0.9")
    assert fa["false_alarm_runs"] == 0
    assert fa["is_a_finite_horizon_count_not_a_probability"] is True
    assert fa["ci95"][1] > 0.0, "a zero count must carry a non-zero upper bound"


def test_support_availability_is_seed_paired_and_exact():
    locked = _fixture(seeds=(1, 2, 3, 4), identifiable_current=0.0,
                      identifiable_corrected=1.0)
    av = ev5.support_availability(locked, condition="EG",
                                  family="imu_isolation")
    assert av["seeds_available"] == {"current": 0, "corrected": 4}
    assert av["discordant_corrected_only"] == 4
    assert av["gain"] == 1.0
    assert av["mcnemar_p"] == pytest.approx(2 * (1 / 16))


def test_the_hybrid_false_refusal_rate_is_flagged_as_true_by_construction():
    """It is zero because the hybrid never abstains. That is a design fact,
    and reporting it as evidence for the correction would be circular."""
    locked = _fixture()
    dm = ev5.decision_metrics(locked, family="imu_isolation")
    for m in ("current", "corrected"):
        assert dm[m]["hybrid_false_refusal_rate"] == 0.0
        assert dm[m]["hybrid_false_refusal_is_zero_by_construction"] is True


def test_noninferiority_uses_the_declared_margin_and_an_exact_bound():
    worse = ev5.noninferior(20, 20, 0, 20)
    assert worse["noninferior"] is False
    same = ev5.noninferior(0, 20, 0, 20)
    assert same["noninferior"] is False, (
        "an exact upper bound on 0/20 exceeds 0.05, and pretending otherwise "
        "would be the whole point of the margin")
    bigger = ev5.noninferior(0, 200, 0, 200)
    assert bigger["noninferior"] is True


# ============================================================ STATISTICS

def test_mcnemar_is_unchanged_from_the_earlier_phases():
    assert ev5.mcnemar_exact(40, 0) == pytest.approx(1.8189894035458565e-12)
    assert ev5.mcnemar_exact(0, 0) == 1.0
    assert ev5.mcnemar_exact(3, 1) == pytest.approx(0.625)


def test_clopper_pearson_matches_the_exact_interval():
    assert ev5.clopper_pearson(0, 40) == [0.0, 0.088097]
    assert ev5.clopper_pearson(40, 40) == [0.911903, 1.0]


def test_the_bootstrap_sorts_its_input_before_resampling():
    """FL-037: resampling by index made the interval depend on file order."""
    values = [1.0, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0, 55.0]
    shuffled = list(reversed(values))
    assert ev5.bootstrap_ci(values, 0.9) == ev5.bootstrap_ci(shuffled, 0.9)


def test_no_interval_is_computed_from_too_few_detections():
    assert ev5.bootstrap_ci([1.0] * (ev5.MIN_DETECTIONS_FOR_CI - 1), 0.5) is None
    assert ev5.bootstrap_ci([1.0] * ev5.MIN_DETECTIONS_FOR_CI, 0.5) is not None


# ============================================================ REAL ARTIFACTS

def test_the_development_campaign_declares_what_it_measured():
    doc = _load(DEV)
    assert doc["is_experimental"] is True
    assert doc["executed_an_autopilot"] is False
    assert doc["armed_a_vehicle"] is False
    assert doc["touched_hardware"] is False
    assert doc["pooled_with_earlier_phases"] is False
    assert doc["consequence_evidence_level"] == "MODEL_BASED_ACTION_CONSEQUENCE"
    assert doc["partition"] == "development"
    assert ev5.validate(doc)["invalid_runs"] == 0


@needs_locked
def test_build_reproduces_the_sealed_result_from_the_committed_runs():
    rebuilt = ev5.build(_load(DEV), _load(LOCKED))
    text = json.dumps(rebuilt, indent=1, sort_keys=True) + "\n"
    assert text == SEALED.read_text(encoding="utf-8")


@needs_locked
def test_reordering_the_runs_changes_no_reported_number():
    dev, locked = _load(DEV), _load(LOCKED)
    shuffled = copy.deepcopy(locked)
    random.Random(515).shuffle(shuffled["runs"])
    assert shuffled["runs"] != locked["runs"]
    text = json.dumps(ev5.build(dev, shuffled), indent=1, sort_keys=True) + "\n"
    assert text == SEALED.read_text(encoding="utf-8")


# ============================================ MANIFEST AND MUTATION SCORE
#
# Both DESELECTED from the mutation selection, for the reasons in
# `tools/mutation/run_phase5_mutations.py`: a sha256 manifest guard fails for
# every mutant (FL-033), and a test pinning this run's own score cannot sit
# inside the selection that run measures.

MANIFEST = P5 / "SHA256_MANIFEST5.json"
MUTATION = P5 / "results" / "PHASE5_MUTATION_RESULTS.json"


@pytest.mark.skipif(not MANIFEST.exists(), reason="manifest not yet built")
def test_the_manifest_matches_every_file_it_lists():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = [rel for rel, want in m["files"].items()
           if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want]
    assert bad == [], bad
    assert m["frozen_core"]["mismatches"] == []
    assert m["pooled_with_earlier_phases"] is False
    assert m["is_experimental"] is True


@pytest.mark.skipif(not MUTATION.exists(), reason="mutation not yet run")
def test_the_mutation_counts_match_the_write_up():
    """The score, its integrity conditions, and the write-up, pinned together.

    A mutation score means nothing without the conditions that produced it,
    so those are asserted rather than trusted.
    """
    d = json.loads(MUTATION.read_text(encoding="utf-8"))
    assert d["baseline_unmutated"]["returncode"] == 0
    assert d["canary"]["verdict"] == "KILLED"
    assert d["kills_attributed_to_a_bare_file"] == 0
    assert d["kills_attributed_to_a_test_node"] == d["killed"]
    assert d["invalid"] == 0
    assert d["evaluated"] == d["killed"] + d["survived"]

    write_up = P5 / "PHASE5_RESULTS.md"
    if write_up.exists():
        text = write_up.read_text(encoding="utf-8")
        assert (f"{d['evaluated']} evaluated, {d['killed']} killed, "
                f"{d['survived']} survived") in text
        for mutant in d["results"]:
            assert mutant["id"] in text, f"{mutant['id']} not in the write-up"
