"""Guards for the evidence-semantics package.

NOTHING HERE SCORES A RESULT. These tests protect the things that would
silently invalidate the package: a broken instrument, a contract that has
drifted from its schema, a citation that no longer points where it claims, and
a report that has quietly acquired a novelty claim its own conclusion denies.
"""

from __future__ import annotations

import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "evidence_semantics")
RES = os.path.join(PKG, "results")


def _j(name, where=PKG):
    with open(os.path.join(where, name), encoding="utf-8") as fh:
        return json.load(fh)


def _needs(name, where=PKG):
    return pytest.mark.skipif(
        not os.path.exists(os.path.join(where, name)),
        reason=f"{name} not built")


# ------------------------------------------------------- the hard stop
@_needs("PRIOR_RESULT_REPRODUCTION.json", RES)
def test_the_item_12_hard_stop_is_recorded_as_cleared():
    """79/120 and shortest 'I'. If this ever stops reproducing, every
    downstream number in the package is void."""
    d = _j("PRIOR_RESULT_REPRODUCTION.json", RES)
    assert d["exact"] is True
    assert d["observed"] == d["expected"]
    assert d["verdict"] == "REPRODUCED"
    assert d["independent_instrument_consistent"] is True


# ------------------------------------------------------- the instrument
@_needs("TOOL_SELF_AUDIT.json")
def test_the_checker_catches_all_four_injected_defects():
    d = _j("TOOL_SELF_AUDIT.json")
    assert d["all_four_detected"] is True
    assert d["instrument_restored_exactly"] is True
    assert len(d["fixtures"]) == 4
    for f in d["fixtures"]:
        assert f["detected"] is True, f["fixture"]


@_needs("TOOL_SELF_AUDIT.json")
def test_the_refuted_self_audit_prediction_is_still_recorded_as_refuted():
    """D1's prediction was wrong. It was NOT re-aimed to make it come true,
    and the record of that must not quietly improve."""
    d = _j("TOOL_SELF_AUDIT.json")
    refuted = d["predictions_refuted"]
    assert refuted == ["D1_one_message_phase_shift"], refuted
    d1 = next(f for f in d["fixtures"]
              if f["fixture"] == "D1_one_message_phase_shift")
    assert d1["prediction_held"] is False
    assert "REFUTED" in d1["prediction_note"]


# ------------------------------------------------------- the findings
@_needs("MINIMAL_COUNTEREXAMPLES.json")
def test_every_reported_witness_is_within_the_searched_bound():
    d = _j("MINIMAL_COUNTEREXAMPLES.json")
    bound = d["max_word_length"]
    assert d["witnesses"], "no witnesses recorded"
    for w in d["witnesses"]:
        assert w["witness_length"] <= bound, w
        assert w["witness_length"] == len(w["witness"])


@_needs("CAUSAL_BLAME_TRACES.json")
def test_no_collapse_is_blamed_on_a_stage_the_path_does_not_have():
    """plugins.py and ulog_source.py have no T3/T4. Naming a site in
    base.py for them would be an attribution to code they never run."""
    d = _j("CAUSAL_BLAME_TRACES.json")
    assert d["traces"]
    for t in d["traces"]:
        assert t["first_collapse_stage"] not in t["no_representation_stage"], t
        if t["path"] != "v1_1_adapter":
            assert t["no_representation_stage"] == ["T3_ingest",
                                                    "T4_channel"], t


@_needs("CAUSAL_BLAME_TRACES.json")
def test_the_gnss_collapse_is_at_the_core_bridge_not_the_adapter():
    """Item 22's illustrative example blames the adapter. Measured, the
    adapter preserves the distinction and the bridge destroys it."""
    d = _j("CAUSAL_BLAME_TRACES.json")
    t = next(x for x in d["traces"]
             if x["family"] == "gnss" and x["path"] == "v1_1_adapter")
    assert t["first_collapse_stage"] == "T5_core_bridge"
    assert t["stage_table"]["T3_ingest"]["identical"] is False
    assert t["stage_table"]["T4_channel"]["identical"] is False


@_needs("CAUSAL_BLAME_TRACES.json")
def test_the_three_families_do_not_all_collapse_at_the_same_stage():
    """If they did, the stage localisation would be reporting a constant
    and would be evidence of nothing."""
    d = _j("CAUSAL_BLAME_TRACES.json")
    stages = {t["family"]: t["first_collapse_stage"] for t in d["traces"]
              if t["path"] == "v1_1_adapter" and t["clause"].endswith("F1")}
    assert len(set(stages.values())) > 1, stages
    assert stages["mag"] == "T3_ingest", stages


def test_the_failsafe_action_sets_never_differ():
    """The ceiling of the whole package. If a word ever DID change the
    issued actions, section 14 of the report would be wrong."""
    import csv
    path = os.path.join(PKG, "DOWNSTREAM_CONSEQUENCES.csv")
    if not os.path.exists(path):
        pytest.skip("DOWNSTREAM_CONSEQUENCES.csv not built")
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for r in rows:
        assert r["actions_a"] == r["actions_b"], r
        assert r["consequence"] != "CONTROL_FAILSAFE", r


def test_no_consequence_is_counted_when_its_control_diverges():
    import csv
    path = os.path.join(PKG, "CROSS_PATH_EQUIVALENCE.csv")
    if not os.path.exists(path):
        pytest.skip("CROSS_PATH_EQUIVALENCE.csv not built")
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        lvl = r["first_attributable_level"]
        if lvl:
            assert r[f"{lvl}_control_equivalent"] == "True", r


