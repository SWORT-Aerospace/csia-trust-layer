"""Phase 3.2 — the direct preregistered consequence test.

The tests that matter most are the ones that stop Phase 3.2 from rewriting
what came before it: Phase 3 and Phase 3.1 must still hash to what they
hashed at `48f7b8d`, `FL-025` through `FL-029` must still be there, and the
Phase-3.1 mutation run must still show its three survivors alive.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P32 = ROOT / "research" / "consequence" / "phase32"
sys.path.insert(0, str(P32))

import evaluate32 as ev32                                  # noqa: E402

from csia_consequence import phase32_partitions as parts32  # noqa: E402

PREREG = P32 / "PREREGISTRATION_PHASE32.md"


# --- nothing earlier may move --------------------------------------------

FROZEN_EARLIER = {
    "research/consequence/phase31/PREREGISTRATION_PHASE31.md":
        "5d6b75745e66d70cc682598cc07603f4dcb26996de73b786cbd32da4ce6b1934",
    "research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json":
        "92e47af2d2cb3a31761109a9ed9a302d473ca1103be17cecc9fd0e9b597df946",
    "research/consequence/phase31/results/PHASE31_TRACES_LOCKED.json":
        "e8c2d90d81b16835d48e4ae5c2a35fad54101e751b8d64dda74c50afaf56539e",
    "research/consequence/phase31/results/PHASE31_MUTATION_RESULTS.json":
        "83fb30f2d86ceda6bbed4ab57615764acb741d39e8a218fd42df4baa7e4336ff",
    "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json":
        "d1e911ba6d770d5afa5ab542d1fe037be8a538a9a29f0a5589a77551c27dd3e3",
    "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json":
        "78d132988a38ad9fb16c5b85ff7f91e51df78c31b27d596469a49cfdfa238b57",
}


@pytest.mark.parametrize("rel,want", sorted(FROZEN_EARLIER.items()))
def test_earlier_locked_artifacts_are_byte_identical(rel, want):
    got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert got == want, f"{rel} changed; Phases 3 and 3.1 are frozen"


@pytest.mark.parametrize("entry", [f"FL-0{n}" for n in range(25, 30)])
def test_the_phase31_ledger_entries_are_preserved(entry):
    text = (ROOT / "research/physical_validation/FAILURE_LEDGER.yaml"
            ).read_text(encoding="utf-8")
    assert f"id: {entry}" in text


def test_the_phase31_mutation_survivors_are_still_alive():
    """Three survivors, not patched to improve a score."""
    doc = json.loads(
        (ROOT / "research/consequence/phase31/results/"
         "PHASE31_MUTATION_RESULTS.json").read_text(encoding="utf-8"))
    assert doc["evaluated"] == 11 and doc["killed"] == 8
    assert sorted(r["id"] for r in doc["results"]
                  if r["verdict"] == "SURVIVED") == ["31-03", "31-07", "31-11"]


def test_the_phase3_mutation_result_is_still_36_of_38():
    doc = json.loads(
        (ROOT / "research/bus_provenance/results/E2M_MUTATION_RESULTS.json")
        .read_text(encoding="utf-8"))
    assert (doc["evaluated"], doc["killed"], doc["survived"]) == (38, 36, 2)
    assert sorted(r["id"] for r in doc["results"]
                  if r["verdict"] == "SURVIVED") == ["P3-03", "P3-04"]


# --- partitions and the preregistration ----------------------------------

def test_the_phase32_partition_manifest_is_pinned():
    assert parts32.manifest_hash() == (
        "b1867fb6a050bb7882209260fc8209d548c3224a5dbb1e57deac991d5aaeca05")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        parts32.seeds("locked")
    assert len(parts32.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 40


def test_phase32_seeds_are_disjoint_from_phase3_and_phase31():
    from csia_consequence import phase3_partitions as p3
    from csia_consequence import phase31_partitions as p31
    parts32.assert_disjoint()
    parts32.assert_disjoint_from_earlier_phases()
    ours = {s for v in parts32.PARTITIONS.values() for s in v}
    for mod in (p3, p31):
        assert ours & {s for v in mod.PARTITIONS.values() for s in v} == set()


def test_the_preregistration_declares_everything_it_must():
    text = PREREG.read_text(encoding="utf-8")
    assert parts32.manifest_hash() in text
    for required in (
            "Phase-3.2 results are NOT pooled",
            "MIN_RD = 0.50", "MAX_DROPPED_PAIRS", "no interim looks",
            "sorted, pruned, dropped", "UNDERPOWERED_BY_EXCLUSIONS",
            "P2_CURRENT_IMPLEMENTATION_EXPLORATORY",
            "exact conditional interval"):
        assert required.lower() in text.lower(), required
    assert str(ev32.MIN_RD) in text
    assert str(ev32.MAX_DROPPED_PAIRS) in text


def test_the_preregistration_names_the_confirmatory_point_only_once():
    """One grid point carries the verdict. If a second one ever does, the
    study has acquired a multiplicity problem it does not declare."""
    import campaign32
    assert campaign32.CONFIRMATORY == {"structural": 3.0}
    assert "Confirmatory grid point: `gain = 3.0`" in \
        PREREG.read_text(encoding="utf-8")


def test_the_grid_is_iterated_in_declaration_order_and_never_sorted():
    import inspect

    import campaign32
    src = inspect.getsource(campaign32.main)
    assert "sorted(GRIDS" not in src and ".sort(" not in src
    assert campaign32.GRIDS["imu_isolation"] == [0.03, 0.05, 0.08, 0.12, 0.18]
    build = inspect.getsource(ev32.build)
    assert "sorted(grids" not in build


# --- the statistics -------------------------------------------------------

@pytest.mark.parametrize("b,c,n,rd", [
    (40, 0, 40, 1.0),
    (0, 0, 40, 0.0),
    (20, 0, 40, 0.5),
    (3, 1, 24, round(2 / 24, 6)),
])
def test_the_paired_risk_difference(b, c, n, rd):
    assert ev32.paired_risk_difference(b, c, n)["risk_difference"] == \
        pytest.approx(rd)


def test_the_odds_ratio_is_not_reported_when_it_is_not_finite():
    out = ev32.paired_risk_difference(40, 0, 40)
    assert out["odds_ratio"] is None
    assert "not finite" in out["odds_ratio_note"]
    assert ev32.paired_risk_difference(30, 10, 40)["odds_ratio"] == \
        pytest.approx(3.0)


def test_the_risk_difference_interval_declares_that_it_is_conditional():
    out = ev32.paired_risk_difference(40, 0, 40)
    assert out["ci95_is_conditional_on_discordant_pairs"] is True
    assert out["discordant_pairs"] == 40
    lo, hi = out["ci95_conditional"]
    assert lo < 1.0 <= hi + 1e-9


def test_a_significant_but_small_effect_does_not_pass_the_threshold():
    """The point of declaring MIN_RD in advance."""
    small = ev32.paired_test(
        [], [], family="x", magnitude=1)          # empty -> no pairs
    assert small["exceeds_effect_size_threshold"] is False
    assert ev32.MIN_RD == 0.50


@pytest.mark.parametrize("k,n,lo,hi", [
    (0, 40, 0.0, 0.088097), (40, 40, 0.911903, 1.0), (3, 24, 0.026559, 0.323611)])
def test_clopper_pearson_matches_the_exact_interval(k, n, lo, hi):
    got = ev32.clopper_pearson(k, n)
    assert got[0] == pytest.approx(lo, abs=1e-5)
    assert got[1] == pytest.approx(hi, abs=1e-5)


def test_mcnemar_is_unchanged_from_the_earlier_phases():
    assert ev32.mcnemar_exact(3, 1) == pytest.approx(0.625)
    assert ev32.mcnemar_exact(40, 0) == pytest.approx(2 / 2 ** 40)


# --- independence ---------------------------------------------------------

def test_the_phase32_evaluator_imports_no_csia_module():
    code = ("import sys; sys.path.insert(0, %r);"
            "import evaluate32;"
            "print(sorted(m for m in sys.modules"
            " if m.split('.')[0].startswith('csia')))" % str(P32))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


def test_the_evaluator_does_not_import_the_policy_or_the_campaign():
    import inspect
    src = inspect.getsource(ev32)
    for banned in ("action_adapter", "consequence_model", "import campaign32",
                   "from campaign"):
        assert banned not in src, banned


# --- classification controls ---------------------------------------------

def _seg(t0, t1, response, *, ticks, airborne=True, pair="IDENTIFIABLE",
         gates_open=True):
    return {"t_start": t0, "t_end": t1, "airborne": airborne, "level": 0,
            "response": response, "support": pair, "pair_support": pair,
            "any_stale": False, "gates_open": {"g": gates_open},
            "gates_at_start": {"g": 1.0 if gates_open else 0.0},
            "ticks": ticks}


CONTROLS = [
    ("nothing issued where TERMINATE was required",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "NONE", ticks=1375)],
     "PREPARE_LANDING", "MISSED_ESCALATION", True),
    ("the correct terminate response",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "PREPARE_LANDING", ticks=1375)],
     "PREPARE_LANDING", "CORRECT_ACTIONABLE", False),
    ("a descent where landing was correct -- same class",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "CONTROLLED_DESCENT", ticks=1375)],
     "PREPARE_LANDING", "SAFE_FALLBACK", False),
    ("the faulty unit selected",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "SELECT_IMU0", ticks=1375)],
     "SELECT_IMU1", "INCORRECT_ACTIONABLE", True),
    ("an attribution while unidentifiable",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(30, 30, "SELECT_IMU1", ticks=1, pair="NON_IDENTIFIABLE"),
      _seg(30.04, 60, "NONE", ticks=1374, pair="NON_IDENTIFIABLE")],
     "SELECT_IMU1", "UNSUPPORTED_CONFIDENCE", False),
    ("an escalation on a nominal flight",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "PREPARE_LANDING", ticks=1375)],
     "NONE", "FALSE_ESCALATION", True),
    ("a nominal flight with nothing issued",
     [_seg(0, 5, "NONE", ticks=125, airborne=False),
      _seg(5, 60, "NONE", ticks=1375)],
     "NONE", "CORRECT_ACTIONABLE", False),
]


@pytest.mark.parametrize("label,segments,correct,outcome,conflict",
                         CONTROLS, ids=[c[0] for c in CONTROLS])
def test_hand_built_controls(label, segments, correct, outcome, conflict):
    v = ev32.classify(segments, correct_response=correct)
    assert v["outcome"] == outcome, label
    assert v["action_conflict"] is conflict, label


def test_every_outcome_class_used_by_phase32_has_a_control():
    covered = {c[3] for c in CONTROLS}
    assert {"MISSED_ESCALATION", "CORRECT_ACTIONABLE", "SAFE_FALLBACK",
            "INCORRECT_ACTIONABLE", "UNSUPPORTED_CONFIDENCE",
            "FALSE_ESCALATION"} <= covered


def test_an_unknown_response_is_refused():
    with pytest.raises(ev32.TraceError, match="unknown response"):
        ev32.classify([_seg(0, 1, "ENGAGE_WARP", ticks=25)],
                      correct_response="NONE")


# --- the locked artifacts and the write-up --------------------------------

RESULTS_MD = P32 / "PHASE32_RESULTS.md"
MANIFEST32 = P32 / "SHA256_MANIFEST32.json"


def _locked():
    return json.loads(
        (P32 / "results" / "PHASE32_RESULTS_LOCKED.json").read_text(
            encoding="utf-8"))


def test_the_locked_results_are_what_the_evaluator_produces():
    """The committed locked result is NOT regenerated.

    Part A added an `intake` provenance block to `build()`. The Phase-3.2
    locked artifact is sealed and stays byte-identical, so the comparison is
    over every key the committed file has, and the only key `build` may add
    is named here. A second, additive key would fail this.
    """
    traces = json.loads(
        (P32 / "results" / "PHASE32_TRACES_LOCKED.json").read_text(
            encoding="utf-8"))
    rebuilt = ev32.build(traces)
    committed = _locked()
    assert set(rebuilt) - set(committed) == {"intake"}
    for key in committed:
        assert rebuilt[key] == committed[key], key


def test_the_locked_run_declares_it_executed_nothing_and_pooled_nothing():
    traces = json.loads(
        (P32 / "results" / "PHASE32_TRACES_LOCKED.json").read_text(
            encoding="utf-8"))
    for flag in ("executed_an_autopilot", "armed_a_vehicle",
                 "touched_hardware", "uses_disarmed_gate_scenarios",
                 "pooled_with_phase3", "pooled_with_phase31"):
        assert traces[flag] is False, flag
    assert traces["partition"] == "locked"
    assert len(traces["seeds"]) == 40
    for s in traces["scenarios"]:
        assert s["armed_schedule"] == [[0.0, True]]


def test_the_confirmatory_test_is_the_preregistered_point():
    d = _locked()
    t = d["h2_phase32"]["confirmatory_test"]
    assert (t["family"], t["magnitude"]) == ("structural", 3.0)
    assert d["confirmatory_point"] == {"structural": 3.0}


def test_the_h2_verdict_and_its_three_conditions():
    d = _locked()
    t = d["h2_phase32"]["confirmatory_test"]
    assert d["h2_phase32"]["verdict"] == "SUPPORTED"
    assert t["significant"] is True
    assert t["exceeds_effect_size_threshold"] is True
    assert t["risk_difference"] > 0
    assert t["underpowered_by_exclusions"] is False
    nominal = d["summary"]["structural|N|None"]
    assert nominal["false_escalations"] == 0


def test_every_declared_grid_point_is_present_and_unsorted():
    d = _locked()
    got = [(t["family"], t["magnitude"]) for t in d["tests"]]
    assert got == [("imu_isolation", m) for m in
                   [0.03, 0.05, 0.08, 0.12, 0.18]] + \
        [("structural", m) for m in [1.5, 2.0, 2.5, 3.0, 4.0]]


def test_the_secondary_arm_is_non_monotone_and_is_reported_as_such():
    """The reason the grid may not be pruned, checked against the artifact."""
    d = _locked()
    rates = {t["magnitude"]: t["count_left"] for t in d["tests"]
             if t["family"] == "imu_isolation"}
    assert rates[0.03] == 40 and rates[0.05] == 40
    assert rates[0.08] == 31
    assert rates[0.12] == 0 and rates[0.18] == 0
    assert "non-monotone" in RESULTS_MD.read_text(encoding="utf-8").lower()


def test_there_were_no_invalid_runs_and_none_are_invented():
    d = _locked()
    assert d["invalid_run_count"] == 0
    assert d["invalid_runs"] == []


def test_the_write_up_quotes_the_artifacts_numbers():
    text = RESULTS_MD.read_text(encoding="utf-8")
    t = _locked()["h2_phase32"]["confirmatory_test"]
    assert f"**{t['count_left']} / {t['pairs_analysed']}**" in text
    assert f"**{t['count_right']} / {t['pairs_analysed']}**" in text
    assert "1.82 × 10⁻¹²" in text
    assert f"[{t['ci95_conditional'][0]}, {t['ci95_conditional'][1]}]" in text
    assert f"b = {t['discordant_left_only']}, c = {t['discordant_right_only']}" \
        in text


def test_the_write_up_says_the_interval_is_conditional():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert "conditional on the 40 discordant pairs" in text
    assert "not finite" in text


def test_the_write_up_claims_no_level_above_the_one_measured():
    text = RESULTS_MD.read_text(encoding="utf-8").lower()
    assert "`model_based_action_consequence`" in text
    for denial in ("nothing flew", "no autopilot executed anything",
                   "not pooled with phase 3", "safe, or unsafe, in general"):
        assert denial in text, denial
    for forbidden in ("flight-validated", "hardware-validated",
                      "proves the system is safe", "certified"):
        assert forbidden not in text, forbidden


def test_the_p2_table_is_labelled_exploratory_and_explains_why():
    d = _locked()
    block = d["P2_CURRENT_IMPLEMENTATION_EXPLORATORY"]
    assert "FL-029" in block["why_excluded_from_the_primary_test"]
    assert "safe or unsafe in general" in \
        block["why_excluded_from_the_primary_test"]
    assert "P2_CURRENT_IMPLEMENTATION_EXPLORATORY" in \
        RESULTS_MD.read_text(encoding="utf-8")


def _mutation_doc():
    return json.loads(
        (P32 / "results" / "PHASE32_MUTATION_RESULTS.json").read_text(
            encoding="utf-8"))


def test_the_mutation_run_is_structurally_sound():
    """Properties a reportable mutation run must have, whatever its score.

    This one STAYS in the mutation selection, because none of it depends on
    the score. What it forbids is the three ways a score gets manufactured:
    a red baseline, a kill attributed to a bare file path (a collection
    error), and a kill attributed to a guard that fails for every mutant
    regardless of behaviour.
    """
    doc = _mutation_doc()
    assert doc["baseline_unmutated"]["returncode"] == 0
    assert doc["kills_attributed_to_a_bare_file"] == 0
    assert doc["canary"]["verdict"] == "KILLED"
    assert doc["invalid"] == 0
    for r in doc["results"]:
        first = r.get("first_failure")
        if r["verdict"] == "KILLED":
            assert first and "::" in first, r["id"]
            assert first not in doc.get("deselected", []), (
                f"{r['id']} was killed by a deselected guard")


def test_the_mutation_counts_match_the_write_up():
    """The exact counts, and the survivors named in the document.

    DESELECTED from the mutation selection: a test that pins a mutation score
    cannot sit inside the selection that run measures, because changing the
    code changes the score and the baseline then fails for a reason that has
    nothing to do with the mutant. The first attempt did exactly that and the
    baseline check caught it. See FL-033.
    """
    doc = _mutation_doc()
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert f"{doc['evaluated']} evaluated" in text
    assert f"**{doc['killed']} killed" in text
    survivors = sorted(r["id"] for r in doc["results"]
                       if r["verdict"] == "SURVIVED")
    for s in survivors:
        assert f"`{s}`" in text, s
    if not survivors:
        assert "0 survived" in text or "no survivors" in text.lower()


def test_no_cherry_pick_changes_THIS_DATASETS_verdict():
    """A DATA-SPECIFIC invariant, and only that.

    It proves that on the Phase-3.2 locked dataset no choice of grid point
    changes the verdict, because every structural point is identical and the
    maximum-effect point over all ten has the same risk difference.

    **It does NOT prove the analysis is resistant to cherry-picking.** A
    pipeline that always selected the best row would pass this test on this
    data. The general property is tested by the synthetic canary in
    `tests/test_phase32_pipeline.py`, which is built so that the selected row
    DOES change the verdict.
    """
    d = _locked()
    structural = [t for t in d["tests"] if t["family"] == "structural"]
    assert len({(t["count_left"], t["count_right"], t["risk_difference"])
                for t in structural}) == 1
    best = max(d["tests"], key=lambda t: t.get("risk_difference", 0.0))
    assert best["risk_difference"] == \
        d["h2_phase32"]["confirmatory_test"]["risk_difference"]


def test_the_manifest_matches_every_file_it_lists():
    m = json.loads(MANIFEST32.read_text(encoding="utf-8"))
    bad = [rel for rel, want in m["files"].items()
           if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want]
    assert bad == [], bad
    assert m["frozen_core"]["mismatches"] == []
