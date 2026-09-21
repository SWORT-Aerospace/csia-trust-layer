"""Phase 4 — detector performance.

Phase 4 measures delay against false alarms. It measures no consequence, and
a test asserts the artifacts say so rather than leaving it to the prose.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P4 = ROOT / "research" / "phase4"
sys.path.insert(0, str(P4))

import evaluate4 as ev4                                   # noqa: E402

from csia_consequence import phase4_partitions as parts4  # noqa: E402

PREREG = P4 / "PREREGISTRATION_PHASE4.md"
DEV = P4 / "results" / "PHASE4_RUNS_DEVELOPMENT.json"


# --- partitions and preregistration ---------------------------------------

def test_the_phase4_partition_manifest_is_pinned():
    assert parts4.manifest_hash() == (
        "bbcaae73c2eee4a579e90723df8d1ea48dcc4e201fb0fd3a2072499d4cdd3174")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        parts4.seeds("locked")
    assert len(parts4.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 40


def test_phase4_seeds_are_disjoint_from_every_consequence_phase():
    from csia_consequence import phase3_partitions as p3
    from csia_consequence import phase31_partitions as p31
    from csia_consequence import phase32_partitions as p32
    parts4.assert_disjoint()
    parts4.assert_disjoint_from_earlier_phases()
    ours = {s for v in parts4.PARTITIONS.values() for s in v}
    for mod in (p3, p31, p32):
        assert ours & {s for v in mod.PARTITIONS.values() for s in v} == set()


def test_the_preregistration_states_the_non_monotonicity_explicitly():
    text = PREREG.read_text(encoding="utf-8")
    assert "**Crossing time is non-monotone in fault rate.**" in text
    for required in ("never** interpolates", "never** sorts or prunes",
                     "34.752", "conflict rate went 40, 40, 31"):
        assert required in text, required


def test_the_preregistration_declares_the_matching_rule_and_the_grids():
    text = PREREG.read_text(encoding="utf-8")
    assert parts4.manifest_hash() in text
    for required in ("TARGET_FAR = [0.00, 0.05, 0.10]",
                     "Primary comparison: `TARGET_FAR = 0.00`",
                     "development` only", "No interim looks",
                     "CUSUM is not a straw man",
                     "NO_THRESHOLD_MEETS_TARGET"):
        assert required in text, required


def test_the_preregistration_forbids_the_claims_it_must():
    text = PREREG.read_text(encoding="utf-8").lower()
    for denial in ("no hardware validation", "no flight validation",
                   "no autopilot execution", "no airworthiness",
                   "no certification", "no novelty claim",
                   "raim proves the csia mechanism",
                   "aircraft that report esc telemetry"):
        assert denial in text, denial


# --- the evaluator --------------------------------------------------------

def test_the_evaluator_imports_no_csia_module():
    code = ("import sys; sys.path.insert(0, %r);"
            "import evaluate4;"
            "print(sorted(m for m in sys.modules"
            " if m.split('.')[0].startswith('csia')))" % str(P4))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


@pytest.mark.parametrize("values,q,want", [
    ([1.0], 0.5, 1.0),
    ([1.0, 2.0, 3.0], 0.5, 2.0),
    ([1.0, 2.0, 3.0, 4.0], 0.5, 2.5),
    ([float(i) for i in range(1, 101)], 0.90, 90.1),
    ([float(i) for i in range(1, 101)], 0.99, 99.01),
])
def test_the_quantile_is_the_declared_interpolation(values, q, want):
    assert ev4.quantile(values, q) == pytest.approx(want)


def test_a_quantile_of_nothing_is_none_not_zero():
    assert ev4.quantile([], 0.5) is None


def test_no_interval_is_computed_from_too_few_detections():
    assert ev4.bootstrap_ci([1.0] * 9, 0.5) is None
    assert ev4.bootstrap_ci([1.0] * 10, 0.5) is not None


def test_clopper_pearson_matches_the_exact_interval():
    assert ev4.clopper_pearson(0, 40)[1] == pytest.approx(0.088097, abs=1e-5)
    assert ev4.clopper_pearson(40, 40)[0] == pytest.approx(0.911903, abs=1e-5)


def _run(seed, gain, onset, alarms):
    return {"seed": seed, "gain": gain, "onset_s": onset,
            "nominal": gain is None, "ticks": 1500, "alarms": alarms,
            "cusum_max": 0.0, "trust_min": 1.0, "active_ticks": 1500,
            "ns_total": 1000}


def _alarm(first=None, after_settle=None, after_onset=None):
    return {"first": first, "after_settle": after_settle,
            "after_onset": after_onset}


def _doc(runs, *, partition="fixture", seeds=None):
    return {"runs": runs, "settle_s": 10.0, "horizon_s": 60.0,
            "partition": partition,
            "seeds": sorted({r["seed"] for r in runs}) if seeds is None
                     else seeds,
            "grids": {"CSIA": [0.9], "CUSUM": [200.0], "BINST": [0.1]},
            "fault": {"gain_grid": [3.0], "onset_grid": [30.0]}}


def _alarms(first=None, after_settle=None, after_onset=None):
    a = _alarm(first, after_settle, after_onset)
    return {"CSIA": {"0.9": a}, "CUSUM": {"200.0": a}, "BINST": {"0.1": a}}


def test_a_latched_alarm_from_the_settling_window_is_a_false_alarm():
    """The defect a development run exposed.

    A detector that crossed at 4.92 s and stayed above threshold is alarming
    throughout the horizon. Measured from `first` alone it looks clean;
    measured from `after_settle` it is what it is.
    """
    latched = _doc([_run(1, None, None,
                         _alarms(first=4.92, after_settle=10.0))])
    assert ev4.false_alarms(latched, "CUSUM", "200.0")["false_alarm_runs"] == 1
    clean = _doc([_run(1, None, None, _alarms(first=4.92, after_settle=None))])
    assert ev4.false_alarms(clean, "CUSUM", "200.0")["false_alarm_runs"] == 0


def test_a_pre_onset_alarm_is_not_a_detection_with_negative_delay():
    doc = _doc([_run(1, 3.0, 30.0,
                     _alarms(first=12.0, after_settle=12.0, after_onset=None))])
    got = ev4.detections(doc, "CSIA", "0.9")
    assert got["misses"] == 1
    assert got["pre_onset_alarms_on_faulted_runs"] == 1
    assert got["mean_delay_s"] is None


def test_a_miss_is_reported_and_never_imputed_as_the_horizon():
    doc = _doc([_run(1, 3.0, 30.0, _alarms()),
                _run(2, 3.0, 30.0,
                     _alarms(first=31.0, after_settle=31.0, after_onset=31.0))])
    got = ev4.detections(doc, "CSIA", "0.9")
    assert got["misses"] == 1 and got["detections"] == 1
    assert got["miss_rate"] == 0.5
    assert got["delays_s"] == [1.0]
    assert got["mean_delay_s"] == 1.0


def test_thresholds_are_selected_on_development_only():
    """The matching reads the development document and nothing else."""
    import inspect
    src = inspect.getsource(ev4.match_operating_points)
    assert "locked" not in src


def test_a_detector_that_cannot_meet_a_target_is_reported_not_dropped():
    dev = _doc([_run(1, None, None,
                     _alarms(first=11.0, after_settle=11.0))])
    chosen = ev4.match_operating_points(dev, targets=[0.00])
    for det in ev4.DETECTORS:
        assert chosen[f"0.00|{det}"]["status"] == "NO_THRESHOLD_MEETS_TARGET"


def test_the_grid_is_read_in_declaration_order():
    doc = _doc([])
    doc["grids"]["CSIA"] = [0.9, 0.5, 0.7]
    assert ev4._thresholds(doc, "CSIA") == ["0.9", "0.5", "0.7"]
    import inspect
    assert "sorted(" not in inspect.getsource(ev4._thresholds)


def test_a_duplicate_run_is_refused():
    doc = _doc([_run(1, 3.0, 30.0, _alarms()), _run(1, 3.0, 30.0, _alarms())])
    with pytest.raises(ev4.DocumentError, match="duplicate run"):
        ev4.validate(doc)


def test_a_missing_threshold_is_refused():
    doc = _doc([_run(1, 3.0, 30.0, _alarms())])
    del doc["runs"][0]["alarms"]["CSIA"]["0.9"]
    with pytest.raises(ev4.DocumentError, match="missing CSIA thresholds"):
        ev4.validate(doc)


# --- the development artifact ---------------------------------------------

def test_the_development_campaign_declares_what_it_measured():
    doc = json.loads(DEV.read_text(encoding="utf-8"))
    assert doc["executed_an_autopilot"] is False
    assert doc["armed_a_vehicle"] is False
    assert doc["touched_hardware"] is False
    assert doc["pooled_with_consequence_phases"] is False
    assert doc["evidence_level"] == "DETERMINISTIC_SIMULATION"
    assert "no action, no policy" in doc["measures"]
    assert doc["node"] == "vibration"
    assert doc["fault"]["onsets_are_exhaustive_not_sampled"] is True
    assert doc["partition"] == "development"


def test_every_declared_grid_point_appears_in_every_run():
    doc = json.loads(DEV.read_text(encoding="utf-8"))
    assert ev4.validate(doc)["runs_seen"] == len(doc["runs"])
    expected = 12 * (1 + len(doc["fault"]["gain_grid"])
                     * len(doc["fault"]["onset_grid"]))
    assert len(doc["runs"]) == expected


def test_the_cusum_uses_the_repositorys_frozen_in_control_statistics():
    doc = json.loads(DEV.read_text(encoding="utf-8"))
    from csia.v1_1.sequential import CUSUM_K, IN_CONTROL
    assert doc["cusum_k"] == CUSUM_K
    assert (doc["in_control"]["mu0"], doc["in_control"]["sigma0"]) == \
        IN_CONTROL["vibration"]
