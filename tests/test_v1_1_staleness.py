"""Phase 4.5 Gate B: runtime stale-timeout derivation and its regression.

The two that matter most:

  * the rule introduces NO number of its own -- it is the adapter's own
    MaxAge, which is the adapter's own MAX_AGE_MARGIN over the contract's own
    declared rate (§9);
  * relaxing a timeout did not buy false-stale immunity by making hard-dropout
    detection unbounded (§7).
"""

from __future__ import annotations

import ast
import csv
import json
import os
import subprocess

import pytest

from csia.aircraft.adapters import get_adapter
from csia.aircraft.adapters.base import MAX_AGE_MARGIN, PlatformAdapter
from csia.runtime.online import STALE_TIMEOUT_S
from csia.v1_1 import staleness as ST

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEP = os.path.join(ROOT, "validation", "v1_1", "deployment")
PLATFORMS = ("ardupilot", "px4")


def _matrix():
    p = os.path.join(DEP, "STALENESS_MATRIX.csv")
    if not os.path.exists(p):
        pytest.skip("staleness matrix not built")
    return list(csv.DictReader(open(p, encoding="utf-8")))


def _summary():
    p = os.path.join(DEP, "STALENESS_REGRESSION_SUMMARY.json")
    if not os.path.exists(p):
        pytest.skip("staleness summary not built")
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------ inherited integrity
def test_the_frozen_core_is_still_untouched():
    r = subprocess.run(["git", "diff", "--stat", "csia-v1.0-research-final",
                        "--", "csia/trust_engine", "csia/diagnosis",
                        "csia/runtime/online.py", "csia/runtime/failsafe.py",
                        "csia/scenarios.py", "csia/profiles.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag unavailable")
    assert r.stdout.strip() == "", r.stdout


def test_the_frozen_default_table_is_not_edited():
    """The fix is an override passed in, never a change to the defaults."""
    assert STALE_TIMEOUT_S == {
        "imu0": 0.05, "imu1": 0.05, "baro": 0.1, "mag": 0.1, "gps": 0.5,
        "motor_esc": 0.1, "battery": 0.5, "vibration": 0.5}


# -------------------------------------------------------------- §5 / §9
def test_the_rule_defines_no_number_of_its_own():
    """Section 9: a multiplier that does not exist cannot be tuned.

    Rounding precision passed to `round()` is not a timeout constant, so it
    is excluded BY POSITION rather than by being small enough to overlook.
    """
    src = open(os.path.join(ROOT, "csia", "v1_1", "staleness.py"),
               encoding="utf-8").read()
    tree = ast.parse(src)
    rounding = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "round"):
            rounding.update(id(a) for a in node.args[1:])
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant)
                and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)
                and id(n) not in rounding]
    assert literals == [], literals
    assert "MAX_AGE_MARGIN" in src


def test_the_channel_max_age_agrees_with_a_live_adapter():
    """If these two ever drift, the runtime and the ingest layer are back to
    disagreeing -- which is the defect this module exists to close."""
    for platform in PLATFORMS:
        mine = ST.channel_max_age(platform)
        theirs = get_adapter(platform)._derive_max_age()
        assert mine == theirs, platform


def test_the_margin_is_the_adapters_own():
    assert MAX_AGE_MARGIN == 5.0
    ages = ST.channel_max_age("px4")
    assert ages["esc.rpm"] == MAX_AGE_MARGIN / 1.0
    assert ages["gnss.position"] == MAX_AGE_MARGIN / 5.0


def test_the_node_timeout_is_the_slowest_required_channel():
    """`max`, not `min`: a node stops arriving when its slowest-permitted
    required channel stops being usable."""
    for platform in PLATFORMS:
        ages = ST.channel_max_age(platform)
        got = ST.build_runtime_stale_timeouts(platform)
        for node, timeout in got.items():
            needed = ST.required_channels(node)
            assert timeout == max(ages[ch] for ch in needed), (platform, node)


def test_the_optional_baro_temperature_does_not_drive_a_timeout():
    assert "baro.temp_c" not in ST.required_channels("baro")
    assert ST.required_channels("baro") == ("baro.altitude",)


def test_every_trust_node_gets_a_timeout_and_nothing_else_does():
    for platform in PLATFORMS:
        got = ST.build_runtime_stale_timeouts(platform)
        assert set(got) == set(STALE_TIMEOUT_S)
        assert "vehicle_status" not in got


def test_the_derived_map_matches_the_published_table():
    """If these move, the spec and the audit are describing a different
    system. Fix the code or reissue both -- not this test."""
    ap = ST.build_runtime_stale_timeouts("ardupilot")
    px = ST.build_runtime_stale_timeouts("px4")
    assert ap == {"imu0": 0.2, "imu1": 0.2, "baro": 0.5, "mag": 0.2,
                  "gps": 1.0, "motor_esc": 0.5, "battery": 0.5,
                  "vibration": 0.5}
    assert px["motor_esc"] == 5.0
    assert px["imu0"] == 0.1
    assert round(px["mag"], 6) == round(5.0 / 14.0, 6)


