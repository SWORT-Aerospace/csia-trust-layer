#!/usr/bin/env python3
"""Phase 0 of the CSIA 2.2 offboard pilot: lock the accepted 2.2 state.
RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_offboard_pilot/verify_pilot_baseline.py [--final]

Writes PILOT_BASELINE.json (or PILOT_FINAL_STATE.json with --final), nothing
else. Every check is re-executed here; no earlier package's harness is run
as a script, so no earlier result file is rewritten.

| check | how |
|---|---|
| 2.2 commits | 4fb191e and the provenance commit c197abd are ancestors of HEAD |
| 2.2 unchanged at lock time | `csia_evidence_assurance/`, the 2.2 package and its tests are identical to 4fb191e (Phase 0 only; the pilot may then extend the code) |
| Semantic Core 2.1.1 | `csia_semantic_core/` byte-identical to 2b2adcc |
| 2.1.1 governance, XSYS gate, Phase C | the revision's own verifier and gate functions, imported |
| 2.2 tests | `tests/test_evidence_assurance_2_2.py` passes |
| scenario, XSYS and E1 replays | `replay_2_2.corpus()`, `replay_2_2.xsys()`, `e1_2_2.run()` re-executed in memory and compared with the committed results |
| profile validator | r2 through the 2.2 gate: ACCEPTED with the same findings |
| producer contracts | every contract file's digest, pinned |
| dataset reports | every committed 2.2 dataset report matches its recorded SHA-256 |
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

import common_pilot as C

OUT = C.HERE / "PILOT_BASELINE.json"
FINAL = C.HERE / "PILOT_FINAL_STATE.json"


def ancestry():
    out = {}
    for c in (C.ACCEPTED_2_2, C.PROVENANCE_2_2, C.SEMANTIC_2_1_1):
        r = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"], cwd=C.REPO)
        out[c] = r.returncode == 0
    return out


def unchanged(since, *paths):
    return C.git("diff", "--stat", since, "--", *paths) or "none"


def pytest_file(f):
    p = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q",
                        "-p", "no:cacheprovider", f], cwd=C.REPO, capture_output=True, text=True)
    tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]
    m = re.search(r"(\d+) passed", tail)
    return {"summary": re.sub(r" in [0-9.]+s", "", tail), "passed": int(m.group(1)) if m else 0,
            "ok": p.returncode == 0}


def replays():
    import e1_2_2
    import replay_2_2 as RP
    committed = json.loads((C.P22 / "REPLAY_2_2_RESULTS.json").read_text())
    e1_committed = json.loads((C.P22 / "E1_2_2_RESULTS.json").read_text())["result"]
    v2 = RP.corpus()
    xs, receipts = RP.xsys()
    e1 = e1_2_2.run()["result"]
    keys_v2 = ("scenarios", "ticks", "rejected", "decision_differences", "gates")
    keys_xs = ("slots", "decision_differences", "rejected", "primary_unchanged",
               "outcomes_changed_outside_V4_C3", "primary_matches_sealed_record")
    keys_e1 = ("attribution", "stale_position_symptom_ticks", "missed_position_symptom_ticks",
               "config_mismatch_ticks", "other_rejections", "recovery_tick",
               "per_tick_equal_to_revision_REVISED_2_1_1_R2")
    receipts_committed = json.loads((C.P22 / "DIFFERENCE_RECEIPTS.json").read_text())["receipts"]
    return {
        "v2_corpus": {k: v2[k] for k in keys_v2},
        "v2_corpus_equal": all(json.dumps(v2[k], sort_keys=True)
                               == json.dumps(committed["v2_corpus"][k], sort_keys=True)
                               for k in keys_v2),
        "xsys": {k: xs[k] for k in keys_xs},
        "xsys_equal": all(json.dumps(xs[k], sort_keys=True)
                          == json.dumps(committed["xsys"][k], sort_keys=True) for k in keys_xs),
        "receipts_equal": json.dumps(receipts, sort_keys=True, default=str)
        == json.dumps(receipts_committed, sort_keys=True, default=str),
        "e1": {k: e1[k] for k in keys_e1},
        "e1_equal": all(json.dumps(e1[k], sort_keys=True) == json.dumps(e1_committed[k], sort_keys=True)
                        for k in keys_e1),
    }


def gates_2_1_1():
    import governance_gates as GG
    import semantic_probe as P
    import verify_baseline as VB
    from csia.v2.profiles import SCENARIOS
    from csia.v2.profiles.matched_scenarios import MATCHED_SETS
    from csia_semantic_core import Corrections
    from csia_semantic_core.profile_overlay import load_successor
    gov = VB.governance_state()
    xs = GG.xsys(True)
    runs = {n: P.run_scenario(SCENARIOS[n]) for m in MATCHED_SETS.values() for n in m}
    pc = GG.phase_c(runs, Corrections.revised(), load_successor("aircraft_successor_r2"))
    committed = json.loads((C.REPO / "engineering/v2/V2_PHASEC_GATE.json").read_text())
    return {"governance_ok": VB.governance_ok(gov),
            "xsys": {k: xs[k] for k in ("slots", "decision_differences_2_1_vs_sealed",
                                        "XSYS_HARD_GATE")},
            "xsys_primary": {k: xs["primary_recomputed_under_2_1"][k]
                             for k in ("n_pairs", "n_success", "lower95", "H_PRIMARY")},
            "xsys_gate_pass": GG.xsys_ok(xs),
            "phase_c_unchanged": (pc["verdict"] == committed["verdict"] and pc["qualifying"] == {
                q["set"]: q["answers"] for q in committed["qualifying_sets"]})}


def profile_and_contracts():
    from csia_evidence_assurance import runs
    from csia_evidence_assurance.contract import CONTRACT_DIR, ProducerContract
    _e, _core, gate, ov = runs.aircraft_setup()
    contracts = {p.stem: ProducerContract.load(p.stem).digest()
                 for p in sorted(CONTRACT_DIR.glob("*.json"))}
    return {"r2_gate": gate.status, "r2_digest": ov.digest(),
            "r2_findings": [f"{s}:{r}:{sub}" for s, r, sub, _d in gate.findings],
            "contract_digests": contracts,
            "pacing_citations_sha256": C.sha(C.REPO / "csia_evidence_assurance/pacing_citations.json")}


def dataset_reports():
    d = json.loads((C.P22 / "DATASETS_2_2.json").read_text())
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and "report_sha256" in v:
            p = C.P22 / "datasets" / k / "report.json"
            out[k] = p.exists() and C.sha(p) == v["report_sha256"]
    return out


def main():
    final = "--final" in sys.argv
    out = {"phase": "pilot final state" if final else "pilot Phase 0 baseline",
           "head": C.git("rev-parse", "--short", "HEAD")}
    out["ancestry"] = ancestry()
    out["semantic_core_changed_since_2_1_1"] = unchanged(C.SEMANTIC_2_1_1, "csia_semantic_core")
    out["frozen_v2_changed_since_2_2"] = unchanged(C.ACCEPTED_2_2, "csia")
    out["previous_2_2_package_changed"] = unchanged(C.ACCEPTED_2_2,
                                                    "research/csia_2_2_evidence_assurance")
    if not final:
        out["code_2_2_changed_since_acceptance"] = unchanged(
            C.ACCEPTED_2_2, "csia_evidence_assurance", "tests/test_evidence_assurance_2_2.py")
    out["ledger_matches_pinned"] = C.sha(
        C.REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == C.LEDGER_PINNED
    out["gates_2_1_1"] = gates_2_1_1()
    out["tests_2_2"] = pytest_file("tests/test_evidence_assurance_2_2.py")
    out["replays"] = replays()
    out["profile_and_contracts"] = profile_and_contracts()
    out["dataset_reports_match"] = dataset_reports()
    g, r, pc = out["gates_2_1_1"], out["replays"], out["profile_and_contracts"]
    ok = (all(out["ancestry"].values())
          and out["semantic_core_changed_since_2_1_1"] == "none"
          and out["frozen_v2_changed_since_2_2"] == "none"
          and out["previous_2_2_package_changed"] == "none"
          and out.get("code_2_2_changed_since_acceptance", "none") == "none"
          and out["ledger_matches_pinned"]
          and g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and out["tests_2_2"]["ok"]
          and r["v2_corpus_equal"] and r["xsys_equal"] and r["receipts_equal"] and r["e1_equal"]
          and pc["r2_gate"] == "ACCEPTED"
          and all(out["dataset_reports_match"].values()))
    out["PILOT_BASELINE_LOCKED" if not final else "PILOT_FINAL_STATE_OK"] = ok
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("profile_and_contracts",)}, indent=1, default=str)[:5000])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
