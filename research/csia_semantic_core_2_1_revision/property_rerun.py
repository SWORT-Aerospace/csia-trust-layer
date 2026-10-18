#!/usr/bin/env python3
"""Phase 1: every existing 2.1 test and property, re-run with 2.1.1 as the
default. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/property_rerun.py

Two runs of each file, in separate pytest processes:

    AS_IS     the committed tests as they are (2.1.0 default)
    REVISED   the same files with `-p revised_defaults_pytest_plugin`, which
              makes `Corrections()` mean all three revisions on, in that
              process only

Files: tests/test_semantic_core_2_1.py (50, including the Hypothesis
property tests P1-P19), tests/test_semantic_core_2_1_shadow.py (51) and
tests/test_semantic_core_2_1_revision.py (68, which pins 2.1.1 itself).

A test that fails only under REVISED is listed with the reason it changes:
a test that pins a 2.1.0 VERSION or a 2.1.0 DECISION the revision was
approved to change is expected; any property test failing is a weakened
property and blocks promotion.

Writes PROPERTY_RERUN.json.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import revision_common as RC

OUT = RC.HERE / "PROPERTY_RERUN.json"
FILES = ("tests/test_semantic_core_2_1.py", "tests/test_semantic_core_2_1_shadow.py",
         "tests/test_semantic_core_2_1_revision.py")
#: Tests whose failure under REVISED is the approved change, with why.
EXPECTED = {
    "test_the_versions_are_declared_and_2_0_0_is_the_historical_one":
        "pins Corrections().ids() to the six 2.1.0 corrections; under the plugin "
        "Corrections() carries the three revisions",
    "test_R9B_the_fault_is_observable_and_the_elimination_rule_is_unchanged":
        "pins 2.1.0's policy A (a faulted refuter leaves SUPPORTED standing); R-1 "
        "withholds it, which is the revision",
    "test_policy_b_withholds_the_supported_a_faulted_refuter_left_standing":
        "pins that 2.1.0 (policy A) leaves the fault-created SUPPORTED; R-1 withholds it",
    "test_g2_the_rejected_repairs_restore_the_wrong_process_stall":
        "pins that under 2.1.0 the GNSS repairs restore the wrong process_stall; under "
        "R-2 they cannot, which is the revision",
    "test_the_revisions_are_off_by_default_and_2_1_0_is_unchanged":
        "pins that Corrections() is 2.1.0; the plugin changes exactly that",
    "test_pacing_given_to_a_2_1_0_core_is_ignored":
        "builds a 'default' core and expects it to be 2.1.0",
    "test_a_revised_result_says_it_is_2_1_1_and_a_default_one_2_1_0":
        "expects the default core to report 2.1.0",
    "test_r1_the_168_fault_created_supported_are_withheld_on_real_ticks":
        "uses Corrections() as its 2.1.0 control",
    "test_r1_attribution_is_never_changed_by_the_fault_policy":
        "uses Corrections() as its 2.1.0 control (still identical: R-1 never changes attribution)",
    "test_r1_a_failed_refuter_of_the_supported_hypothesis_withholds_it":
        "uses Corrections() as its 2.1.0 control",
    "test_r1_a_material_refuter_failure_never_creates_a_supported":
        "uses Corrections() as its 2.1.0 control",
    "test_r3_epochs_are_ignored_entirely_by_a_2_1_0_core":
        "uses Corrections() as its 2.1.0 control",
    "test_r2_no_pacing_declaration_gives_no_answer_and_no_fallback_to_links":
        "unaffected by design; listed only if it fails",
}
PROPERTY = re.compile(r"test_P\d")
#: Property tests whose 2.1.0 statement R-1 supersedes by definition, with
#: the replacement property checked by `p5_prime()` (and pinned in
#: tests/test_semantic_core_2_1_revision.py).
SUPERSEDED = {
    "test_P5_every_injected_fault_is_reported_where_it_is_evaluated":
        "P5 has two clauses: (a) a fault is reported wherever the predicate is "
        "evaluated; (b) a fault decides exactly what a None return decides. R-1 "
        "is, by definition, the rule that a FAULTED refuter of the supported "
        "hypothesis withholds it while a merely UNMEASURED one does not, so (b) "
        "cannot hold as an equality. Replacement P5': (a) unchanged, and (b') a "
        "fault never decides anything MORE certain than a None return: every "
        "difference is a SUPPORTED withheld as WITHHELD_PREDICATE_FAULT with "
        "the same survivors, and attribution is identical",
}


def run(f, plugin):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(RC.HERE), env.get("PYTHONPATH", "")])
    cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-rf",
           "-p", "no:cacheprovider", f]
    if plugin:
        cmd[3:3] = ["-p", "revised_defaults_pytest_plugin"]
    p = subprocess.run(cmd, cwd=RC.REPO, capture_output=True, text=True, env=env)
    failed = sorted(set(re.findall(r"^FAILED \S+::(\S+?)(?:\[| - |$)", p.stdout, re.M)))
    tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:]
    passed = re.search(r"(\d+) passed", tail)
    return {"exit": p.returncode, "summary": tail,
            "passed": int(passed.group(1)) if passed else 0, "failed": failed}


def p5_prime():
    """P5' over P5's own injection: every base predicate of the frozen table
    raises, on the final tick of every shipped scenario, under 2.1.1."""
    import semantic_probe as P
    from csia.v2 import signatures as SIG
    from csia.v2.localization import Predicate
    from csia.v2.profiles import SCENARIOS
    from csia_semantic_core import Corrections, SemanticCore21

    def boom(i, s):
        raise KeyError("defect")
    rev = Corrections.revised()
    finals = [(n, *P.run_scenario(SCENARIOS[n])) for n in sorted(SCENARIOS)]
    pids = sorted(p for p in SIG.PREDICATES if not p.endswith("_FALSE"))
    out = {"injections": 0, "evaluated": 0, "reported": 0, "identical": 0,
           "withheld_only": 0, "more_certain_than_none": 0,
           "attribution_differs": 0, "withheld_names_the_fault": 0, "examples": []}
    for pid in pids:
        for name, engine, res in finals:
            records = tuple(res[-1].records)
            preds = dict(engine.predicates)
            preds[pid] = Predicate(pid, "", "X", boom)
            as_none = dict(engine.predicates)
            as_none[pid] = Predicate(pid, "", "X", lambda i, s: None)
            tf = SemanticCore21(engine.symptoms, preds, engine.relations, rev,
                                trace=False).reason(records)
            tn = SemanticCore21(engine.symptoms, as_none, engine.relations, rev,
                                trace=False).reason(records)
            out["injections"] += 1
            if P.aproj(tf.attribution.v2) != P.aproj(tn.attribution.v2):
                out["attribution_differs"] += 1
            nn = {x.key: x for x in tn.localizations}
            for x in tf.localizations:
                vals = x.v2.detail["predicate_values"]
                if pid in vals or pid + "_FALSE" in vals:
                    out["evaluated"] += 1
                    out["reported"] += int(x.evaluation == "PREDICATE_FAULT" and pid in
                                           {e.predicate for e in x.predicate_errors})
                y = nn[x.key]
                if P.lproj(x.v2) == P.lproj(y.v2):
                    out["identical"] += 1
                elif (x.outcome == "WITHHELD_PREDICATE_FAULT" and y.outcome == "SUPPORTED"
                      and set(x.supported) | set(x.unresolved) == set(y.supported) | set(y.unresolved)):
                    out["withheld_only"] += 1
                    out["withheld_names_the_fault"] += int(any(
                        e["predicate"] == pid for e in x.fault_impact
                        if e["action"] == "SUPPORTED_WITHHELD"))
                    if len(out["examples"]) < 5:
                        out["examples"].append([pid, name, x.key])
                else:
                    out["more_certain_than_none"] += 1
    out["P5_prime_holds"] = (out["evaluated"] == out["reported"] > 0
                             and out["more_certain_than_none"] == 0
                             and out["attribution_differs"] == 0
                             and out["withheld_names_the_fault"] == out["withheld_only"])
    return out


def main():
    out = {"harness": "semantic_core_2_1_revision_property_rerun", "files": {}}
    blocking = []
    for f in FILES:
        as_is, rev = run(f, False), run(f, True)
        only_rev = sorted(set(rev["failed"]) - set(as_is["failed"]))
        rows = []
        for t in only_rev:
            why = EXPECTED.get(t) or SUPERSEDED.get(t)
            prop = bool(PROPERTY.match(t))
            rows.append({"test": t, "property_test": prop,
                         "superseded_by_R1": t in SUPERSEDED,
                         "expected": why is not None,
                         "why": why or "NOT EXPECTED"})
            if why is None or (prop and t not in SUPERSEDED):
                blocking.append(f"{f}::{t}")
        out["files"][f] = {"as_is": as_is, "revised_default": rev,
                           "fail_only_under_revised": rows}
        print(f, "as-is:", as_is["summary"], "| revised:", rev["summary"])
        for r in rows:
            print("   ", r["test"], "->", r["why"])
    out["P5_prime"] = p5_prime()
    out["property_tests_weakened"] = [b for b in blocking if PROPERTY.search(b)]
    if not out["P5_prime"]["P5_prime_holds"]:
        out["property_tests_weakened"].append("P5 (replacement P5' fails)")
    out["unexpected_failures"] = blocking
    out["NO_PROPERTY_WEAKENED"] = not out["property_tests_weakened"]
    print("P5'", {k: v for k, v in out["P5_prime"].items() if k != "examples"})
    RC.write_json(OUT, out)
    print("unexpected:", blocking)


if __name__ == "__main__":
    sys.exit(main())
