"""Mutation testing for the mission layer: would the tests NOTICE a defect?

WHY THIS AND NOT COVERAGE
--------------------------
Coverage says a line RAN. It does not say that changing the line would fail a
test. A suite can execute every statement in a module and assert nothing about
any of them, and it will report 100%.

Mutation testing asks the question coverage cannot:

    if this operator were wrong, would anything go red?

A mutant that survives is a line the tests execute and do not constrain. That
is where a real defect would hide.

THE OPERATORS
-------------
Deliberately small and semantic, aimed at the kinds of mistake this layer is
actually vulnerable to:

    COMPARISON       >  <->  >=,  <  <->  <=,  ==  <->  !=
    BOOLEAN          True <-> False
    BOOL_OP          and <-> or
    STATE_CONSTANT   SUPPORTED <-> DEGRADED_SUPPORTED <-> UNKNOWN <->
                     NOT_SUPPORTED
    MEMBERSHIP       in <-> not in

The state-constant operator is the one that matters most here. The whole
layer is a state machine over five words, and swapping two of them is exactly
the defect class the programme is about -- UNKNOWN promoted to SUPPORTED is
one mutation.

HONEST LIMITS, BECAUSE A SCORE INVITES OVERREADING
----------------------------------------------------
* EQUIVALENT MUTANTS ARE NOT DETECTED. Some surviving mutants change no
  behaviour at all and cannot be killed by any test. They are counted as
  survivors, so the score reported here is a LOWER BOUND on test quality.
* It mutates the mission layer only. The frozen core is not touched, by rule
  and by the path filter.
* A high score means the tests constrain the code. It does not mean the code
  is right -- a well-tested wrong definition scores perfectly.

    python tools/xr/mutation_probe.py --out <json>
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: Mutated. The mission layer ONLY -- the frozen core is never touched.
TARGETS = (
    "csia_mission/capability.py",
    "csia_mission/product.py",
    "csia_mission/planner.py",
    "csia_mission/recovery.py",
    "csia_mission/reconfiguration.py",
    "csia_mission/graphs.py",
    "csia_mission/compute.py",
    "csia_mission/forge_seed.py",
)

#: Run against each mutant. Fast on purpose: a slow probe is a probe nobody
#: runs, and a probe nobody runs measures nothing.
TEST_SUBSET = (
    "tests/test_mission_assurance.py",
    "tests/test_mission_untested_modules.py",
    "tests/test_mission_boundaries.py",
    "tests/test_mission_survivor_kills.py",
    "tests/test_bad_product_references.py",
)

_CMP_SWAP = {
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}

_STATES = ["SUPPORTED", "DEGRADED_SUPPORTED", "NOT_SUPPORTED", "UNKNOWN",
           "NOT_EVALUABLE"]


class _Mutator(ast.NodeTransformer):
    """Applies exactly ONE mutation, identified by index."""

    def __init__(self, target_index: int):
        self.target_index = target_index
        self.seen = 0
        self.applied = None

    def _hit(self, kind: str, detail: str, lineno: int) -> bool:
        match = self.seen == self.target_index
        if match:
            self.applied = {"kind": kind, "detail": detail, "line": lineno}
        self.seen += 1
        return match

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            swap = _CMP_SWAP.get(type(op))
            if swap and self._hit("COMPARISON",
                                  f"{type(op).__name__} -> {swap.__name__}",
                                  node.lineno):
                node.ops[i] = swap()
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        new = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        if self._hit("BOOL_OP",
                     f"{type(node.op).__name__} -> {type(new).__name__}",
                     node.lineno):
            node.op = new
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self._hit("BOOLEAN", f"{node.value} -> {not node.value}",
                         node.lineno):
                return ast.copy_location(ast.Constant(not node.value), node)
        elif isinstance(node.value, str) and node.value in _STATES:
            other = _STATES[(_STATES.index(node.value) + 1) % len(_STATES)]
            if self._hit("STATE_CONSTANT", f"{node.value} -> {other}",
                         node.lineno):
                return ast.copy_location(ast.Constant(other), node)
        return node


def _count_sites(source: str) -> int:
    m = _Mutator(-1)
    m.visit(ast.parse(source))
    return m.seen


def _mutate(source: str, index: int):
    tree = ast.parse(source)
    m = _Mutator(index)
    tree = m.visit(tree)
    if m.applied is None:
        return None, None
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), m.applied


def _run_subset(workdir: str) -> bool:
    """True when the suite PASSES (the mutant survived)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TEST_SUBSET, "-q", "-x",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=workdir, capture_output=True, text=True, timeout=300)
    return proc.returncode == 0


