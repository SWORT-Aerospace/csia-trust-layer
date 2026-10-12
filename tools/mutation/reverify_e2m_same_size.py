"""Re-measure E2M's three SAME-SIZE mutants under a hardened procedure.

WHY ONLY THREE
--------------
FL-042: CPython validates a cached `.pyc` against the source's
`(mtime, size)`. A mutation whose replacement is the SAME LENGTH as what it
replaces, restored inside one mtime tick, leaves the interpreter reusing the
MUTATED bytecode -- the restore silently does nothing and every later mutant
is "killed" by damage that is not its own.

The defect can therefore only bite where a replacement is the same length.
Across `run_e2m_mutations.py` that is exactly three mutants:

    SUP-01  csia_consequence/support.py           "^" -> "|"
    SUP-05  csia_consequence/gates.py             "==" -> "!="
    P3-07   csia_consequence/consequence_model.py two branches swapped

Those three, and the mutants that ran after them, are the only part of
38/36/2 the defect could have touched. This runner re-measures the three.

WHAT IS HARDENED, AND WHY EACH
--------------------------------
1. **A FRESH SANDBOX PER MUTANT.** Not a shared worktree with restores --
   there is no restore step to get wrong, because no mutant ever sees a tree
   another mutant touched. This is the strongest available isolation and it
   removes the FL-042 mechanism by construction rather than by remembering to
   purge.
2. **`PYTHONDONTWRITEBYTECODE=1`.** No `.pyc` is written at all, so none can
   be stale.
3. **`__pycache__` purged** before each run anyway, in case the checkout
   carried one in.
4. **Baseline verified in its own fresh sandbox**, exit 0 required.
5. **Canary in its own fresh sandbox**, must die.
6. **Every kill must name a test node.** A kill whose first failure is a bare
   file is a collection error, not a behavioural kill, and is classified as
   such rather than counted.
7. **Outcomes are distinguished**, never collapsed: `KILLED` (behavioural),
   `SURVIVED`, `INVALID_MUTANT` (anchor absent), `COLLECTION_ERROR`,
   `TIMEOUT`.

WHAT THIS DOES NOT DO
---------------------
It does not modify `csia_e2m/`, `csia_bus_provenance/`, the frozen core, the
original `E2M_MUTATION_RESULTS.json`, or any locked campaign. It does not
re-run the other 35 mutants and makes no claim about them. It writes its own
artifact; the original stays exactly as published, because "it was re-run and
agreed" is a different fact from "it was right".

    python tools/mutation/reverify_e2m_same_size.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "mutation"))

PYTHON = os.path.join(ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

TARGETS = ("SUP-01", "SUP-05", "P3-07")


def _interpreter_version():
    """The version of the interpreter the sandboxes actually run under."""
    out = subprocess.run([PYTHON, "-c", "import sys;print(sys.version.split()[0])"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_e2m():
    """Import the ORIGINAL runner and take its mutants verbatim.

    Restating the mutants here would let this file and the published one
    drift, and then the re-measurement would be of something else.
    """
    import importlib.util
    path = os.path.join(ROOT, "tools", "mutation", "run_e2m_mutations.py")
    spec = importlib.util.spec_from_file_location("_e2m_orig", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_sandbox() -> str:
    """A fresh detached worktree. One per mutant, never reused."""
    box = tempfile.mkdtemp(prefix="csia-e2m-reverify-")
    wt = os.path.join(box, "wt")
    subprocess.run(["git", "worktree", "add", "--detach", wt, "HEAD"],
                   cwd=ROOT, check=True, capture_output=True)
    return box


def drop_sandbox(box: str) -> None:
    wt = os.path.join(box, "wt")
    subprocess.run(["git", "worktree", "remove", "--force", wt],
                   cwd=ROOT, capture_output=True)
    shutil.rmtree(box, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=ROOT,
                   capture_output=True)


def sync_uncommitted(wt: str, paths) -> int:
    """Copy working-tree versions of the files that matter into the sandbox.

    The worktree is created at HEAD, so anything uncommitted would otherwise
    be invisible. Copying is explicit and the count is recorded.
    """
    n = 0
    for rel in paths:
        src = os.path.join(ROOT, rel)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(wt, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def purge_bytecode(root: str) -> int:
    removed = 0
    for dirpath, dirnames, _files in os.walk(root):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)
                removed += 1
    return removed


FIRST_FAIL = re.compile(r"^(FAILED|ERROR)\s+(\S+)", re.M)
COLLECT_ERR = re.compile(r"errors? during collection|ImportError while importing|"
                         r"INTERNALERROR", re.I)



def contamination_signature(published, same_size_ids):
    """Look for FL-042's fingerprint in the PUBLISHED run, without rerunning it.

    Re-measuring a same-size mutant in isolation confirms that mutant only.
    FL-042 does not damage the mutant that triggers it -- it damages the run
    that comes AFTER, which can inherit the previous mutant's bytecode and be
    scored a kill on a test that belongs to its predecessor. So the question
    the isolated reruns cannot answer is asked here instead, of the published
    record: does that inheritance show up anywhere in it?

    Three marks would show it:
      * a kill attributed to a bare file rather than a named test node
        (contamination often fails at import, before any node exists);
      * a run of three or more consecutive mutants killed by one same node
        (one leaked module killing everything downstream of it);
      * a same-size mutant's immediate successor scored a kill on the very
        node that killed its predecessor -- which is what a leaked .pyc
        produces, since the predecessor's own test goes on failing.

    Absence of all three is evidence, not proof: it is what an uncontaminated
    run looks like, and it does not license any claim about mutants that were
    never re-measured.
    """
    rows = published["results"]
    order = [r["id"] for r in rows]
    by_id = {r["id"]: r for r in rows}

    kills = [r for r in rows if r["verdict"] == "KILLED"]
    bare = [r["id"] for r in kills if not r.get("first_failure_is_test_node")]

    runs, run = [], []
    for r in rows:
        node = r.get("first_failure") if r["verdict"] == "KILLED" else None
        if node and run and run[-1][1] == node:
            run.append((r["id"], node))
        else:
            if len(run) >= 3:
                runs.append({"node": run[0][1], "ids": [i for i, _ in run]})
            run = [(r["id"], node)] if node else []
    if len(run) >= 3:
        runs.append({"node": run[0][1], "ids": [i for i, _ in run]})

    followers = []
    for mid in same_size_ids:
        i = order.index(mid)
        if i + 1 >= len(order):
            followers.append({"mutant": mid, "follower": None})
            continue
        fid = order[i + 1]
        f, m = by_id[fid], by_id[mid]
        f_node = f.get("first_failure") or ""
        # The precise fingerprint: if the predecessor's mutated bytecode were
        # still loaded, the predecessor's OWN test would fail again, so the
        # follower would be scored a kill on the predecessor's node. Matching
        # test filenames to target modules was tried first and rejected: the
        # repository does not name test files after the modules they exercise
        # (P3-08 targets research/consequence/phase3/ and is tested by
        # tests/test_consequence_phase3.py), so that rule reported a mark
        # where there was none. Node identity needs no naming convention.
        followers.append({
            "mutant": mid,
            "mutant_first_failure": m.get("first_failure"),
            "follower": fid,
            "follower_target": f["path"],
            "follower_verdict": f["verdict"],
            "follower_first_failure": f_node or None,
            "follower_repeated_predecessors_node":
                bool(f_node) and f_node == m.get("first_failure"),
        })

    marks = bool(bare) or bool(runs) or any(
        f.get("follower_repeated_predecessors_node") for f in followers)
    return {
        "what_this_asks": ("whether the PUBLISHED 38-mutant run carries "
                           "FL-042's fingerprint, which the three isolated "
                           "reruns cannot show"),
        "kills": len(kills),
        "distinct_first_failure_nodes": len(
            {r["first_failure"] for r in kills if r.get("first_failure")}),
        "kills_attributed_to_a_bare_file": bare,
        "runs_of_length_3_or_more": runs,
        "same_size_followers": followers,
        "signature_found": marks,
        "evidence_is_not_proof": (
            "No signature means the published run looks uncontaminated. It "
            "does not re-measure the 35 mutants that were not rerun, and no "
            "claim about them rests on it."),
    }


def run_selection(wt: str, selection, timeout: int) -> dict:
    """Run the selection in a sandbox with bytecode writing DISABLED."""
    env = dict(os.environ)
    env["PYTHONPATH"] = wt + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"      # no .pyc can be written
    env.pop("PYTHONPYCACHEPREFIX", None)
    purge_bytecode(wt)
    started = time.time()
    try:
        proc = subprocess.run(
            [PYTHON, "-m", "pytest", "-x", "-q", "--no-header",
             "-p", "no:cacheprovider", *selection],
            cwd=wt, env=env, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout + proc.stderr
        rc = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode(errors="replace") if isinstance(
            exc.stdout, bytes) else (exc.stdout or "")
        rc, timed_out = -9, True
    m = FIRST_FAIL.search(out)
    return {
        "returncode": rc,
        "timed_out": timed_out,
        "first_failure": m.group(2) if m else None,
        "collection_error": bool(COLLECT_ERR.search(out)),
        "seconds": round(time.time() - started, 1),
        "tail": out.strip().splitlines()[-6:],
    }


def classify(outcome: dict) -> str:
    """Never collapse the outcomes. Each is a different fact."""
    if outcome["timed_out"]:
        return "TIMEOUT"
    if outcome["collection_error"]:
        return "COLLECTION_ERROR"
    if outcome["returncode"] == 0:
        return "SURVIVED"
    first = outcome["first_failure"]
    if not first or "::" not in first:
        return "COLLECTION_ERROR"          # a kill with no named test node
    return "KILLED"


def one_mutant(mutant, selection, extra_sync, timeout: int) -> dict:
    """One mutant, one FRESH sandbox. No restore step exists to get wrong."""
    box = make_sandbox()
    wt = os.path.join(box, "wt")
    try:
        synced = sync_uncommitted(wt, extra_sync)
        path = os.path.join(wt, mutant["path"])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.count(mutant["old"]) != 1:
            return {"verdict": "INVALID_MUTANT",
                    "why": f"anchor appears {text.count(mutant['old'])} times",
                    "synced": synced}
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(mutant["old"], mutant["new"], 1))
        outcome = run_selection(wt, selection, timeout)
        return {"verdict": classify(outcome), "synced": synced, **outcome}
    finally:
        drop_sandbox(box)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "bus_provenance", "results",
        "E2M_SAME_SIZE_REVERIFY_FL042.json"))
    ap.add_argument("--timeout", type=int, default=2400)
    args = ap.parse_args(argv)

    orig = _load_e2m()
    selection = [s for s in orig.SELECTION
                 if os.path.isfile(os.path.join(ROOT, s))]
    by_id = {m["id"]: m for m in orig.MUTANTS}
    wanted = [by_id[t] for t in TARGETS]
    for m in wanted:
        assert len(m["old"]) == len(m["new"]), (
            f"{m['id']} is not same-size; this runner exists only for those")

    published = json.load(open(os.path.join(
        ROOT, "research/bus_provenance/results/E2M_MUTATION_RESULTS.json"),
        encoding="utf-8"))
    was = {r["id"]: r for r in published["results"]}

    #: Files that may be uncommitted and must reach the sandbox.
    extra = sorted({m["path"] for m in orig.MUTANTS} | set(selection))

    started = time.time()

    # --- 1. baseline, in its OWN fresh sandbox -------------------------
    box = make_sandbox()
    try:
        synced = sync_uncommitted(os.path.join(box, "wt"), extra)
        baseline = run_selection(os.path.join(box, "wt"), selection,
                                 args.timeout)
    finally:
        drop_sandbox(box)
    print(f"  baseline        exit {baseline['returncode']}  "
          f"{baseline['seconds']}s")
    if baseline["returncode"] != 0:
        raise SystemExit(
            "ABORT: the UNMUTATED selection does not pass in a fresh "
            f"sandbox (first failure {baseline['first_failure']!r}). "
            "Refusing to report.")

    # --- 2. canary, in its OWN fresh sandbox ---------------------------
    canary_spec = dict(orig.CANARY) if hasattr(orig, "CANARY") else None
    if canary_spec is None:
        raise SystemExit("ABORT: the original runner declares no canary")
    canary = one_mutant(canary_spec, selection, extra, args.timeout)
    print(f"  CANARY          {canary['verdict']:16s} "
          f"{canary.get('first_failure') or ''}")
    if canary["verdict"] != "KILLED":
        raise SystemExit(
            f"ABORT: the canary did not die ({canary['verdict']}).")

    # --- 3. the three, each in its OWN fresh sandbox --------------------
    results = []
    for mutant in wanted:
        got = one_mutant(mutant, selection, extra, args.timeout)
        before = was.get(mutant["id"], {})
        row = {
            "id": mutant["id"], "family": mutant["family"],
            "path": mutant["path"],
            "same_size": True,
            "breaks": mutant["breaks"],
            "reverified_verdict": got["verdict"],
            "reverified_first_failure": got.get("first_failure"),
            "published_verdict": before.get("verdict"),
            "published_first_failure": before.get("first_failure"),
            "verdict_changed": got["verdict"] != before.get("verdict"),
            "node_changed": (got.get("first_failure")
                             != before.get("first_failure")),
            "seconds": got.get("seconds"),
            "sandbox_was_fresh": True,
        }
        results.append(row)
        flag = "" if not (row["verdict_changed"] or row["node_changed"]) \
            else "  <-- CHANGED"
        print(f"  {mutant['id']:8s}        {got['verdict']:16s} "
              f"{got.get('first_failure') or ''}{flag}")

    changed = [r for r in results if r["verdict_changed"] or r["node_changed"]]
    document = {
        "schema": "csia.e2m.same_size_reverification/1",
        "why": ("FL-042: a same-length replacement restored inside one mtime "
                "tick can leave CPython reusing the MUTATED .pyc. Only "
                "same-size mutants can trigger it; these are E2M's three."),
        "is_a_rerun_not_a_replacement": True,
        "original_artifact": "research/bus_provenance/results/E2M_MUTATION_RESULTS.json",
        "original_result": {"evaluated": published["evaluated"],
                            "killed": published["killed"],
                            "survived": published["survived"]},
        "original_is_unmodified": True,
        "scope": {"re_measured": list(TARGETS),
                  "not_re_measured": sorted(
                      set(by_id) - set(TARGETS)),
                  "claims_nothing_about_the_others": True},
        "hardening": {
            "fresh_sandbox_per_mutant": True,
            "no_restore_step_exists": True,
            "pythondontwritebytecode": True,
            "pycache_purged_before_every_run": True,
            "baseline_in_its_own_fresh_sandbox": True,
            "canary_in_its_own_fresh_sandbox": True,
            "outcomes_distinguished": ["KILLED", "SURVIVED", "INVALID_MUTANT",
                                       "COLLECTION_ERROR", "TIMEOUT"],
            "a_kill_without_a_named_test_node_is_a_collection_error": True,
        },
        "selection": selection,
        "interpreter": {
            "reverification_ran_on": _interpreter_version(),
            "executable": os.path.relpath(PYTHON, ROOT)
            if PYTHON.startswith(ROOT) else PYTHON,
            "original_artifact_records_no_interpreter": True,
            "note": ("The published E2M artifact does not record the "
                     "interpreter it ran on, so this field states what THIS "
                     "re-measurement used and claims nothing about the "
                     "original run's interpreter."),
        },
        "baseline_unmutated": {"returncode": baseline["returncode"],
                               "seconds": baseline["seconds"]},
        "canary": {"verdict": canary["verdict"],
                   "first_failure": canary.get("first_failure")},
        "results": results,
        "contamination_signature_analysis": contamination_signature(
            published, list(TARGETS)),
        "verdicts_changed": len(changed),
        "changed": [r["id"] for r in changed],
        "all_kills_name_a_test_node": all(
            r["reverified_first_failure"] and "::" in r["reverified_first_failure"]
            for r in results if r["reverified_verdict"] == "KILLED"),
        "collection_errors": sum(1 for r in results
                                 if r["reverified_verdict"] == "COLLECTION_ERROR"),
        "timeouts": sum(1 for r in results
                        if r["reverified_verdict"] == "TIMEOUT"),
        "invalid": sum(1 for r in results
                       if r["reverified_verdict"] == "INVALID_MUTANT"),
        "elapsed_s": round(time.time() - started, 1),
        "what_this_is_not": (
            "not a re-measurement of the other 35 mutants, not a new score, "
            "and not a replacement for the published 38/36/2."),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"\n{len(results)} re-measured, {len(changed)} changed")
    print(f"wrote {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
