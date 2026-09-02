"""Phase 4.5 §§20–28: the frozen golden corpus and the numeric spec.

The two that matter most:

  * the run-length encoding is LOSSLESS -- the full per-tick Tier-A series is
    reconstructed and checked against its own hash, not taken on trust;
  * the Tier-B tolerance was frozen BEFORE any C exists, and no C exists.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EMB = os.path.join(ROOT, "embedded", "v1_1")
GOLD = os.path.join(EMB, "golden")

EXPECTED_CASES = {
    "CLEAN", "GNSS_RAMP_SLOW", "GNSS_RAMP_FAST", "GNSS_FIX_LOSS",
    "IMU0_BIAS_DRIFT", "DUAL_IMU_FAILURE", "MAG_DEGRADED", "POWER_SAG",
    "VIBRATION_ANOMALY", "BATTERY_SENTINEL", "MAG_SENTINEL"}


def _manifest():
    p = os.path.join(GOLD, "MANIFEST.json")
    if not os.path.exists(p):
        pytest.skip("golden corpus not built")
    return json.load(open(p, encoding="utf-8"))


def _lines(name):
    with open(os.path.join(GOLD, name), encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def _canon(row):
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------- §29 / §36
def test_no_c_source_exists_anywhere():
    """Phase 4.5 ends with frozen traces and NO port."""
    found = [os.path.join(d, f) for d, _s, fs in os.walk(EMB) for f in fs
             if f.endswith((".c", ".h", ".cpp", ".hpp", ".cc"))]
    assert not found, found


# ------------------------------------------------------------------- §20
def test_the_corpus_refuses_to_exist_without_its_preconditions():
    checks = _manifest()["preconditions"]
    for name in ("A_trust_mode_review", "B_staleness", "B_phase4_unaffected",
                 "C_consumer", "numeric_spec_written_before_c"):
        assert checks[name] is True, name


def test_the_builder_enforces_the_preconditions_itself():
    """A gate kept in a person's memory is not a gate."""
    src = open(os.path.join(EMB, "build_golden.py"), encoding="utf-8").read()
    assert "_preconditions" in src
    assert "STOP: Phase 4.5 preconditions not met" in src


# ------------------------------------------------------------- §21 / §27
def test_all_eleven_cases_are_frozen():
    m = _manifest()
    ids = {c["case_id"] for c in m["cases"]}
    assert ids == EXPECTED_CASES
    assert m["case_count"] == 11
    assert m["total_ticks"] == 13500


def test_every_case_names_its_source_config_input_and_output_hashes():
    m = _manifest()
    assert m["source_sha"] and m["config_hash"]
    assert m["trust_mode"] == "FLAT_V1_1"
    assert m["sequential"] == {"k": 0.5, "h": 500.0}
    assert m["output_schema_version"] == "1.1.0"
    for case in m["cases"]:
        assert case["input_hashes"], case["case_id"]
        assert len(case["tierA_series_sha256"]) == 64, case["case_id"]
        if case["kind"] == "SCENARIO":
            assert len(case["tierB_series_sha256"]) == 64, case["case_id"]
            assert case["ticks"] == 1500