# ------------------------------------------------------- the contracts
def test_every_contract_matches_the_schema_shape():
    """A light structural check: the schema is the spec, and a contract that
    has drifted from it makes the checker's output unreadable."""
    schema = _j("EVIDENCE_SEMANTICS_CONTRACT.schema.json")
    required = set(schema["required"])
    allowed_states = set(schema["$defs"]["state"]["enum"])
    d = os.path.join(PKG, "ARDUPILOT_INGEST_CONTRACTS")
    names = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    assert names, "no contracts"
    for fn in names:
        c = _j(fn, d)
        assert required <= set(c), (fn, required - set(c))
        assert set(c) <= set(schema["properties"]), fn
        for row in c["accepted_input_states"]:
            assert row["state"] in allowed_states, (fn, row)
        for m in c["forbidden_merges"]:
            assert set(m["states"]) <= allowed_states, (fn, m)
            assert set(m["witness_words"]) == set(m["states"]), (fn, m)
            assert m["needed_by"].strip(), fn
        for s in c["emitted_states_required"]:
            assert s in allowed_states, (fn, s)


def test_contract_stage_sites_name_files_that_exist():
    d = os.path.join(PKG, "ARDUPILOT_INGEST_CONTRACTS")
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".json")):
        for stage, site in _j(fn, d)["stage_sites"].items():
            m = re.match(r"^(csia/[\w/]+\.py)", site)
            if m:
                assert os.path.exists(os.path.join(ROOT, m.group(1))), \
                    (fn, stage, site)


# ------------------------------------------------------- the citations
def test_every_cross_sensor_citation_still_resolves():
    """The audit re-reads each cited line at build time; this re-checks it
    at test time, so a later edit to the adapter cannot leave a stale line
    number in a committed CSV."""
    import csv
    path = os.path.join(PKG, "CROSS_SENSOR_AUDIT.csv")
    if not os.path.exists(path):
        pytest.skip("CROSS_SENSOR_AUDIT.csv not built")
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    # Resolved against the revision the audit was taken at, not the worktree.
    # These rows are facts about what v1 DID; the v1.1 engineering pass changed
    # some of that code, and a citation to superseded code must still resolve
    # or the audit becomes unreadable. See cross_sensor_audit.CITED_REVISION.
    import subprocess
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cross_sensor_audit", os.path.join(PKG, "cross_sensor_audit.py"))
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    cache = {}
    for r in rows:
        fpath, line_no = r["citation"].rsplit(":", 1)
        if fpath not in cache:
            got = subprocess.run(
                ["git", "show", f"{audit.CITED_REVISION}:{fpath}"],
                cwd=ROOT, capture_output=True, text=True)
            cache[fpath] = (got.stdout if got.returncode == 0
                            else open(os.path.join(ROOT, fpath),
                                      encoding="utf-8").read())
        lines = cache[fpath].splitlines()
        assert lines[int(line_no) - 1].strip() == r["cited_text"], r["citation"]


def test_at_most_two_additional_sensor_families_were_selected():
    """Item 23's limit."""
    d = _j("CROSS_SENSOR_AUDIT.json", RES) if os.path.exists(
        os.path.join(RES, "CROSS_SENSOR_AUDIT.json")) else None
    if d is None:
        pytest.skip("CROSS_SENSOR_AUDIT.json not built")
    assert len(set(d["additional_families_selected"])) <= 2, d


# ------------------------------------------------------- the ledger
def test_the_ledger_records_no_surviving_novelty_claim():
    led = _j("CLAIM_LEDGER.json")
    statuses = {c["status"] for c in led["claims"]}
    assert "PROVED - POSSIBLE NOVEL CONTRIBUTION" not in statuses, (
        "the whole package concludes the opposite; a claim at this status "
        "needs the report rewritten, not the ledger edited")
    assert led["refuted_predictions"], "refuted predictions must be kept"
    for p in led["refuted_predictions"]:
        assert p["kept"] is True


def test_the_ledger_and_the_hard_stops_agree():
    led = _j("CLAIM_LEDGER.json")
    stops = {s["item"]: s for s in led["hard_stops"]}
    assert stops[12]["result"] == "CLEARED"
    assert stops[12]["observed"] == stops[12]["expected"]
    assert "NOT EXECUTED" in stops[27]["result"]
    assert "HONOURED" in stops[32]["result"]


# ------------------------------------------------------- writing drift
DENIALS = ("not ", "no ", "none", "nothing", "never", "cannot", "may not",
           "subsumed", "known/", "forbidden", "struck", "downgrad",
           "prior art", "unsupported", "settled", "without", "refuted",
           "reduction", "denies")


def test_no_novelty_wording_anywhere_in_the_package():
    """A heuristic guard against writing drift, not a proof of anything.
    Its job is to fail loudly if someone later writes 'this is novel' in a
    package whose whole conclusion is that it is not."""
    banned = ("first-ever", "unprecedented", "new paradigm", "new theorem",
              "breakthrough")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        text = raw.replace("*", "").replace("`", "")
        text = re.sub(r"[.,;:!?)\]]", " ", text)
        for w in banned:
            if w not in text:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if w not in line:
                    continue
                if line.lstrip().startswith("#"):
                    continue
                window = " ".join(lines[i:i + 3])
                assert any(k in window for k in DENIALS), (fn, w, line[:120])


def test_the_frozen_core_was_not_touched():
    """Item 32. The package may not change CSIA production behaviour, and
    the v1 freeze test already enforces the hashes -- this asserts the
    package's own claim to have honoured it is checkable."""
    led = _j("CLAIM_LEDGER.json")
    stop = next(s for s in led["hard_stops"] if s["item"] == 32)
    assert "FROZEN_PATHS untouched" in stop["result"]
    assert os.path.exists(os.path.join(ROOT, "tests", "test_v1_frozen.py"))
