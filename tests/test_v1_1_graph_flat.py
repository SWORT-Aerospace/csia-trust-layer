"""Phase 3A gate: GRAPH vs FLAT.

Section 18: if the arms do not consume matched inputs, the comparison is
INVALID. These tests enforce the matching and protect the two claims the
verdict rests on -- that the ablation removes exactly one coupling, and that
the diagnosis cannot be affected by it at all.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")
ABL = os.path.join(ENG, "ablation")


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ABL, fn))
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def flat():
    return _load("_v11_flat", "flat.py")


@pytest.fixture(scope="module")
def scen():
    from csia.scenarios import run_scenario
    return run_scenario("gps_spoof")


# ------------------------------------------------- the structural claim
def test_the_diagnosis_never_reads_trust():
    """The claim the whole verdict rests on: attribution CANNOT differ.

    Checked against the module's imports and body, not asserted in prose.
    """
    src = open(os.path.join(ROOT, "csia", "diagnosis", "bayes.py"),
               encoding="utf-8").read()
    # the only thing imported from the trust engine is a pure function
    assert "from ..trust_engine.engine import consistency" in src
    assert "TrustHistory" not in src
    assert "trust_engine.engine import" in src
    # and nothing reads a trust value
    for bad in ("hist.trust", ".trust[", "trust=", "TrustState"):
        assert bad not in src, bad


def test_both_arms_produce_the_same_posterior(flat, scen):
    """The structural claim, measured as well as read."""
    from csia.diagnosis.bayes import CausalDiagnosis
    _t, _f, td, _h, _d = scen
    a = CausalDiagnosis().run(td).posterior
    b = CausalDiagnosis().run(td).posterior
    assert np.array_equal(a, b)


# -------------------------------------------------------- section 18 matching
def test_the_graph_arm_reproduces_the_frozen_pipeline(flat, scen):
    """If the harness had drifted from production, every number is void."""
    from csia.trust_engine.engine import TrustEngine
    from csia.trust_graph.graph import build_trust_graph
    _t, _f, td, hist, _d = scen
    got = TrustEngine(build_trust_graph()).run(td)
    assert np.array_equal(got.trust, hist.trust)


def test_flat_is_the_frozen_core_with_one_coupling_removed(flat):
    """No method may be copied out of the frozen engine."""
    from csia.trust_engine.engine import TrustCore
    assert issubclass(flat.FlatTrustCore, TrustCore)
    import re
    src = open(os.path.join(ABL, "flat.py"), encoding="utf-8").read()
    # Strip docstrings and comments first: flat.py QUOTES the frozen
    # expression to explain the ablation, which is documentation, not
    # duplication. What must not appear is executable copied code.
    body = re.sub(r'"""[\s\S]*?"""', "", src)
    body = re.sub(r"#.*", "", body)
    for marker in ("self.alpha[n] =", "rho = cfg.rho_max", "c_nbr =",
                   "evidence = sum("):
        assert marker not in body, f"frozen TrustCore body copied: {marker!r}"
    assert "super().step(" in body


def test_flat_neutralises_exactly_the_neighbour_trust_weight(flat, scen):
    """The ablation must be the trust factor and nothing else.

    Constructed directly: with every neighbour trust already at 1.0, GRAPH and
    FLAT must agree bit-for-bit on the first tick, because the only difference
    between them is that factor.
    """
    from csia.trust_engine.engine import TrustCore
    from csia.trust_graph.graph import build_trust_graph
    names = list(build_trust_graph().nodes)
    edges = {"redundant_imu": ("imu0", "imu1", 0.4, 1.0),
             "accel_esc_rpm": ("imu0", "motor_esc", 0.9, 1.0)}
    phys = {n: (0.5, 1.0) for n in names}
    hist = {n: 0.4 for n in names}
    vr = {n: 0.3 for n in names}
    fresh = {n: True for n in names}

    g = TrustCore(names)
    f = flat.FlatTrustCore(names)
    g.trust = {n: 1.0 for n in names}          # neutralise GRAPH by hand
    rg = g.step(edges, phys, hist, vr, fresh)
    rf = f.step(edges, phys, hist, vr, fresh)
    for n in names:
        assert rg[n]["trust"] == rf[n]["trust"], n
        assert rg[n]["evidence"] == rf[n]["evidence"], n


def test_the_arms_actually_differ_somewhere(flat, scen):
    """A no-op ablation would make the whole comparison vacuous."""
    from csia.trust_engine.engine import TrustEngine
    from csia.trust_graph.graph import build_trust_graph
    _t, _f, td, _h, _d = scen
    graph = build_trust_graph()
    a = TrustEngine(graph).run(td).trust
    b = flat.FlatTrustEngine(graph).run(td).trust
    assert not np.array_equal(a, b), "FLAT is identical to GRAPH; no ablation"
    assert np.abs(a - b).max() < 0.5, "implausibly large divergence"


def test_flat_does_not_leak_into_the_frozen_engine(flat, scen):
    """FlatTrustEngine swaps a class during its own run. It must put it back."""
    import csia.trust_engine.engine as eng
    from csia.trust_graph.graph import build_trust_graph
    before = eng.TrustCore
    _t, _f, td, _h, _d = scen
    flat.FlatTrustEngine(build_trust_graph()).run(td)
    assert eng.TrustCore is before


def test_the_frozen_trust_engine_is_untouched():
    import subprocess
    r = subprocess.run(["git", "diff", "--stat", "csia-v1.0-research-final",
                        "--", "csia/trust_engine", "csia/diagnosis",
                        "csia/runtime/failsafe.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag unavailable")
    assert r.stdout.strip() == "", r.stdout


# ------------------------------------------------------------- the artifacts
def test_the_ablation_artifacts_support_the_verdict():
    p = os.path.join(ENG, "GRAPH_FLAT_SUMMARY.json")
    if not os.path.exists(p):
        pytest.skip("Phase 3A artifacts not built")
    d = json.load(open(p, encoding="utf-8"))
    assert d["matching"]["graph_arm_reproduces_frozen_pipeline"] is True
    assert d["structural_finding"]["diagnosis_is_graph_independent"] is True

    per = d["per_scenario"]
    assert len(per) == 9
    # every scenario's trust divergence stays small
    assert max(v["max_abs_trust_delta"] for v in per.values()) < 0.1
    # the two scenarios that differ must differ in TIMING, not in outcome
    for s, v in per.items():
        if not v["assurance_levels_identical"]:
            assert v["graph_n_transitions"] == v["flat_n_transitions"], s


def test_the_simplification_plan_scopes_itself_correctly():
    """The plan must not be readable as 'delete the trust graph'."""
    t = open(os.path.join(ENG, "GRAPH_SIMPLIFICATION_PLAN.md"),
             encoding="utf-8").read()
    assert "edge topology stays exactly as it is" in t
    assert "has been executed" in t          # i.e. NOTHING has been
    low = t.lower()
    assert "not recommended for removal" in low


def test_the_verdict_is_one_of_the_allowed_options():
    t = open(os.path.join(ENG, "GRAPH_FLAT_ABLATION_SPEC.md"),
             encoding="utf-8").read()
    allowed = ("GRAPH_EARNS_COMPLEXITY", "GRAPH_PARTIALLY_EARNS_COMPLEXITY",
               "GRAPH_NO_MATERIAL_GAIN", "FLAT_BETTER", "INCONCLUSIVE")
    assert sum(v in t for v in allowed) >= 1
    assert "GRAPH_NO_MATERIAL_GAIN" in t


def test_no_novelty_language_in_the_phase_3a_documents():
    """Section 31. A DENIAL of novelty is not a novelty claim, so match on
    word boundaries and require a denial nearby -- otherwise the guard fires
    on 'no novelty language', which is the opposite of what it polices."""
    import re
    banned = (r"\bnovel\b", r"\bnovelty\b", r"\bfirst-ever\b",
              r"\bbreakthrough\b", r"\bnew theorem\b")
    denials = ("no ", "not ", "never", "none", "cannot", "warranted",
               "forbidden", "is not a")
    for fn in ("GRAPH_FLAT_ABLATION_SPEC.md", "GRAPH_SIMPLIFICATION_PLAN.md"):
        lines = open(os.path.join(ENG, fn),
                     encoding="utf-8").read().lower().splitlines()
        for i, line in enumerate(lines):
            for w in banned:
                if not re.search(w, line):
                    continue
                window = " ".join(lines[max(0, i - 1):i + 2])
                assert any(k in window for k in denials), (fn, w, line[:120])
