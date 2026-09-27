"""XSYS-001-A2: the C4 correction is prospective, and nothing else moved.

`docs/research/XSYS_001_A2_C4_CORRECTION.md` corrects only the definition of
criterion C4 of XSYS-001-A1. It was specified, and its evaluation code, pilot
matrix and runner committed (4f3378f), BEFORE any fresh A2 pilot flew; A1 and
XSYS-001 stay byte-identical, including A1's failed C4 and its NOT ACCEPTED
status.

This test pins the three manifests and proves:
  * XSYS-001 and A1 are unchanged, every file of both still matches;
  * the A2 manifest binds both by SHA-256 and carries every earlier file;
  * the pre-pilot files are exactly those committed before the pilots;
  * C1, C2, C3 and C5 keep their A1 definitions (C1 NOT loosened);
  * the confirmatory matrix and order are A1's, unchanged; so are levels,
    thresholds, windows, hypotheses, endpoint, zero-WRONG, v2 and PX4;
  * the recorded decision follows from the recorded gates, and the A2
    executor can fly only if every gate passed;
  * no confirmatory data exist under a manifest that does not allow them.

Standard library only.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "research" / "xsys_confirmatory_001"
A1D, A2D = X / "amendment_a1", X / "amendment_a2"

XSYS_SHA256 = "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"
A1_SHA256 = "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"
#: XSYS-001-A2 manifest at the A2 freeze. Changing it is a further amendment.
A2_SHA256 = "d86e857d000d54502ec66bcbc83dbf679c55903aaf8ffe5e557e4514b1dded8f"

PREPILOT = {  # committed at 4f3378f, before any A2 pilot flew
    "research/xsys_confirmatory_001/amendment_a2/C4_A2_SPEC.json":
        "cec3e3ce1c74ec533b97dd95ef44b18517d0607c2ed7589b5cab3e72e539aaa1",
    "research/xsys_confirmatory_001/amendment_a2/PILOT_MATRIX_A2.csv":
        "221ab182933b26a7404405d32bd82b5b4a588c5f5f6b357930aff62ba3f0a830",
    "research/xsys_confirmatory_001/amendment_a2/analyze_a2.py":
        "a3dfe02c0d21522b572cf03e4e7b20929122270479b219e9223a4177fba3d07f",
    "research/xsys_confirmatory_001/amendment_a2/fly_pilots_a2.py":
        "a8b852d33b8d719b22731238d32a9d6947a7e403fd770e5990985bed4c38f22e",
    "research/xsys_confirmatory_001/amendment_a2/generate_pilots_a2.py":
        "7581782ce439c5c4cc7d809ef981555e0137e3772ead6918720f373e0fe1e642",
    "docs/research/XSYS_001_A2_C4_CORRECTION.md":
        "54fb4e0d500cfc2aff1e00c897c6ee9b2b5a47f25ddd92dfeaf15f29d055e678",
}
READY = "C1 C2 C3 C4-A2 C5 ALL PASS (guard tests still required)"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _json(p: Path):
    return json.loads(p.read_text())


def _const(path: Path, name: str):
    """A module-level constant, including one bound by tuple assignment."""
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if getattr(t, "id", None) == name:
                return ast.literal_eval(node.value)
            if isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for el, val in zip(t.elts, node.value.elts):
                    if getattr(el, "id", None) == name:
                        return ast.literal_eval(val)
    raise AssertionError(name)


# --- the chain -------------------------------------------------------------------

def test_xsys_001_and_a1_are_unchanged():
    xm, am = X / "prereg" / "FREEZE_MANIFEST.json", A1D / "FREEZE_MANIFEST_A1.json"
    assert _sha256(xm) == XSYS_SHA256 and _sha256(am) == A1_SHA256
    for m in (xm, am):
        changed = [r for r, h in _json(m)["frozen_files"].items() if _sha256(ROOT / r) != h]
        assert not changed, f"{m.name}: {changed}"
    a1_check = _json(A1D / "independence" / "DESIGN_CHECK.json")
    assert a1_check["criteria"]["C4"] is False
    assert a1_check["decision"] == "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK"


def test_a2_manifest_is_frozen_and_binds_the_chain():
    m_path = A2D / "FREEZE_MANIFEST_A2.json"
    assert _sha256(m_path) == A2_SHA256
    assert (A2D / "FREEZE_MANIFEST_A2.sha256").read_text().split()[0] == A2_SHA256
    m = _json(m_path)
    assert m["amends"] == "XSYS-001-A1"
    assert m["parent_manifest"] == {"path": "research/xsys_confirmatory_001/amendment_a1/FREEZE_MANIFEST_A1.json",
                                    "sha256": A1_SHA256}
    assert m["grandparent_manifest"] == {"path": "research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json",
                                         "sha256": XSYS_SHA256}
    for rel, h in _json(A1D / "FREEZE_MANIFEST_A1.json")["frozen_files"].items():
        assert m["frozen_files"][rel] == h, rel
    changed = [r for r, h in m["frozen_files"].items() if not (ROOT / r).exists() or _sha256(ROOT / r) != h]
    assert not changed, changed


def test_prepilot_files_are_the_ones_committed_before_the_pilots():
    m = _json(A2D / "FREEZE_MANIFEST_A2.json")
    assert m["prepilot_commit"] == "4f3378f" and m["prepilot_files"] == PREPILOT
    for rel, h in PREPILOT.items():
        assert _sha256(ROOT / rel) == h, rel


def test_every_a2_file_is_frozen():
    frozen = set(_json(A2D / "FREEZE_MANIFEST_A2.json")["frozen_files"])
    files = {str(p.relative_to(ROOT)) for p in A2D.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and "pilot_logs" not in p.parts
             and p.suffix in (".py", ".csv", ".json")
             and p.name not in ("FREEZE_MANIFEST_A2.json", "POST_FREEZE_CHECK_A2.json")}
    assert not files - frozen, sorted(files - frozen)


# --- only C4 changed ----------------------------------------------------------------

def test_c1_c2_c3_c5_are_unchanged():
    a1 = _json(A1D / "FREEZE_MANIFEST_A1.json")["frozen_files"]
    for rel in ("research/xsys_confirmatory_001/amendment_a1/independence/DIAGNOSTIC_SPEC.json",
                "research/xsys_confirmatory_001/amendment_a1/independence/independence_diagnostics.py",
                "research/xsys_confirmatory_001/amendment_a1/independence/MEMORY.json",
                "research/xsys_confirmatory_001/amendment_a1/generate_matrix_a1.py"):
        assert _sha256(ROOT / rel) == a1[rel], rel
    spec = _json(A1D / "independence" / "DIAGNOSTIC_SPEC.json")["acceptance_criteria"]
    assert spec["C1_no_shared_draws"].startswith("DX1 I(a,b) <= 0.001")
    analyze = A2D / "analyze_a2.py"
    assert _const(analyze, "C1_MAX") == 0.001, "C1 must not be loosened"
    assert _const(analyze, "S_SPACING") == 25.0 and _const(analyze, "TAU_MEM") == 0.332
    assert "import independence_diagnostics as ID" in analyze.read_text()
    c4a2 = _json(A2D / "C4_A2_SPEC.json")
    assert c4a2["scope"].startswith("C4 only")


def test_confirmatory_matrix_and_order_are_a1s_unchanged():
    m = _json(A2D / "FREEZE_MANIFEST_A2.json")
    a1 = _json(A1D / "FREEZE_MANIFEST_A1.json")["frozen_files"]
    for rel, h in m["confirmatory_matrix_unchanged_from_A1"].items():
        assert h == a1[rel] == _sha256(ROOT / rel), rel
    src = (A2D / "execution_a2" / "run_confirmatory_a2.py").read_text()
    assert 'A1 / "FLIGHT_MATRIX_A1.csv"' in src and 'A1 / "EXECUTION_ORDER_A1.csv"' in src
    assert 'X / "execution" / "xsys_run_trial.py"' in src
    assert 'default=str(A2 / "FREEZE_MANIFEST_A2.json")' in src


def test_science_is_unchanged():
    xs = _json(X / "prereg" / "FREEZE_MANIFEST.json")["frozen_files"]
    for rel in ("research/xsys_confirmatory_001/prereg/PREREG_CONFIG.json",
                "research/xsys_confirmatory_001/calibration/CALIBRATION.json",
                "research/xsys_confirmatory_001/pipeline/xsys_features.py",
                "research/xsys_confirmatory_001/pipeline/stage0_prepare.py",
                "research/xsys_confirmatory_001/pipeline/stage1_evidence.py",
                "research/xsys_confirmatory_001/pipeline/stage2_score.py",
                "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py",
                "csia/v2/localization.py", "csia/v2/evidence.py",
                "research/px4_actuator_effectiveness/patch/0001-sih-actuator-effectiveness.patch",
                "research/px4_actuator_effectiveness/config/logger_topics.txt",
                "docs/research/XSYS_001_PREREGISTRATION.md"):
        assert _sha256(ROOT / rel) == xs[rel], rel
    cfg = _json(X / "prereg" / "PREREG_CONFIG.json")
    assert cfg["design"]["fault_levels_eta"] == [0.95, 0.85, 0.75, 0.65, 0.55]
    assert "zero WRONG" in cfg["primary_endpoint"]["decision"]
    etas = {r["eta"] for r in csv.DictReader(open(A1D / "FLIGHT_MATRIX_A1.csv"))}
    assert etas == {"1.00", "0.95", "0.85", "0.75", "0.65", "0.55"}


# --- decision ------------------------------------------------------------------------

def test_decision_follows_from_the_recorded_gates():
    res = _json(A2D / "C4_A2_RESULTS.json")
    g = res["gates"]
    assert set(g) == {"A1_C1", "A1_C2", "A1_C3", "A1_C5", "fresh_C1", "fresh_C5", "C4_A2", "EV_A2"}
    assert (res["decision"] == READY) == all(g.values())
    assert res["decision"] in (READY, "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK")
    assert res["spec_sha256"] == PREPILOT["research/xsys_confirmatory_001/amendment_a2/C4_A2_SPEC.json"]
    assert res["pilot_matrix_sha256"] == PREPILOT["research/xsys_confirmatory_001/amendment_a2/PILOT_MATRIX_A2.csv"]
    assert _json(A2D / "FREEZE_MANIFEST_A2.json")["decision"] == res["decision"]
    src = (A2D / "execution_a2" / "run_confirmatory_a2.py").read_text()
    assert 'if not accepted and not a.dry_run:' in src and '"C4_A2_RESULTS.json"' in src


def test_pilots_are_nominal_only_and_never_confirmatory():
    pilots = list(csv.DictReader(open(A2D / "PILOT_MATRIX_A2.csv")))
    assert len(pilots) == 10 and all(p["onset_param"] == "SDLOG_DIRS_MAX" for p in pilots)
    confirmatory = {r["flight_id"] for r in csv.DictReader(open(A1D / "FLIGHT_MATRIX_A1.csv"))}
    assert not {p["pilot_id"] for p in pilots} & confirmatory
    for rec in (A2D / "pilot_logs").glob("A2P-*.json"):
        r = _json(rec)
        assert r["onset_param"] == "SDLOG_DIRS_MAX" and "NOMINAL-ONLY" in r["extra"]["purpose"]


def test_confirmatory_data_only_under_an_accepted_manifest():
    res = _json(A2D / "C4_A2_RESULTS.json")
    allowed = {A2_SHA256} if res["decision"] == READY else set()
    research = ROOT / "research"
    for camp in research.rglob("CAMPAIGN.json"):
        assert _json(camp).get("freeze_manifest_sha256") in allowed, camp
    for pat in ("XS1-*.json", "XS1A1-*.json"):
        for rec in research.rglob(pat):
            assert _json(rec).get("extra", {}).get("freeze_manifest_sha256") in allowed, rec
