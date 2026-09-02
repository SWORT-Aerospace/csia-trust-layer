"""Phase 4A gate: versioned trust mode and the promoted sequential bank.

The two that matter most:

  * LEGACY is the FROZEN class, not a copy of it -- so v1 replay cannot drift;
  * the substitution used by the batch path is always restored.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess

import numpy as np
import pytest

from csia.trust_engine.engine import EngineConfig, TrustCore
from csia.v1_1 import sequential as SEQ
from csia.v1_1.trust_mode import (DEFAULT_TRUST_MODE, FlatTrustCore,
                                  TrustMode, _core_class,
                                  attach_to_online_layer, make_core,
                                  make_engine, trust_mode_of)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")


def _regression():
    p = os.path.join(ENG, "TRUST_MODE_REGRESSION.json")
    if not os.path.exists(p):
        pytest.skip("Phase 4A regression not built")
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------- inherited integrity
def test_the_frozen_core_is_still_untouched():
    r = subprocess.run(["git", "diff", "--stat", "csia-v1.0-research-final",
                        "--", "csia/trust_engine", "csia/diagnosis",
                        "csia/runtime/online.py", "csia/runtime/failsafe.py",
                        "csia/scenarios.py", "csia/profiles.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag unavailable")
    assert r.stdout.strip() == "", r.stdout


# ------------------------------------------------------------- section 2
def test_the_default_mode_is_flat():
    assert DEFAULT_TRUST_MODE is TrustMode.FLAT_V1_1
    assert trust_mode_of(None) is TrustMode.FLAT_V1_1


def test_an_unknown_mode_raises_rather_than_falling_back():
    """A typo that silently selected the default would change which
    architecture produced a flight record."""
    with pytest.raises(ValueError):
        trust_mode_of("FLAT")
    with pytest.raises(ValueError):
        trust_mode_of("legacy")


def test_legacy_returns_the_frozen_class_itself_not_a_copy():
    core = make_core(TrustMode.LEGACY_NEIGHBOR_PROPAGATION, ["a", "b"])
    assert type(core) is TrustCore
    flat = make_core(TrustMode.FLAT_V1_1, ["a", "b"])
    assert type(flat) is FlatTrustCore
    assert isinstance(flat, TrustCore)


def test_the_flat_core_does_not_copy_the_frozen_step_body():
    """FLAT must SUBCLASS. A copied body would drift from the frozen core."""
    src = open(os.path.join(ROOT, "csia", "v1_1", "trust_mode.py"),
               encoding="utf-8").read()
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "FlatTrustCore":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "step":
                    body = fn.body
    assert body is not None
    # docstring + one assignment + one return. Anything more is a copy.
    stmts = [s for s in body if not (isinstance(s, ast.Expr)
                                     and isinstance(s.value, ast.Constant))]
    assert len(stmts) == 2, ast.dump(body[-1])
    assert isinstance(stmts[-1], ast.Return)
    for marker in ("rho_max", "alpha[n]", "w_nbr", "var_ratio.get"):
        assert marker not in src, marker


def test_the_mode_expressions_are_the_exact_production_line():
    assert (TrustMode.LEGACY_NEIGHBOR_PROPAGATION.neighbour_weight_expression
            == "w = float(gate_e) * self.trust[other]")
    assert (TrustMode.FLAT_V1_1.neighbour_weight_expression
            == "w = float(gate_e)")
    assert TrustMode.LEGACY_NEIGHBOR_PROPAGATION.propagates_trust
    assert not TrustMode.FLAT_V1_1.propagates_trust


def test_the_class_substitution_is_restored_even_on_an_exception():
    import csia.trust_engine.engine as eng
    real = eng.TrustCore
    with pytest.raises(RuntimeError):
        with _core_class(FlatTrustCore):
            assert eng.TrustCore is FlatTrustCore
            raise RuntimeError("boom")
    assert eng.TrustCore is real


def test_flat_neutralises_exactly_the_neighbour_factor():
    """With neighbour trust already at 1.0 the two modes must agree."""
    names = ["a", "b"]
    cfg = EngineConfig()
    legacy = make_core(TrustMode.LEGACY_NEIGHBOR_PROPAGATION, names, cfg)
    flat = make_core(TrustMode.FLAT_V1_1, names, cfg)
    legacy.trust = {n: 1.0 for n in names}
    args = ({"e": ("a", "b", 1.4, 1.0)}, {"a": (1.2, 1.0), "b": (0.9, 1.0)},
            {"a": 1.0, "b": 1.1}, {"a": 1.0, "b": 1.0},
            {"a": True, "b": True})
    r1 = legacy.step(*args)
    r2 = flat.step(*args)
    for n in names:
        assert r1[n]["trust"] == r2[n]["trust"]


def test_attaching_to_an_online_layer_swaps_only_the_core():
    from csia.runtime.online import OnlineTrustLayer
    layer = OnlineTrustLayer()
    names, cfg = layer.core.names, layer.core.cfg
    mode = attach_to_online_layer(layer, TrustMode.FLAT_V1_1)
    assert mode is TrustMode.FLAT_V1_1
    assert type(layer.core) is FlatTrustCore
    assert layer.core.names == names and layer.core.cfg is cfg
    assert layer.trust_mode is TrustMode.FLAT_V1_1

    layer2 = OnlineTrustLayer()
    attach_to_online_layer(layer2, TrustMode.LEGACY_NEIGHBOR_PROPAGATION)
    assert type(layer2.core) is TrustCore


def test_make_engine_carries_the_mode():
    from csia.trust_graph.graph import build_trust_graph
    eng = make_engine(None, build_trust_graph())
    assert eng.trust_mode is TrustMode.FLAT_V1_1


# ------------------------------------------------------------- section 3
def test_the_trust_mode_regression_passed_on_every_axis():
    d = _regression()
    assert d["verdict"] == "PASS", d["failures"]
    assert d["gate_A_legacy_reproduces_graph"] is True
    assert d["gate_B_default_reproduces_flat"] is True
    assert d["declared_trust_trajectory_tolerance"] == 0.0
    assert d["default_trust_mode"] == "FLAT_V1_1"
    assert len(d["mechanisms"]) == 9
    for mech, r in d["per_mechanism"].items():
        assert r["legacy_reproduces_graph_bitwise"] is True, mech
        assert r["flat_reproduces_flat_bitwise"] is True, mech
        assert r["legacy_max_abs_trust_delta"] == 0.0, mech
        assert r["flat_max_abs_trust_delta"] == 0.0, mech
        assert r["legacy_transitions_match"] is True, mech
        assert r["flat_transitions_match"] is True, mech


def test_the_default_mode_reproduces_the_phase_3b_t3_arm():
    """Phase 4 gate B. T3 = earliest of the flat-trust transition and the
    sequential alarm, so reproducing both components must reproduce T3.
    Checked against the Phase 3B results file, not against a copied list."""
    import csv
    p = os.path.join(ENG, "PHASE3B_ARCHITECTURE_RESULTS.csv")
    if not os.path.exists(p):
        pytest.skip("Phase 3B results unavailable")
    want = {}
    for row in csv.DictReader(open(p, encoding="utf-8")):
        if row["arm"] == "T3_TRUST_FLAT_PLUS_SEQ":
            want[row["mechanism"]] = (
                None if row["detection_censored"] == "True"
                else round(float(row["detection_response_s"]), 4))

    for mech, r in _regression()["per_mechanism"].items():
        trust_t = (r["transitions_flat"][0][0] if r["transitions_flat"]
                   else None)
        seq_idx = r["sequential_first_alarm_index"]
        seq_t = round(min(seq_idx.values()) * 0.04, 4) if seq_idx else None
        cands = [x for x in (trust_t, seq_t) if x is not None]
        got = round(min(cands), 4) if cands else None
        assert got == want[mech], (mech, got, want[mech])


def test_the_regression_reproduces_the_phase_3b_detection_times():
    """If these drift, Phase 3B's architecture decision no longer describes
    the shipped default. Fix the code, not the numbers."""
    d = _regression()["per_mechanism"]
    expected = {"GNSS_RAMP_SLOW": 32.48, "GNSS_RAMP_FAST": 24.36,
                "GNSS_FIX_LOSS": 26.0, "DUAL_IMU_FAILURE": 34.12,
                "MAG_DEGRADED": 30.04, "POWER_SAG": 33.72,
                "VIBRATION_ANOMALY": 34.16}
    for mech, first in expected.items():
        assert d[mech]["transitions_flat"][0][0] == first, mech
    for mech in ("CLEAN", "IMU0_BIAS_DRIFT"):
        assert d[mech]["transitions_flat"] == [], mech


# ------------------------------------------------------- the sequential bank
def test_the_cusum_constants_are_exact():
    assert SEQ.CUSUM_K == 0.5
    assert SEQ.CUSUM_H == 500.0
    assert SEQ.COVERED_NODES == ("battery", "gps", "mag", "motor_esc",
                                 "vibration")


def test_the_imu_nodes_have_no_sequential_residual():
    """Section 12 of the Phase 3B brief, carried into the runtime."""
    for n in ("imu0", "imu1", "baro"):
        assert n not in SEQ.IN_CONTROL
        assert n in SEQ.NO_RESIDUAL and SEQ.NO_RESIDUAL[n]
    assert not SEQ.CusumBank().covers("imu0")


def test_the_frozen_in_control_stats_are_the_clean_arm_stats():
    """They are constants so the runtime cannot re-estimate them mid-fault.
    Constants that nothing checks are constants that quietly go wrong."""
    import importlib.util
    from csia.scenarios import run_scenario
    # Loaded BY PATH, as every sibling v1.1 test does. A bare `import
    # b4_verify` after a sys.path insert reads to the CI dependency scanner
    # as an undeclared PyPI package, and it caught exactly that here.
    spec = importlib.util.spec_from_file_location(
        "b4_verify", os.path.join(ENG, "ablation", "b4_verify.py"))
    B4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B4)
    _t, _f, td, _h, _d = run_scenario("clean")
    for n, (lam, act) in B4.lam_streams(td).items():
        v = lam[act]
        if v.size < 2 or v.std(ddof=1) <= 1e-12:
            assert n not in SEQ.IN_CONTROL, n
            continue
        mu0, sd0 = SEQ.IN_CONTROL[n]
        assert float(v.mean()) == mu0, n
        assert float(v.std(ddof=1)) == sd0, n


def test_a_gated_out_tick_neither_advances_nor_resets_the_statistic():
    """Absence of evidence is not evidence of change."""
    bank = SEQ.CusumBank()
    mu0, sd0 = SEQ.IN_CONTROL["gps"]
    for _ in range(50):
        bank.update("gps", mu0 + 10 * sd0, True)
    before = bank.S["gps"]
    assert before > 0
    bank.update("gps", 0.0, False)
    assert bank.S["gps"] == before


def test_the_online_bank_reproduces_the_batch_statistic():
    d = _regression()["per_mechanism"]
    for mech, r in d.items():
        assert r["sequential_online_equals_batch"] is True, mech
    assert d["GNSS_RAMP_FAST"]["sequential_first_alarm_index"] == {"gps": 529}
    assert d["CLEAN"]["sequential_first_alarm_index"] == {}


def test_the_bank_never_reports_a_node_it_does_not_cover():
    bank = SEQ.CusumBank()
    out = bank.step({"imu0": (99.0, 1.0), "gps": (0.5, 1.0)},
                    {"imu0": True, "gps": True})
    assert "imu0" not in out
    assert "gps" in out


def test_the_bank_state_is_serialisable_and_names_its_constants():
    st = SEQ.CusumBank().state()
    assert st["k"] == 0.5 and st["h"] == 500.0
    assert set(st["S"]) == set(SEQ.COVERED_NODES)
    json.dumps(st)


# --------------------------------------------------------------- section 4
def test_the_architecture_freeze_records_what_phase_5_ports():
    p = os.path.join(ENG, "V1_1_ARCHITECTURE_FREEZE.json")
    if not os.path.exists(p):
        pytest.skip("freeze not built")
    d = json.load(open(p, encoding="utf-8"))
    assert d["trust_mode_default"] == "FLAT_V1_1"
    assert d["sequential"]["k"] == 0.5 and d["sequential"]["h"] == 500.0
    assert d["sequential"]["covered_nodes"] == list(SEQ.COVERED_NODES)
    assert d["output_schema_version"] == "1.1.0"
    assert d["frozen_v1_tag"] == "csia-v1.0-research-final"
    assert set(d["runtime_module_hashes"]) == {
        "csia/v1_1/__init__.py", "csia/v1_1/sequential.py",
        "csia/v1_1/trust_mode.py"}


def test_the_freeze_document_states_what_it_does_not_freeze():
    t = open(os.path.join(ENG, "V1_1_ARCHITECTURE_FREEZE.md"),
             encoding="utf-8").read()
    assert "Numerical golden-trace values" in t
    assert "NOT IMPLEMENTED — MODEL ADEQUACY TEST" in t
    assert "no target-hardware figure exists" in t.lower()


def test_no_novelty_language_in_the_phase_4a_documents():
    import re
    banned = (r"\bnovel\b", r"\bnovelty\b", r"\bbreakthrough\b",
              r"\bfirst-ever\b")
    denials = ("no ", "not ", "never", "none", "cannot", "warranted",
               "is not a", "prior art", "claimed")
    for fn in ("TRUST_MODE_VERSIONING.md", "V1_1_ARCHITECTURE_FREEZE.md"):
        lines = open(os.path.join(ENG, fn),
                     encoding="utf-8").read().lower().splitlines()
        for i, line in enumerate(lines):
            for w in banned:
                if not re.search(w, line):
                    continue
                window = " ".join(lines[max(0, i - 1):i + 2])
                assert any(k in window for k in denials), (fn, w, line[:120])


def test_trust_history_shapes_are_unchanged_between_modes():
    from csia.scenarios import run_scenario
    from csia.trust_graph.graph import build_trust_graph
    _t, _f, td, _h, _d = run_scenario("clean")
    a = make_engine(TrustMode.FLAT_V1_1, build_trust_graph()).run(td)
    b = make_engine(TrustMode.LEGACY_NEIGHBOR_PROPAGATION,
                    build_trust_graph()).run(td)
    assert a.trust.shape == b.trust.shape
    assert a.names == b.names
    assert not np.array_equal(a.trust, b.trust), (
        "clean-arm trajectories are identical in both modes; the ablation "
        "would then be measuring nothing")