def test_the_frozen_input_hashes_still_match_the_tree():
    """If a frozen input changed, the corpus describes a system that no
    longer exists. Rebuild it deliberately -- do not edit this test."""
    for rel, sha in _manifest()["frozen_input_hashes"].items():
        with open(os.path.join(ROOT, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == sha, rel


def test_every_stored_file_matches_its_recorded_file_hash():
    for case in _manifest()["cases"]:
        for kind in ("tierA", "tierB"):
            name = case.get(f"{kind}_file")
            if not name:
                continue
            with open(os.path.join(GOLD, name), "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
            assert got == case[f"{kind}_file_sha256"], (case["case_id"], kind)


def test_the_corpus_hash_covers_every_case():
    m = _manifest()
    want = hashlib.sha256("".join(sorted(
        c["tierA_series_sha256"] + (c["tierB_series_sha256"] or "")
        for c in m["cases"])).encode("utf-8")).hexdigest()
    assert open(os.path.join(GOLD, "CORPUS_SHA256"),
                encoding="utf-8").read().strip() == want


# ------------------------------------------------------------------- §23
def test_the_tier_a_encoding_is_lossless():
    """THE test for the compression. Reconstruct the full per-tick series
    from the run-length encoding and check it against the hash of the series
    that was actually computed."""
    for case in _manifest()["cases"]:
        if case["kind"] != "SCENARIO":
            continue
        runs = _lines(case["tierA_file"])
        rebuilt, h = [], hashlib.sha256()
        for run in runs:
            for j in range(run["n"]):
                row = {"t": round(run["t"] + 0.04 * j, 4), **run["v"]}
                rebuilt.append(row)
        assert len(rebuilt) == case["ticks"], case["case_id"]
        for row in rebuilt:
            h.update(_canon(row).encode("utf-8"))
            h.update(b"\n")
        assert h.hexdigest() == case["tierA_series_sha256"], case["case_id"]


def test_tier_a_carries_every_field_section_23_requires():
    runs = _lines("GNSS_FIX_LOSS.tierA.jsonl")
    body = runs[0]["v"]
    for key in ("assurance", "fn", "codes", "leader", "identifiable",
                "ambiguity", "support", "alarming", "fresh", "missing",
                "active_rel", "supp_rel", "supp_why"):
        assert key in body, key


def test_the_fix_loss_tier_a_records_the_result_the_layer_exists_for():
    runs = _lines("GNSS_FIX_LOSS.tierA.jsonl")
    at26 = [r for r in runs if r["t"] <= 26.0][-1]
    body = at26["v"]
    assert body["support"] == "NON_IDENTIFIABLE"
    assert body["leader"] == "nominal"
    assert body["identifiable"] is False
    assert body["fresh"]["gps"] is False
    for fn in ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION",
               "GEOFENCE_SUPPORT"):
        assert body["fn"][fn] == "INELIGIBLE", fn
    assert body["fn"]["INERTIAL_CONTINUATION"] == "ELIGIBLE"


def test_the_ledger_sequence_is_frozen_per_case():
    for case in _manifest()["cases"]:
        if case["kind"] != "SCENARIO":
            continue
        events = _lines(case["ledger_file"])
        assert len(events) == case["ledger_events"], case["case_id"]
        assert [e["seq"] for e in events] == list(range(len(events)))


def test_tier_c_fields_are_not_in_the_frozen_ledger():
    """A port must reproduce the event SEQUENCE, not this build's hashes."""
    for case in _manifest()["cases"]:
        if case["kind"] != "SCENARIO":
            continue
        for ev in _lines(case["ledger_file"]):
            for banned in ("event_id", "content_sha256",
                           "previous_event_hash", "software_sha"):
                assert banned not in ev, (case["case_id"], banned)


def test_the_ingest_cases_are_present_and_declare_no_tier_b():
    m = {c["case_id"]: c for c in _manifest()["cases"]}
    for name in ("BATTERY_SENTINEL", "MAG_SENTINEL"):
        case = m[name]
        assert case["kind"] == "INGEST"
        assert case["tierB_file"] is None
        assert "no trust tick" in case["note"]
        rows = _lines(case["tierA_file"])
        assert [r["stage"] for r in rows] == ["after_real_reading",
                                              "after_sentinel"]
        assert rows[0]["present"] is True
        assert rows[1]["present"] is False
        assert rows[1]["missing"] == "SENTINEL"


# ------------------------------------------------------------------- §24
def test_the_declared_tolerance_matches_the_spec():
    m = _manifest()
    assert m["tier_b_tolerance"] == {
        "trust": 1e-4, "alpha_beta_rel": 1e-4, "smoothed": 1e-3,
        "score": 1e-3, "posterior": 1e-3, "cusum_S": 0.5}
    spec = open(os.path.join(EMB, "NUMERIC_EQUIVALENCE_SPEC.md"),
                encoding="utf-8").read()
    for token in ("1e-4", "1e-3", "0.5 abs", "2⁻²⁴"):
        assert token in spec, token
    assert "never widened after seeing C" in spec


def test_the_tolerance_is_larger_than_its_derived_bound_everywhere():
    """Headroom, but bounded headroom: a tolerance below its own derivation
    would be a bound this system is known to violate."""
    derived = {"trust": 3.0e-5, "smoothed": 1.22e-4, "posterior": 6.2e-5,
               "cusum_S": 4.49e-2}
    declared = _manifest()["tier_b_tolerance"]
    for key, bound in derived.items():
        assert declared[key] > bound, key
        # 20x, not a tighter cap: `posterior` deliberately INHERITS the
        # score's 1e-3 rather than getting a bound of its own, because its
        # error is derived from the score's and the softmax contracts. That
        # puts it at 16x, which is a consequence of keeping the two
        # consistent rather than a separate decision.
        assert declared[key] < 20 * bound, (key, "headroom is excessive")


def test_tier_b_is_stored_with_its_full_series_hash():
    for case in _manifest()["cases"]:
        if case["kind"] != "SCENARIO":
            continue
        rows = _lines(case["tierB_file"])
        assert len(rows) == case["tierB_rows_stored"]
        assert case["tierB_encoding"] == "stride 10"
        assert len(rows) == case["ticks"] // 10
        for key in ("trust", "S", "posterior", "smoothed", "score"):
            assert key in rows[0], key


# ------------------------------------------------------------------- §26
def test_the_decision_margin_audit_enumerates_the_near_boundary_ticks():
    p = os.path.join(EMB, "DECISION_MARGIN_AUDIT.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    m = _manifest()
    assert len(rows) == m["near_boundary_ticks"] == 2
    assert m["near_boundary_fraction"] < 0.001
    by_case = {r["case"]: r for r in rows}
    assert set(by_case) == {"DUAL_IMU_FAILURE", "MAG_DEGRADED"}
    assert by_case["DUAL_IMU_FAILURE"]["reasons"] == "trust/att_emergency"
    assert by_case["MAG_DEGRADED"]["reasons"] == "trust/heading_caution"
    for r in rows:
        assert r["near_boundary"] == "True"


def test_no_tick_is_near_the_cusum_or_ranking_boundary():
    """Recorded because it is what makes the two flagged ticks tractable:
    only trust thresholds are in reach of the declared tolerance."""
    rows = list(csv.DictReader(open(
        os.path.join(EMB, "DECISION_MARGIN_AUDIT.csv"), encoding="utf-8")))
    tol = _manifest()["tier_b_tolerance"]
    for r in rows:
        assert float(r["d_cusum_h"]) > tol["cusum_S"], r
        assert float(r["d_score_margin"]) > tol["score"], r


def test_the_flagged_distances_really_are_within_tolerance():
    rows = {r["case"]: r for r in csv.DictReader(open(
        os.path.join(EMB, "DECISION_MARGIN_AUDIT.csv"), encoding="utf-8"))}
    tol = _manifest()["tier_b_tolerance"]["trust"]
    assert float(rows["DUAL_IMU_FAILURE"]["d_att_emergency"]) <= tol
    assert float(rows["MAG_DEGRADED"]["d_heading_caution"]) <= tol


# ------------------------------------------------------------------- §28
def test_phase_5_is_authorized_and_says_so_explicitly():
    t = open(os.path.join(EMB, "PHASE5_AUTHORIZATION.md"),
             encoding="utf-8").read()
    assert "PHASE5_READY:  YES" in t
    for gate in ("trust-mode review", "hard dropout", "API consumer",
                 "firewall", "golden corpus frozen", "numeric spec before C"):
        assert gate in t, gate
    assert "no C port exists" in t
    assert "M2" in t


def test_the_authorization_does_not_claim_a_maturity_move():
    t = open(os.path.join(EMB, "PHASE5_AUTHORIZATION.md"),
             encoding="utf-8").read()
    assert "does not move M2" in t
    assert "ZERO verified-clean hours" in t
    assert "Research maturity: **none established.**" in t


# ------------------------------------------------------------------- §19
def test_the_timeout_change_costs_nothing_per_tick():
    p = os.path.join(ROOT, "engineering", "v1_1", "PHASE4_5_COMPUTE.json")
    if not os.path.exists(p):
        pytest.skip("compute not measured")
    d = json.load(open(p, encoding="utf-8"))
    assert d["core_path_changed"] is False
    assert abs(d["per_tick_delta_us"]) < 0.2, d["per_tick_delta_us"]
    assert all(v["median_us"] < 100 for v in d["startup_us"].values())
    assert "NO TARGET-HARDWARE FIGURE EXISTS" in d["note"]
    assert "reporting_us" in d and "per_tick_us" in d