def test_the_derivation_is_explainable_to_its_source_row():
    rows = {r["node"]: r for r in ST.explain("px4")}
    assert rows["motor_esc"]["declared_rate_hz"] == 1
    assert rows["motor_esc"]["source"] == "contract"
    assert rows["motor_esc"]["driving_channel"] == "esc.current"
    assert rows["gps"]["margin_periods"] == 5.0


# -------------------------------------------------------------------- §10
def test_the_shadow_constructor_passes_the_derived_map():
    from csia.deploy.shadow import ShadowConfig, ShadowRunner
    for platform in PLATFORMS:
        runner = ShadowRunner(ShadowConfig(platform=platform))
        want = ST.build_runtime_stale_timeouts(platform)
        assert runner.stale_timeouts == want, platform
        assert runner.layer._stale == want, platform


def test_no_numeric_timeout_is_copied_into_the_deployment_module():
    """Section 5: do not copy numeric constants manually into shadow.py.

    Parsed, not grepped. The module's own comment explains the defect by
    naming `STALE_TIMEOUT_S`, and a grep would match the explanation rather
    than an import -- which is the opposite of what is being checked.
    """
    tree = ast.parse(open(os.path.join(ROOT, "csia", "deploy", "shadow.py"),
                          encoding="utf-8").read())
    imported, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.Name):
            used.add(node.id)
    assert "build_runtime_stale_timeouts" in imported
    assert "STALE_TIMEOUT_S" not in imported
    assert "STALE_TIMEOUT_S" not in used

    # and the call site passes the derived map rather than a literal
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id == "OnlineTrustLayer"]
    assert len(calls) == 1
    kw = {k.arg for k in calls[0].keywords}
    assert "stale_timeout_s" in kw


# ------------------------------------------------------------- §4 / §11
def test_the_px4_esc_node_never_reaches_the_core_in_either_arm():
    """The reproduction's NEGATIVE result, and the correction to Phase 4 §68.

    Two arms with opposite timeouts (0.1 s and 5.0 s) and an identical
    outcome is how you tell the timeout is not the cause: the node is
    withheld by QUALIFICATION, one layer earlier.
    """
    for name in ("PX4_MOTOR_ESC_STALENESS_PRE_FIX.csv",
                 "PX4_MOTOR_ESC_STALENESS_POST_FIX.csv"):
        p = os.path.join(DEP, name)
        if not os.path.exists(p):
            pytest.skip("reproduction not built")
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        assert rows
        assert all(r["motor_esc_reached_core"] == "False" for r in rows), name
        assert all(r["esc_rpm_admissible"] == "False" for r in rows), name
        assert all(r["esc_current_admissible"] == "False" for r in rows), name
    pre = list(csv.DictReader(open(
        os.path.join(DEP, "PX4_MOTOR_ESC_STALENESS_PRE_FIX.csv"),
        encoding="utf-8")))
    post = list(csv.DictReader(open(
        os.path.join(DEP, "PX4_MOTOR_ESC_STALENESS_POST_FIX.csv"),
        encoding="utf-8")))
    assert pre[0]["stale_timeout_s"] == "0.1"
    assert post[0]["stale_timeout_s"] == "5.0"


def test_motor_esc_is_inadmissible_on_both_platforms():
    s = _summary()["admissibility"]
    for platform in PLATFORMS:
        assert s[platform]["motor_esc"]["admissible"] is False, platform
        assert s[platform]["motor_esc"]["blocked_by"], platform


def test_an_inadmissible_node_reports_no_staleness_metric():
    """Blaming the watchdog for a qualification decision would be a
    misattribution, so those cells are null rather than 100%."""
    for r in _matrix():
        if r["admissible"] == "False":
            assert r["nominal_false_stale_fraction"] == "", r
            assert r["dropout_stale_latency_s"] == "", r


# --------------------------------------------------------------- §7 / §8
def test_the_derived_rule_has_no_false_stale_on_any_admissible_node():
    for r in _matrix():
        if r["admissible"] != "True" or r["arm"] != "DERIVED_RULE":
            continue
        if r["condition"] not in ("NOMINAL_RATE", "RATE_JITTER"):
            continue
        assert float(r["nominal_false_stale_fraction"]) == 0.0, r


def test_the_frozen_default_false_stales_baro_under_jitter():
    """The defect that IS reproducible: 0.10 s timeout on a 0.10 s period
    leaves exactly zero margin, so any positive jitter trips it."""
    hits = {(r["platform"], r["node"]): float(
                r["nominal_false_stale_fraction"])
            for r in _matrix()
            if r["arm"] == "FROZEN_DEFAULT" and r["condition"] == "RATE_JITTER"
            and r["admissible"] == "True"
            and float(r["nominal_false_stale_fraction"]) > 0.0}
    assert set(hits) == {("ardupilot", "baro"), ("px4", "baro")}, hits
    assert all(0.02 < v < 0.05 for v in hits.values()), hits
    assert STALE_TIMEOUT_S["baro"] == 0.1
    assert ST.build_runtime_stale_timeouts("px4")["baro"] == 0.5


