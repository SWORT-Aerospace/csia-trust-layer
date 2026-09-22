"""Create, validate and refresh BUILD_PROVENANCE.json under an evidence gate.

WHAT WAS ACTUALLY WRONG
-----------------------
`tools/assurance/build_provenance.py` emits the record. Its only guard is
`protected_write`, which refuses to clobber a committed artifact unless
`--regenerate` is passed. That guard protects against ACCIDENT. It does not
ask whether the tree the record describes is in a state worth recording, so
the record could be regenerated from a tree with a red suite, failing blocking
guards or a drifted frozen core, and would look exactly as authoritative as
one written from a good tree.

FL-048 asserted that a green-suite gate on this record made refreshing it
circular. That was wrong, and FL-049 records the correction: the green-suite
gate belongs to `tools/research/iv_followup_seal_record.py`, which writes a
DIFFERENT artifact (`FOLLOWUP_SEAL_OPENING_RECORD.md`). This record never had
such a gate. So nothing here removes a gate; this ADDS the one that was
missing, and adds it in a shape that cannot become circular.

WHY IT CANNOT BECOME CIRCULAR
------------------------------
The obvious way to add the gate is "refuse to write unless the suite exited
zero". Applied here that WOULD be circular, because the suite contains
`tests/test_post_e1_hardening_round2.py::test_the_build_provenance_describes_this_checkout`,
which fails precisely when the record needs rewriting. Requiring it to pass
before the write that makes it pass is a deadlock, and the tempting escapes --
a `--force` flag, an environment variable, deselecting the test, marking it
skip -- all amount to letting somebody declare the tree good instead of
showing it.

The resolution is that this one test is a CONSEQUENCE of the write, not a
precondition for it. So:

  * every other test must pass. The permitted failure set is empty or exactly
    {the provenance validation node}. Two failures, or one failure that is
    some other test, is a refusal.
  * the allowance is a hard-coded single node in this file. It is not a flag,
    not an option, not an environment variable, and nothing a caller passes
    can widen it.
  * after writing, that node is RE-RUN. If it still fails, the write is
    ROLLED BACK and the command exits nonzero. The allowance therefore cannot
    ship a record that does not satisfy the check it was allowed to bypass.

THE THREE OPERATIONS ARE SEPARATE
----------------------------------
    validate   read-only. Classifies the record and exits with a code that
               says which state it found. Writes nothing, ever.
    create     only when no record exists AND the path is untracked at HEAD.
    refresh    only when a record exists. A STALE record may be replaced, but
               never silently: the new record carries the digest and commit
               of what it superseded, and the operation says so on stderr.

EVIDENCE REQUIRED FOR ANY WRITE
--------------------------------
All four, every time, for both create and refresh:

    1. a recorded full-suite run whose failures are empty or exactly the
       provenance validation node
    2. blocking guards pass
    3. frozen-core digest identical to the freeze
    4. every required SHA256 manifest verifies

    python tools/assurance/provenance_workflow.py validate
    python tools/assurance/provenance_workflow.py create  --suite-output <p>
    python tools/assurance/provenance_workflow.py refresh --suite-output <p>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RECORD = os.path.join(ROOT, "research", "physical_validation", "results",
                      "BUILD_PROVENANCE.json")

#: The one test whose failure a write is allowed to resolve. Hard-coded,
#: single-valued, and deliberately not parameterised: the whole point is that
#: no caller can nominate a different test as "the one that does not count".
SELF_REFERENTIAL_NODE = ("tests/test_post_e1_hardening_round2.py::"
                         "test_the_build_provenance_describes_this_checkout")

#: Manifests that must verify before the record may be written. Each is a
#: {path: sha256} map produced by its own builder; this re-hashes the files
#: rather than trusting the manifest's own summary line.
REQUIRED_MANIFESTS = (
    "research/consequence/phase32/SHA256_MANIFEST32.json",
    "research/phase4/SHA256_MANIFEST4.json",
    "research/phase5/SHA256_MANIFEST5.json",
)

#: How far back the record's commit may sit. Mirrors the assertion in
#: tests/test_post_e1_hardening_round2.py; if that window changes, this must
#: change with it, and `validate` disagreeing with the test is itself a bug.
COMMIT_WINDOW = 3

ABSENT = "ABSENT"
VALID = "VALID"
STALE = "STALE"
DELETED = "DELETED"

#: validate's exit codes, distinct so a caller can act on the state.
EXIT = {VALID: 0, STALE: 1, ABSENT: 2, DELETED: 3}


def _git(*args, check=False):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip() if r.returncode == 0 else None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tracked_at_head(rel):
    """Is this path in HEAD's tree? Distinguishes 'never created' from
    'deleted', which is the difference between a first write and an attempt
    to reset a stale record by removing it."""
    out = _git("ls-tree", "-r", "--name-only", "HEAD", "--", rel)
    return bool(out)


# ------------------------------------------------------------------ validate

def classify(record_path=None):
    """The record's state, with the evidence for the classification.

    The path defaults to RECORD at CALL time, not at definition time. Binding
    it as a default argument captured the value at import and made the
    function deaf to any later change to the module global -- which is how a
    caller pointed at one record while this classified another.
    """
    record_path = record_path or RECORD
    rel = os.path.relpath(record_path, ROOT)
    head = _git("rev-parse", "HEAD")
    window = (_git("rev-list", f"--max-count={COMMIT_WINDOW}", "HEAD")
              or "").split()

    if not os.path.exists(record_path):
        if _tracked_at_head(rel):
            return DELETED, {
                "record": rel, "head": head,
                "why": ("the record is absent from the working tree but "
                        "present in HEAD. That is a DELETION, not a first "
                        "write. Creating a record here would replace a "
                        "committed one while reporting it as a creation, "
                        "which is exactly the silent replacement the "
                        "workflow exists to prevent."),
            }
        return ABSENT, {
            "record": rel, "head": head,
            "why": ("no record in the working tree and none in HEAD, so "
                    "this is a genuine first write"),
        }

    try:
        doc = json.load(open(record_path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return STALE, {"record": rel, "head": head,
                       "why": f"the record is unreadable: {exc}"}

    recorded = (doc.get("source") or {}).get("commit")
    fresh = bool(recorded) and (recorded == head or recorded in window)
    detail = {
        "record": rel, "head": head, "recorded_commit": recorded,
        "commit_window": window, "sha256": _sha256(record_path),
        "why": ("the recorded commit is HEAD or within the last "
                f"{COMMIT_WINDOW}" if fresh else
                f"the recorded commit {recorded} is not HEAD and not within "
                f"the last {COMMIT_WINDOW} commits"),
    }
    return (VALID if fresh else STALE), detail


# ------------------------------------------------------------------ evidence

def suite_evidence(suite_output):
    """Read a recorded pytest run. Empty failures, or exactly the one node."""
    if not os.path.exists(suite_output):
        return False, {"ok": False,
                       "why": f"no recorded suite run at {suite_output}"}
    text = open(suite_output, errors="replace").read()

    exit_match = re.search(r"PYTEST_EXIT=(\d+)", text)
    code = int(exit_match.group(1)) if exit_match else None
    if code is None:
        return False, {"ok": False, "why": (
            "the recorded run carries no PYTEST_EXIT= line, so its outcome "
            "cannot be read. Record it with "
            "`pytest -q > out.txt; echo PYTEST_EXIT=$? >> out.txt`.")}

    failed = sorted({ln.split(" ", 1)[1].split(" ")[0]
                     for ln in text.splitlines()
                     if ln.startswith(("FAILED ", "ERROR "))})
    collected = sum(line.count(".") for line in text.splitlines()
                    if re.fullmatch(r"[.sxX]+\s*(\[\s*\d+%\])?", line.strip()))

    allowed = {SELF_REFERENTIAL_NODE}
    unexplained = [f for f in failed if f not in allowed]

    detail = {"exit_code": code, "failed": failed,
              "tests_counted": collected,
              "self_referential_failure_allowed": SELF_REFERENTIAL_NODE,
              "unexplained_failures": unexplained,
              "why_one_node_is_allowed": (
                  "this node checks the very record the write produces, so "
                  "it is a consequence of the write rather than a "
                  "precondition for it. It is re-run after the write and the "
                  "write is rolled back if it still fails.")}

    if unexplained:
        detail["ok"] = False
        detail["why"] = (f"{len(unexplained)} failure(s) that this write "
                         f"does not resolve: {unexplained}")
        return False, detail
    if code != 0 and not failed:
        detail["ok"] = False
        detail["why"] = (f"the run exited {code} but named no failing test; "
                         f"an unexplained nonzero exit is not evidence of a "
                         f"good tree")
        return False, detail
    if collected <= 0:
        detail["ok"] = False
        detail["why"] = ("the recorded run counted no tests, so it is not "
                         "evidence of anything")
        return False, detail
    detail["ok"] = True
    detail["why"] = ("no failures" if not failed else
                     "the only failure is the node this write resolves")
    return True, detail


def guards_evidence():
    """`make check-blocking` must pass."""
    r = subprocess.run(["make", "check-blocking"], cwd=ROOT,
                       capture_output=True, text=True)
    passed = r.returncode == 0 and "BLOCKING GUARDS: PASS" in r.stdout
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith("###")]
    return passed, {"ok": passed, "exit_code": r.returncode,
                    "guards_seen": [t.replace("#", "").strip() for t in tail],
                    "why": ("blocking guards pass" if passed else
                            "blocking guards did not pass")}


def frozen_core_evidence():
    """The frozen core must be identical to the freeze."""
    from tools.assurance.build_provenance import _frozen_core_digests
    core = _frozen_core_digests()
    if "error" in core:
        return False, {"ok": False, "why": core["error"]}
    ok = bool(core.get("identical_to_the_freeze"))
    return ok, {"ok": ok,
                "paths_that_differ": core.get("paths_that_differ") or [],
                "not_verifiable": core.get("not_verifiable") or [],
                "why": ("frozen core identical to the freeze" if ok else
                        f"frozen core drifted on "
                        f"{core.get('paths_that_differ')}")}


def manifests_evidence():
    """Every required manifest must re-hash to what it records."""
    results, all_ok = {}, True
    for rel in REQUIRED_MANIFESTS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            results[rel] = {"ok": False, "why": "manifest absent"}
            all_ok = False
            continue
        doc = json.load(open(path, encoding="utf-8"))
        entries = doc.get("files") or doc.get("hashes") or {}
        if isinstance(entries, list):
            entries = {e["path"]: e["sha256"] for e in entries
                       if isinstance(e, dict) and "path" in e}
        mismatched, missing = [], []
        for frel, want in entries.items():
            digest = want["sha256"] if isinstance(want, dict) else want
            fpath = os.path.join(ROOT, frel)
            if not os.path.exists(fpath):
                missing.append(frel)
            elif _sha256(fpath) != digest:
                mismatched.append(frel)
        ok = not mismatched and not missing and bool(entries)
        results[rel] = {"ok": ok, "files": len(entries),
                        "mismatched": sorted(mismatched),
                        "missing": sorted(missing)}
        if not entries:
            results[rel]["why"] = ("the manifest lists no files, so "
                                   "verifying it proves nothing")
        all_ok = all_ok and ok
    return all_ok, {"ok": all_ok, "manifests": results}


def gather_evidence(suite_output, guards_runner=None):
    """All four preconditions. Every one is reported, pass or fail.

    `guards_runner` exists so the unit tests can exercise the other three
    preconditions without a multi-minute `make check-blocking`. The CLI never
    passes it, so there is no command-line or environment route to a relaxed
    evidence set: a caller who wants one has to edit this file, which is a
    reviewable change rather than an invocation.
    """
    ok_suite, suite = suite_evidence(suite_output)
    ok_guards, guards = (guards_runner or guards_evidence)()
    ok_core, core = frozen_core_evidence()
    ok_man, manifests = manifests_evidence()
    evidence = {"suite": suite, "blocking_guards": guards,
                "frozen_core": core, "manifests": manifests}
    return (ok_suite and ok_guards and ok_core and ok_man), evidence


def _print_evidence(evidence):
    for name, block in evidence.items():
        mark = "PASS" if block.get("ok") else "FAIL"
        print(f"  [{mark}] {name}: {block.get('why', '')}")
        for key in ("unexplained_failures", "paths_that_differ"):
            if block.get(key):
                print(f"           {key}: {block[key]}")
        if name == "manifests":
            for rel, r in (block.get("manifests") or {}).items():
                sub = "ok " if r.get("ok") else "FAIL"
                print(f"           [{sub}] {rel} ({r.get('files', 0)} files)")


# -------------------------------------------------------------------- writes

def _write_record(supersedes=None):
    """Emit through the existing generator and the existing write guard."""
    from tools.assurance.build_provenance import provenance
    from tools.evidence_guard import protected_write

    doc = provenance()
    if supersedes:
        doc["supersedes"] = supersedes
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    with protected_write(RECORD, regenerate=bool(supersedes)) as fh:
        fh.write(text)
    return doc


def _reverify_or_rollback(previous_bytes):
    """Re-run the one allowed-failing node. Roll back if it still fails."""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q",
                        SELF_REFERENTIAL_NODE],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        return True
    print("the written record does not satisfy the check the write was "
          "allowed to resolve; ROLLING BACK", file=sys.stderr)
    print(r.stdout[-1500:], file=sys.stderr)
    if previous_bytes is None:
        if os.path.exists(RECORD):
            os.remove(RECORD)
    else:
        with open(RECORD, "wb") as fh:
            fh.write(previous_bytes)
    return False


def cmd_validate(args):
    state, detail = classify()
    print(f"PROVENANCE RECORD: {state}")
    for k, v in detail.items():
        print(f"  {k}: {v}")
    return EXIT[state]


def cmd_create(args):
    state, detail = classify()
    if state != ABSENT:
        print(f"REFUSED: create requires no existing record; found {state}.",
              file=sys.stderr)
        print(f"  {detail.get('why')}", file=sys.stderr)
        if state in (VALID, STALE):
            print("  Use `refresh` to replace an existing record.",
                  file=sys.stderr)
        return 2

    ok, evidence = gather_evidence(args.suite_output)
    print("EVIDENCE FOR CREATION")
    _print_evidence(evidence)
    if not ok:
        print("REFUSED: the evidence set is incomplete; nothing written.",
              file=sys.stderr)
        return 1

    _write_record(supersedes=None)
    if not _reverify_or_rollback(None):
        return 1
    print(f"created {os.path.relpath(RECORD, ROOT)}")
    return 0


def cmd_refresh(args):
    state, detail = classify()
    if state == ABSENT:
        print("REFUSED: no record to refresh. Use `create`.", file=sys.stderr)
        return 2
    if state == DELETED:
        print("REFUSED: the record is absent from the working tree but "
              "present in HEAD.", file=sys.stderr)
        print(f"  {detail['why']}", file=sys.stderr)
        print("  Restore it with `git checkout -- <path>` and refresh that.",
              file=sys.stderr)
        return 2

    previous_bytes = open(RECORD, "rb").read()
    supersedes = None
    if state == STALE:
        supersedes = {
            "commit": detail.get("recorded_commit"),
            "sha256": detail.get("sha256"),
            "why": ("the superseded record named a commit outside the "
                    f"{COMMIT_WINDOW}-commit window"),
            "note": ("recorded so the replacement of a stale record is "
                     "visible in the artifact itself rather than only in "
                     "version control"),
        }
        print("NOTE: the existing record is STALE and will be REPLACED.")
        print(f"  superseding commit {supersedes['commit']} "
              f"sha256 {supersedes['sha256']}")
    else:
        supersedes = {
            "commit": detail.get("recorded_commit"),
            "sha256": detail.get("sha256"),
            "why": "routine refresh of a record that was still valid",
        }

    ok, evidence = gather_evidence(args.suite_output)
    print(f"EVIDENCE FOR REFRESH (existing record: {state})")
    _print_evidence(evidence)
    if not ok:
        print("REFUSED: the evidence set is incomplete; nothing written.",
              file=sys.stderr)
        return 1

    _write_record(supersedes=supersedes)
    if not _reverify_or_rollback(previous_bytes):
        return 1
    print(f"refreshed {os.path.relpath(RECORD, ROOT)} "
          f"(superseded {supersedes['commit']})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="classify the record; writes nothing")

    for name, help_text in (("create", "write a record where none exists"),
                            ("refresh", "replace an existing record")):
        p = sub.add_parser(name, help=help_text)
        # The ONLY option either write command takes. There is deliberately
        # no --force, no --allow-stale, no --skip-guards and no environment
        # variable: every one of those would let a caller ASSERT the tree is
        # good instead of SHOWING it, which is the failure mode this whole
        # file exists to prevent.
        p.add_argument("--suite-output", required=True,
                       help="a recorded full-suite run carrying PYTEST_EXIT=")

    args = ap.parse_args(argv)
    return {"validate": cmd_validate, "create": cmd_create,
            "refresh": cmd_refresh}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
