"""XSYS-001: the preregistration cannot change silently.

`docs/research/XSYS_001_PREREGISTRATION.md` freezes the first confirmatory
cross-system experiment before any confirmatory flight exists. Its manifest,
`research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json`, holds the
SHA-256 of every file that defines the experiment. This test holds the
manifest's own SHA-256, so every route to moving a goalpost fails here:

  * editing a frozen file (threshold, window, rule, matrix, script)
      -> test_every_frozen_file_matches_the_manifest
  * re-freezing with a new manifest
      -> test_manifest_is_the_frozen_one (the constant below must be edited,
         in a diff anyone can see)
  * regenerating the matrix or the order differently
      -> test_matrices_regenerate_byte_for_byte, test_execution_order_*
  * letting the code drift from the declared configuration
      -> test_code_constants_match_the_declared_configuration
  * letting the blinded stage see a label
      -> test_blind_stage_cannot_name_a_label_source
  * producing "confirmatory" data under another protocol
      -> test_confirmatory_data_are_bound_to_this_manifest

Standard library only: the research pipeline's numerical dependencies are
not needed to check a freeze.
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
PREREG = X / "prereg"
MANIFEST = PREREG / "FREEZE_MANIFEST.json"

#: SHA-256 of FREEZE_MANIFEST.json at the freeze commit. Changing it is an
#: amendment of the preregistration, not a test fix.
FROZEN_MANIFEST_SHA256 = "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module_constant(path: Path, name: str):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def _generator():
    spec = importlib.util.spec_from_file_location("xsys_generate_matrix", PREREG / "generate_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _csv_text(rows) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


# --- the freeze -------------------------------------------------------------

def test_manifest_is_the_frozen_one():
    assert _sha256(MANIFEST) == FROZEN_MANIFEST_SHA256, (
        "FREEZE_MANIFEST.json is not the manifest frozen for XSYS-001. A changed "
        "protocol is a new preregistration, not an edit of this one.")
    recorded = (PREREG / "FREEZE_MANIFEST.sha256").read_text().split()[0]
    assert recorded == FROZEN_MANIFEST_SHA256


def test_every_frozen_file_matches_the_manifest():
    frozen = json.loads(MANIFEST.read_text())["frozen_files"]
    changed = [rel for rel, want in frozen.items()
               if not (ROOT / rel).exists() or _sha256(ROOT / rel) != want]
    assert not changed, f"frozen XSYS-001 files changed after the freeze: {changed}"


def test_manifest_covers_the_whole_protocol():
    frozen = set(json.loads(MANIFEST.read_text())["frozen_files"])
    code = {str(p.relative_to(ROOT)) for d in ("pipeline", "execution", "calibration", "prereg")
            for p in (X / d).iterdir() if p.suffix in (".py", ".csv") or p.name in
            ("CALIBRATION.json", "PREREG_CONFIG.json", "POWER.json")}
    assert not code - frozen, f"protocol files outside the freeze: {sorted(code - frozen)}"
    for must in ("docs/research/XSYS_001_PREREGISTRATION.md", "csia/v2/localization.py", "csia/v2/evidence.py",
                 "research/px4_actuator_effectiveness/patch/0001-sih-actuator-effectiveness.patch",
                 "research/px4_actuator_effectiveness/config/logger_topics.txt"):
        assert must in frozen, must


# --- matrix and order --------------------------------------------------------

def test_matrices_regenerate_byte_for_byte():
    flights, analysis, order = _generator().build()
    assert _csv_text(flights) == (PREREG / "FLIGHT_MATRIX.csv").read_text()
    assert _csv_text(analysis) == (PREREG / "ANALYSIS_MATRIX.csv").read_text()


def test_execution_order_is_the_seeded_permutation():
    gen = _generator()
    flights, _, order = gen.build()
    rows = list(csv.DictReader(open(PREREG / "EXECUTION_ORDER.csv")))
    assert [r["flight_id"] for r in rows] == order
    assert [int(r["position"]) for r in rows] == list(range(1, len(order) + 1))
    assert sorted(order) == sorted(f["flight_id"] for f in flights)
    keys = [r["order_key_sha256"] for r in rows]
    assert keys == sorted(keys)
    assert all(k == hashlib.sha256(f"{gen.SEED}/order/{r['flight_id']}".encode()).hexdigest()
               for k, r in zip(keys, rows))


def test_execution_order_is_not_monotone_in_severity():
    eta = {r["flight_id"]: float(r["eta"]) for r in csv.DictReader(open(PREREG / "FLIGHT_MATRIX.csv"))}
    seq = [eta[r["flight_id"]] for r in csv.DictReader(open(PREREG / "EXECUTION_ORDER.csv"))]
    assert seq != sorted(seq) and seq != sorted(seq, reverse=True)


def test_every_pair_is_matched_within_its_nuisance_condition():
    flights = {r["flight_id"]: r for r in csv.DictReader(open(PREREG / "FLIGHT_MATRIX.csv"))}
    analysis = list(csv.DictReader(open(PREREG / "ANALYSIS_MATRIX.csv")))
    ids = [r["analysis_id"] for r in analysis]
    assert len(ids) == len(set(ids)) and len(flights) == 66 and len(analysis) == 121
    pairs = {}
    for r in analysis:
        if r["kind"] in ("A", "B"):
            pairs.setdefault(r["pair_id"], {})[r["kind"]] = r
    assert len(pairs) == 55
    for pid, p in pairs.items():
        a, b = p["A"], p["B"]
        fa, fb = flights[a["source_flight_id"]], flights[b["source_flight_id"]]
        assert fa["condition"] == "A" and fb["condition"] == "NB", pid
        assert b["matched_a_flight_id"] == a["source_flight_id"], pid
        assert a["eta"] == b["eta"] == fa["eta"] and fa["onset_value"] == fa["eta"], pid
        for k in ("nuisance_id", "heading_deg", "t_onset_s", "t_arm_s", "t_end_s", "log_config"):
            assert fa[k] == fb[k], (pid, k)


# --- code agrees with the declared configuration -----------------------------

def test_code_constants_match_the_declared_configuration():
    cfg = json.loads((PREREG / "PREREG_CONFIG.json").read_text())
    gen = _generator()
    d = cfg["design"]
    assert list(gen.LEVELS) == d["fault_levels_eta"]
    assert gen.N_CONDITIONS == d["n_conditions"]
    assert gen.SEED == d["seed"]
    assert gen.T_ARM_S == d["t_arm_s"] and gen.T_END_AFTER_ONSET_S == d["t_end_after_onset_s"]
    assert list(gen.BENIGN) == [d["benign_onset_event"]["parameter"], d["benign_onset_event"]["value"]]
    power = json.loads((PREREG / "POWER.json").read_text())
    assert power["smallest_H_meeting_requirement"] == gen.N_CONDITIONS

    windows = _module_constant(X / "pipeline" / "xsys_features.py", "WINDOWS")
    assert {k: list(v) for k, v in windows.items()} == cfg["windows_s"]
    assert {k: list(v) for k, v in gen.WINDOWS.items()} == cfg["windows_s"]
    assert list(_module_constant(X / "pipeline" / "xsys_features.py", "ANALYSIS_SPAN")) == cfg["analysis_span_s"]

    assert _module_constant(X / "pipeline" / "stage0_prepare.py", "TOL") == cfg["check_tolerances"]
    assert list(_module_constant(X / "pipeline" / "stage1_evidence.py", "VARIANTS")) == cfg["variants"]
    s2 = X / "pipeline" / "stage2_score.py"
    assert _module_constant(s2, "ALPHA_ONE_SIDED") == cfg["primary_endpoint"]["alpha_one_sided"]
    assert _module_constant(s2, "NULL_RATE") == cfg["primary_endpoint"]["null_rate"]
    assert _module_constant(s2, "PRIMARY") == (cfg["checkpoints"]["primary"], cfg["primary_variant"])

    cal = json.loads((X / "calibration" / "CALIBRATION.json").read_text())["calibration"]
    assert {k: cfg["calibration"][k] for k in cal} == cal


# --- blinding -----------------------------------------------------------------

def test_blind_stage_cannot_name_a_label_source():
    forbidden = ("--key", "--qc", "KEY.json", "QC.json", "truth", "analysis_id", "pair_id",
                 "PHYSICAL_ACTUATOR_DEGRADATION", "RPM_TELEMETRY_CORRUPTION", "matched_a")
    blind_side = ("stage1_evidence.py", "xsys_features.py", "xsys_v2_adapter.py", "xsys_freeze_check.py")
    for name in blind_side:
        text = (X / "pipeline" / name).read_text()
        found = [t for t in forbidden if t in text]
        assert not found, f"{name} (stage 1 and its imports) names {found}"
    tree = ast.parse((X / "pipeline" / "stage1_evidence.py").read_text())
    local = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not {"stage0_prepare", "stage2_score", "xsys_extract"} & local


# --- data --------------------------------------------------------------------

def test_confirmatory_data_are_bound_to_this_manifest():
    """No confirmatory flight existed at the freeze. Any that appear later
    must carry this manifest's SHA-256 in their campaign and trial records."""
    for camp in X.rglob("CAMPAIGN.json"):
        assert json.loads(camp.read_text())["freeze_manifest_sha256"] == FROZEN_MANIFEST_SHA256, camp
    for rec in X.rglob("XS1-*.json"):
        extra = json.loads(rec.read_text()).get("extra", {})
        assert extra.get("freeze_manifest_sha256") == FROZEN_MANIFEST_SHA256, rec
    for log in list(X.rglob("XS1-*.ulg")) + list(X.rglob("XS1-*.ulg.xz")):
        stem = log.name.split(".")[0]
        assert (log.parent / f"{stem}.json").exists(), f"{log} has no trial record"
