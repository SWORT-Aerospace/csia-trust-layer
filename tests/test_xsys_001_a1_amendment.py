"""XSYS-001-A1: the pre-data nuisance amendment cannot change silently, and it
changed nothing but the nuisance generation.

`docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md` amends XSYS-001 before
any confirmatory flight: the nuisance conditions of the original design read
the same simulator noise stream at overlapping simulated times, so they were
not independent units. The amendment moves each condition to its own segment
of that stream (pre-arm dwell) and leaves everything else frozen.

This test pins the amendment manifest and proves the chain:
  * the XSYS-001 preregistration, manifest and frozen files are byte-identical;
  * the amendment manifest binds the XSYS-001 manifest by SHA-256 and lists
    every XSYS-001 frozen file with the same hash;
  * hypotheses, levels, thresholds, windows, endpoint, decision rule, v2 and
    the PX4 apparatus are the XSYS-001 files, unchanged;
  * the amended matrix and order regenerate byte for byte and keep the
    matched-pair structure; the executor reads them; stage 1 stays blind;
  * the amendment's own acceptance rule failed criterion C4, and that
    decision binds: the A1 executor refuses to fly, and no campaign may carry
    the XSYS-001 or the XSYS-001-A1 manifest.

Standard library only.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "research" / "xsys_confirmatory_001"
A1 = X / "amendment_a1"
PARENT = X / "prereg" / "FREEZE_MANIFEST.json"
MANIFEST_A1 = A1 / "FREEZE_MANIFEST_A1.json"

#: XSYS-001 manifest (unchanged by the amendment).
PARENT_SHA256 = "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"
#: XSYS-001-A1 manifest at the amendment freeze. Changing it is a further
#: amendment, not a test fix.
A1_MANIFEST_SHA256 = "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _csv_text(rows) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _rows(p: Path):
    return list(csv.DictReader(open(p)))


def _parent():
    return json.loads(PARENT.read_text())


def _a1():
    return json.loads(MANIFEST_A1.read_text())


# --- 1-3: the chain -------------------------------------------------------------

def test_original_preregistration_and_manifest_are_byte_identical():
    assert _sha256(PARENT) == PARENT_SHA256
    assert (X / "prereg" / "FREEZE_MANIFEST.sha256").read_text().split()[0] == PARENT_SHA256
    doc = "docs/research/XSYS_001_PREREGISTRATION.md"
    assert _sha256(ROOT / doc) == _parent()["frozen_files"][doc]
    changed = [r for r, h in _parent()["frozen_files"].items() if _sha256(ROOT / r) != h]
    assert not changed, f"XSYS-001 frozen files changed: {changed}"


def test_amendment_manifest_is_the_frozen_one_and_binds_the_original():
    assert _sha256(MANIFEST_A1) == A1_MANIFEST_SHA256, "the amendment manifest changed"
    assert (A1 / "FREEZE_MANIFEST_A1.sha256").read_text().split()[0] == A1_MANIFEST_SHA256
    m = _a1()
    assert m["amends"] == "XSYS-001"
    assert m["parent_manifest"] == {"path": "research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json",
                                    "sha256": PARENT_SHA256}
    for rel, h in _parent()["frozen_files"].items():
        assert m["frozen_files"].get(rel) == h, f"{rel} is not carried unchanged into the amendment"
    assert m["frozen_files"]["research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json"] == PARENT_SHA256
    assert m["logger_config_file"] == _parent()["logger_config_file"] and m["px4"] == _parent()["px4"]


def test_every_amendment_file_matches_its_manifest():
    changed = [r for r, h in _a1()["frozen_files"].items() if not (ROOT / r).exists() or _sha256(ROOT / r) != h]
    assert not changed, f"XSYS-001-A1 frozen files changed: {changed}"


def test_amendment_covers_every_amendment_file():
    """Pilot logs are covered through pilot_logs/SHA256SUMS, which is frozen."""
    frozen = set(_a1()["frozen_files"])
    code = {str(p.relative_to(ROOT)) for p in A1.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and "pilot_logs" not in p.parts
            and p.suffix in (".py", ".csv", ".json")
            and p.name not in ("FREEZE_MANIFEST_A1.json", "POST_FREEZE_CHECK_A1.json")}
    assert not code - frozen, f"amendment files outside the freeze: {sorted(code - frozen)}"


# --- 4-5, 16: matrix, order, executor ---------------------------------------------

def test_amended_matrix_and_order_regenerate_byte_for_byte():
    gen = _load("xsys_generate_matrix_a1", A1 / "generate_matrix_a1.py")
    flights, analysis, order = gen.build()
    assert _csv_text(flights) == (A1 / "FLIGHT_MATRIX_A1.csv").read_text()
    assert _csv_text(analysis) == (A1 / "ANALYSIS_MATRIX_A1.csv").read_text()
    rows = _rows(A1 / "EXECUTION_ORDER_A1.csv")
    assert [r["flight_id"] for r in rows] == order
    assert all(r["order_key_sha256"] == hashlib.sha256(f"{gen.SEED_A1}/order/{r['flight_id']}".encode()).hexdigest()
               for r in rows)
    assert gen.SEED_A1 != _load("xsys_generate_matrix", X / "prereg" / "generate_matrix.py").SEED


def test_amended_design_constants_come_from_the_frozen_rule():
    gen = _load("xsys_generate_matrix_a1", A1 / "generate_matrix_a1.py")
    mem = json.loads((A1 / "independence" / "MEMORY.json").read_text())
    assert abs(gen.TAU_MEM_S - mem["DX6_memory"]["tau_mem_s"]) < 1e-9
    assert gen.S_SEPARATION_S == mem["separation"]["S_s"] >= 20.0 + gen.TAU_MEM_S
    check = json.loads((A1 / "independence" / "DESIGN_CHECK.json").read_text())
    assert check["S_s"] == gen.S_SEPARATION_S and check["tau_mem_s"] == gen.TAU_MEM_S


def test_acceptance_decision_is_recorded_and_blocks_execution():
    """The amendment's own frozen criteria decided, and the decision binds:
    C4 failed, so XSYS-001-A1 is frozen but not executable."""
    check = json.loads((A1 / "independence" / "DESIGN_CHECK.json").read_text())
    assert check["criteria"] == {"C1": True, "C2": True, "C3": True, "C4": False, "C5": True}
    assert check["decision"] == "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK"
    cfg = json.loads((A1 / "A1_CONFIG.json").read_text())
    assert cfg["status"].startswith("FROZEN - NOT ACCEPTED FOR EXECUTION")
    src = (A1 / "execution_a1" / "run_confirmatory_a1.py").read_text()
    assert 'if not accepted and not a.dry_run:' in src and 'DESIGN_CHECK.json' in src
    posthoc = json.loads((A1 / "independence" / "C4_POSTHOC_EXPLORATORY.json").read_text())
    assert posthoc["label"].startswith("POST-HOC / EXPLORATORY")


def test_every_condition_reads_its_own_noise_segment():
    rows = _rows(A1 / "FLIGHT_MATRIX_A1.csv")
    gen = _load("xsys_generate_matrix_a1", A1 / "generate_matrix_a1.py")
    by_cond = {}
    for r in rows:
        by_cond.setdefault(r["nuisance_id"], []).append(r)
    onsets = []
    for cid, rs in by_cond.items():
        keys = {(r["heading_deg"], r["t_arm_s"], r["t_onset_s"], r["t_end_s"], r["noise_segment_id"]) for r in rs}
        assert len(keys) == 1, f"{cid}: its flights do not share one schedule"
        r = rs[0]
        assert float(r["t_onset_s"]) - float(r["t_arm_s"]) == 20.0
        onsets.append(float(r["t_onset_s"]))
    onsets.sort()
    assert min(b - a for a, b in zip(onsets, onsets[1:])) >= 20.0 + gen.TAU_MEM_S
    assert len({r["noise_segment_id"] for r in rows}) == 11


def test_matched_pairs_and_levels_are_unchanged():
    old_f, new_f = _rows(X / "prereg" / "FLIGHT_MATRIX.csv"), _rows(A1 / "FLIGHT_MATRIX_A1.csv")
    old_a, new_a = _rows(X / "prereg" / "ANALYSIS_MATRIX.csv"), _rows(A1 / "ANALYSIS_MATRIX_A1.csv")
    assert len(new_f) == len(old_f) == 66 and len(new_a) == len(old_a) == 121
    assert sorted({r["eta"] for r in new_f}) == sorted({r["eta"] for r in old_f})
    assert sorted({r["heading_deg"] for r in new_f}) == sorted({r["heading_deg"] for r in old_f})
    strip = lambda s: s.split("-", 1)[1]  # noqa: E731  drop the id prefix
    for key in ("kind", "eta", "nuisance_id"):
        assert [(strip(r["analysis_id"]), r[key]) for r in new_a] == [(strip(r["analysis_id"]), r[key]) for r in old_a]
    flights = {r["flight_id"]: r for r in new_f}
    for r in new_a:
        if r["kind"] == "B":
            a, nb = flights[r["matched_a_flight_id"]], flights[r["source_flight_id"]]
            assert a["condition"] == "A" and nb["condition"] == "NB" and a["eta"] == r["eta"]
            assert a["nuisance_id"] == nb["nuisance_id"] == r["nuisance_id"]
            assert a["t_onset_s"] == nb["t_onset_s"] and a["heading_deg"] == nb["heading_deg"]


def test_order_does_not_reveal_role_level_or_segment():
    flights = {r["flight_id"]: r for r in _rows(A1 / "FLIGHT_MATRIX_A1.csv")}
    seq = [flights[r["flight_id"]] for r in _rows(A1 / "EXECUTION_ORDER_A1.csv")]

    def spearman(xs):
        n = len(xs)
        rk = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: (xs[i], i)))}
        r = [rk[i] for i in range(n)]
        d2 = sum((r[i] - i) ** 2 for i in range(n))
        return 1 - 6 * d2 / (n * (n * n - 1))
    for field in ("eta", "noise_segment_id"):
        vals = [x[field] for x in seq]
        assert abs(spearman(vals)) < 0.3, field
    roles = [x["condition"] for x in seq]
    assert "NB" in roles[:33] and "NB" in roles[33:]


def test_executor_flies_the_amended_matrix_with_the_frozen_driver():
    src = (A1 / "execution_a1" / "run_confirmatory_a1.py").read_text()
    assert 'A1 / "FLIGHT_MATRIX_A1.csv"' in src and 'A1 / "EXECUTION_ORDER_A1.csv"' in src
    assert '"FLIGHT_MATRIX.csv"' not in src and '"EXECUTION_ORDER.csv"' not in src
    assert 'X / "execution" / "xsys_run_trial.py"' in src
    assert 'default=str(A1 / "FREEZE_MANIFEST_A1.json")' in src


# --- 6-14: nothing but the nuisance changed ------------------------------------------

UNCHANGED = {
    "hypotheses, endpoints, taxonomy, decision rule (config)": "research/xsys_confirmatory_001/prereg/PREREG_CONFIG.json",
    "thresholds": "research/xsys_confirmatory_001/calibration/CALIBRATION.json",
    "evidence definitions and windows": "research/xsys_confirmatory_001/pipeline/xsys_features.py",
    "case-B construction, checks, exclusions": "research/xsys_confirmatory_001/pipeline/stage0_prepare.py",
    "blinded evidence": "research/xsys_confirmatory_001/pipeline/stage1_evidence.py",
    "primary endpoint, zero-WRONG, bound, Holm": "research/xsys_confirmatory_001/pipeline/stage2_score.py",
    "attribution semantics (adapter)": "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py",
    "sample-size rule": "research/xsys_confirmatory_001/prereg/power_analysis.py",
    "v2 localization": "csia/v2/localization.py",
    "v2 evidence": "csia/v2/evidence.py",
    "PX4 patch": "research/px4_actuator_effectiveness/patch/0001-sih-actuator-effectiveness.patch",
    "logger configuration": "research/px4_actuator_effectiveness/config/logger_topics.txt",
    "trial driver": "research/xsys_confirmatory_001/execution/xsys_run_trial.py",
    "preregistration document": "docs/research/XSYS_001_PREREGISTRATION.md",
}


def test_frozen_science_is_the_xsys_001_files_unchanged():
    parent, a1 = _parent()["frozen_files"], _a1()["frozen_files"]
    for what, rel in UNCHANGED.items():
        assert rel in parent, f"{what}: {rel} was not frozen by XSYS-001"
        assert _sha256(ROOT / rel) == parent[rel] == a1[rel], f"{what} changed: {rel}"


def test_frozen_values_are_unchanged():
    cfg = json.loads((X / "prereg" / "PREREG_CONFIG.json").read_text())
    assert cfg["design"]["fault_levels_eta"] == [0.95, 0.85, 0.75, 0.65, 0.55]
    assert cfg["design"]["n_conditions"] == 11
    assert cfg["windows_s"] == {"T0": [-5.0, 0.0], "T1": [0.0, 0.2], "T2": [0.2, 2.0], "T3": [10.0, 15.0]}
    pe = cfg["primary_endpoint"]
    assert pe["alpha_one_sided"] == 0.05 and pe["null_rate"] == 0.5
    assert "zero WRONG" in pe["decision"] and "lower95 > 0.5" in pe["decision"]
    gen = _load("xsys_generate_matrix_a1", A1 / "generate_matrix_a1.py")
    assert list(gen.LEVELS) == cfg["design"]["fault_levels_eta"] and gen.N_CONDITIONS == 11
    assert {k: list(v) for k, v in gen.WINDOWS.items()} == cfg["windows_s"]
    power = json.loads((A1 / "POWER_A1.json").read_text())
    assert power["identical_to_frozen_POWER_json"] and power["decision_N"] == 11


# --- 19: blinding ----------------------------------------------------------------

def test_stage1_is_unchanged_and_blind_and_wrappers_only_redirect_paths():
    s1 = X / "pipeline" / "stage1_evidence.py"
    assert _sha256(s1) == _parent()["frozen_files"]["research/xsys_confirmatory_001/pipeline/stage1_evidence.py"]
    text = s1.read_text()
    for t in ("--key", "--qc", "truth", "analysis_id", "pair_id", "matched_a", "XS1A1", "noise_segment"):
        assert t not in text
    paths = (A1 / "pipeline_a1" / "a1_paths.py").read_text()
    tree = ast.parse(paths)
    remap = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "REMAP")
    assert set(remap) == {"research/xsys_confirmatory_001/prereg/FLIGHT_MATRIX.csv",
                          "research/xsys_confirmatory_001/prereg/ANALYSIS_MATRIX.csv"}
    for w in ("stage0_prepare_a1.py", "stage2_score_a1.py"):
        body = (A1 / "pipeline_a1" / w).read_text()
        assert "a1_paths.install()" in body and body.count("def ") == 0


# --- 15: no confirmatory data -------------------------------------------------------

def test_neither_superseded_nor_unaccepted_design_is_ever_flown():
    """XSYS-001's nuisance design is refuted (its conditions share noise) and
    XSYS-001-A1 is not accepted for execution, so no campaign and no trial
    record may ever carry either manifest. A later amendment that is accepted
    carries its own manifest and its own guard."""
    forbidden = {PARENT_SHA256, A1_MANIFEST_SHA256}
    research = ROOT / "research"
    for camp in research.rglob("CAMPAIGN.json"):
        assert json.loads(camp.read_text()).get("freeze_manifest_sha256") not in forbidden, camp
    for pat in ("XS1-*.json", "XS1A1-*.json"):
        for rec in research.rglob(pat):
            assert json.loads(rec.read_text()).get("extra", {}).get("freeze_manifest_sha256") not in forbidden, rec