def run(sample: int = 60, seed: int = 20260907) -> dict:
    rng = random.Random(seed)

    sites = []
    for rel in TARGETS:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            src = fh.read()
        n = _count_sites(src)
        sites.extend((rel, i) for i in range(n))

    total_sites = len(sites)
    chosen = sites if sample >= total_sites else rng.sample(sites, sample)
    chosen.sort()

    killed, survived, invalid = [], [], []

    with tempfile.TemporaryDirectory(prefix="csia-mutation-") as tmp:
        work = os.path.join(tmp, "repo")
        # A copy, so nothing can mutate the real tree even if this crashes.
        shutil.copytree(ROOT, work, symlinks=True, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "build", "*.pyc"))

        # A test path that does not exist makes pytest exit 4 (usage error),
        # which `_run_subset` reads as "tests failed" -- i.e. as a KILL. The
        # baseline check below would catch it, but only as an opaque "the
        # unmutated copy does not pass", sending the reader hunting for a
        # broken test that is really just a typo in --tests. Name it.
        missing = [t for t in TEST_SUBSET
                   if not os.path.exists(os.path.join(work, t))]
        if missing:
            return {"error": f"test path(s) do not exist: {missing}. pytest "
                             f"would exit 4 and every mutant would read as "
                             f"KILLED.", "aborted": True,
                    "missing_test_paths": missing}

        # Sanity: the UNMUTATED copy must pass, or every "kill" is spurious.
        if not _run_subset(work):
            return {"error": "the unmutated copy does not pass; every kill "
                             "would be spurious", "aborted": True}

        for rel, index in chosen:
            path = os.path.join(work, rel)
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                original = fh.read()
            mutated, applied = _mutate(original, index)
            if mutated is None:
                invalid.append({"file": rel, "index": index})
                continue
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(mutated)
                record = {"file": rel, "index": index, **applied}
                if _run_subset(work):
                    survived.append(record)
                else:
                    killed.append(record)
            except (SyntaxError, OSError) as exc:      # pragma: no cover
                invalid.append({"file": rel, "index": index,
                                "error": str(exc)})
            finally:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(original)

    evaluated = len(killed) + len(survived)
    by_file = {}
    for rec in killed + survived:
        e = by_file.setdefault(rec["file"], {"killed": 0, "survived": 0})
        e["killed" if rec in killed else "survived"] += 1
    for rel, e in by_file.items():
        n = e["killed"] + e["survived"]
        e["score"] = round(e["killed"] / n, 3) if n else None

    by_kind = {}
    for rec in killed + survived:
        e = by_kind.setdefault(rec["kind"], {"killed": 0, "survived": 0})
        e["killed" if rec in killed else "survived"] += 1
    for kind, e in by_kind.items():
        n = e["killed"] + e["survived"]
        e["score"] = round(e["killed"] / n, 3) if n else None

    return {
        "schema": "csia.mission.mutation_probe/1",
        "targets": list(TARGETS),
        "test_subset": list(TEST_SUBSET),
        "total_mutation_sites": total_sites,
        "sampled": len(chosen),
        "seed": seed,
        "evaluated": evaluated,
        "killed": len(killed),
        "survived": len(survived),
        "invalid": len(invalid),
        "mutation_score": round(len(killed) / evaluated, 4) if evaluated
        else None,
        "by_file": dict(sorted(by_file.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "surviving_mutants": survived,
        "what_the_score_means": (
            "the fraction of injected defects that at least one test "
            "noticed. A survivor is a line the tests EXECUTE and do not "
            "CONSTRAIN."),
        "what_it_does_not_mean": (
            "that the code is right. A well-tested wrong definition scores "
            "perfectly. This bounds test sensitivity, not correctness."),
        "why_it_is_a_lower_bound": (
            "EQUIVALENT MUTANTS ARE NOT DETECTED. Some survivors change no "
            "behaviour at all and cannot be killed by any test, so they "
            "count against the score without being real gaps."),
        "frozen_core_untouched": (
            "the target list contains only csia_mission paths, and the probe "
            "runs against a COPY of the tree"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--targets", default=None,
                    help="comma-separated paths to mutate instead of the "
                         "mission layer; used to measure a BASELINE against "
                         "an earlier body of work")
    ap.add_argument("--tests", default=None,
                    help="comma-separated test files to run per mutant")
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    if args.targets:
        globals()["TARGETS"] = tuple(args.targets.split(","))
    if args.tests:
        globals()["TEST_SUBSET"] = tuple(args.tests.split(","))
    doc = run(args.sample, args.seed)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    if not doc.get("aborted"):
        print(f"\nmutation score {doc['mutation_score']}  "
              f"({doc['killed']} killed / {doc['evaluated']} evaluated, "
              f"{doc['survived']} survived, of {doc['total_mutation_sites']} "
              f"sites)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