def test_nothing_false_stales_at_exactly_nominal_rate_in_either_arm():
    for r in _matrix():
        if r["admissible"] == "True" and r["condition"] == "NOMINAL_RATE":
            assert float(r["nominal_false_stale_fraction"]) == 0.0, r


def test_every_admissible_node_still_detects_a_hard_dropout():
    """Section 7: the false-stale fix must not be bought by making stale
    detection arbitrarily slow."""
    tick = 1.0 / _summary()["tick_hz"]
    for r in _matrix():
        if r["condition"] != "SUSTAINED_DROPOUT" or r["admissible"] != "True":
            continue
        lat = r["dropout_stale_latency_s"]
        assert lat != "", r
        lat, timeout = float(lat), float(r["stale_timeout_s"])
        # detection fires on the first tick with age > timeout, so the
        # latency is bounded by construction rather than by luck
        assert timeout < lat <= timeout + 2 * tick + 1e-9, r


def test_the_worst_dropout_latency_is_bounded_and_recorded():
    s = _summary()
    worst = s["worst_sustained_dropout_latency_s"]
    assert worst["FROZEN_DEFAULT"]["latency_s"] == 0.56
    assert worst["DERIVED_RULE"]["latency_s"] == 1.08
    assert worst["DERIVED_RULE"]["node"] == "gps"
    assert worst["DERIVED_RULE"]["latency_s"] < 1.2


def test_the_gates_passed():
    s = _summary()
    assert s["gate_B_nominal_rate_pass"] is True
    assert s["gate_B_jitter_pass"] is True
    assert s["gate_C_hard_dropout_pass"] is True
    assert s["evidence_tier"]["matrix"] == "SYNTHETIC_DEPLOYMENT_REGRESSION"


def test_the_matrix_covers_every_node_condition_and_platform():
    rows = _matrix()
    seen = {(r["platform"], r["node"], r["condition"], r["arm"])
            for r in rows}
    assert len(seen) == 2 * 8 * 4 * 2 == len(rows)


# -------------------------------------------------------------------- §12
def test_the_timeout_change_moved_no_phase_4_result():
    p = os.path.join(DEP, "PHASE4_REGRESSION_AFTER_TIMEOUT.json")
    if not os.path.exists(p):
        pytest.skip("phase 4 regression not built")
    d = json.load(open(p, encoding="utf-8"))
    assert d["verdict"] == "NO_BEHAVIOURAL_CHANGE"
    assert d["structural_check"]["pass"] is True
    assert d["behavioural_change"] is False
    assert d["artifacts_differing_behaviourally"] == []
    # the eligibility results must be byte-identical, not merely equivalent
    byte_same = {a["artifact"] for a in d["artifacts"]
                 if a.get("bytes_identical")}
    assert "engineering/v1_1/FUNCTION_ELIGIBILITY_RESULTS.csv" in byte_same


def test_the_phase_4_runners_cannot_see_a_runtime_timeout():
    """The structural reason the check above is not a coincidence."""
    banned = {"OnlineTrustLayer", "get_adapter", "PlatformAdapter",
              "ShadowRunner", "build_runtime_stale_timeouts"}
    for rel in ("run_p4b.py", "run_p4c.py", "run_p4d.py"):
        tree = ast.parse(open(os.path.join(
            ROOT, "engineering", "v1_1", "phase4", rel),
            encoding="utf-8").read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
        assert not (names & banned), (rel, names & banned)


# --------------------------------------------------------------- evidence
def test_the_real_ulog_rates_are_recorded_as_a_different_transport():
    p = os.path.join(DEP, "PX4_ULOG_TOPIC_RATES.csv")
    if not os.path.exists(p):
        pytest.skip("no ULog reachable in this environment")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows
    esc = [r for r in rows if r["topic"] == "esc_status"]
    assert esc, "esc_status missing from the real logs"
    # ~10 Hz on the uORB/ULog transport against the 1 Hz the contract
    # declares for MAVLink ESC_STATUS. Different transports, different rates.
    assert all(float(r["mean_rate_hz"]) > 5.0 for r in esc), esc
    assert _summary()["evidence_tier"]["ulog_rates"] == "REAL_PX4_ULOG_TIMING"


def test_the_spec_records_the_phase_4_correction():
    t = open(os.path.join(ROOT, "engineering", "v1_1",
                          "STALENESS_RUNTIME_SPEC.md"), encoding="utf-8").read()
    assert "That prediction was" in t and "wrong" in t
    assert "min" in t and "max" in t
    assert "No published number changes" in t
