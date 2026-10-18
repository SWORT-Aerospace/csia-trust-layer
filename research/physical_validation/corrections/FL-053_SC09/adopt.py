#!/usr/bin/env python3
"""Adopt (or preview adopting) the FL-053 / SC-09 correction. TIER A only.

    # preview: prints the exact diff, writes nothing
    python research/physical_validation/corrections/FL-053_SC09/adopt.py

    # write a reviewable patch of the preview
    python research/physical_validation/corrections/FL-053_SC09/adopt.py --patch-out PATH

    # adopt: the owner only, under rule R8
    python research/physical_validation/corrections/FL-053_SC09/adopt.py --apply \\
        --decided-by "NAME" --decision-reference "WHERE THE DECISION IS RECORDED" \\
        --guard-pins-decision "HOW THE PINNED LEDGER-HASH GUARDS ARE HANDLED"

What --apply changes, and nothing else:
  1. appends FL-053.ledger_entry.yaml to research/physical_validation/FAILURE_LEDGER.yaml
  2. in each of the three sealed-phase manifests that pin the ledger, rewrites
     the ledger's SHA-256 and `head_at_build` (to the HEAD at adoption), and no
     other line -- the precedent of commits b7f1816, d69919d, c2aac29, 39dc509
  3. raises "ledger has N entries" by one in docs/FIELD_INTEGRATION_RUNBOOK.md
  4. appends PI-006 to research/physical_validation/PAPER_IMPACT_LEDGER.yaml
     with ready_to_integrate set to true
  5. adds a pointer note after the systems-paper gate table in
     docs/CURRENT_PROGRAM_STATE.md; the gate-9 row itself is not rewritten
  6. sets CORRECTION_RECORD.yaml status to ADOPTED with the decision fields

It never touches research/systems-paper/, the generator, the historical prose,
the handoffs, PRIME-1 or the evidence export, and it never commits. Tier B
(row 15 of the Paper I corrections ledger and an evidence-export rebuild) is a
separate decision described in README.md section 5.

It refuses if FL-053 is already used, if the ledger's FL series no longer ends
at FL-052 (the id must then be reassigned by the owner), if the record is not
PROPOSED, or if any pinned historical file has changed.

IT ALSO REFUSES --apply WHILE OTHER CODE PINS THE LEDGER'S EXACT HASH, unless
--guard-pins-decision names the owner's decision about them. The adoption
rehearsal found seven such pins (Semantic Core 2.1, 2.1.1 and shadow, CSIA 2.2
and the baseline verifiers built on it); an append changes the hash, so those
guards fail. This tool does not edit them. The preview lists them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

import yaml

PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(PKG, "..", "..", "..", ".."))
REL_PKG = os.path.relpath(PKG, ROOT)
LEDGER = "research/physical_validation/FAILURE_LEDGER.yaml"
MANIFESTS = ("research/consequence/phase32/SHA256_MANIFEST32.json",
             "research/phase4/SHA256_MANIFEST4.json",
             "research/phase5/SHA256_MANIFEST5.json")
RUNBOOK = "docs/FIELD_INTEGRATION_RUNBOOK.md"
IMPACT = "research/physical_validation/PAPER_IMPACT_LEDGER.yaml"
STATE = "docs/CURRENT_PROGRAM_STATE.md"
RECORD = os.path.join(REL_PKG, "CORRECTION_RECORD.yaml")
STATE_ANCHOR = "to `review.px4.io`). Neither is a research problem.\n"


def read(rel):
    # newline="" keeps CRLF and every other byte as committed, so hashes match git
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as fh:
        return fh.read()


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def ledger_code_pins(ledger_sha):
    """Tracked Python files outside this package that contain the ledger's hash."""
    out = subprocess.run(["git", "grep", "-l", ledger_sha, "--", "*.py"], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    return sorted(p for p in out if not p.startswith(REL_PKG.replace(os.sep, "/") + "/"))


def preflight(record):
    errs = []
    if record["status"] != "PROPOSED":
        errs.append(f"record status is {record['status']}, not PROPOSED")
    ids = [e["id"] for e in yaml.safe_load(read(LEDGER))["entries"]]
    if "FL-053" in ids:
        errs.append("FL-053 is already in the ledger")
    fl = sorted(int(i[3:]) for i in ids if i.startswith("FL-"))
    if fl and fl[-1] != 52:
        errs.append(f"the FL series ends at FL-{fl[-1]:03d}, not FL-052; the owner must reassign this entry's id")
    for rel, want in record["historical_record"]["pinned_files"].items():
        if sha_text(read(rel)) != want:
            errs.append(f"pinned historical file changed: {rel}")
    if "PI-006" in read(IMPACT):
        errs.append("PI-006 is already used in the paper impact ledger")
    if STATE_ANCHOR not in read(STATE):
        errs.append("the program-state anchor line was not found")
    return errs


def build(record, decided_by, reference, head, today, pins_decision=None):
    """Return {path: (old_text, new_text)} for every file tier A changes."""
    out = {}
    led_old = read(LEDGER)
    entry = read(os.path.join(REL_PKG, "FL-053.ledger_entry.yaml"))
    led_new = led_old if led_old.endswith("\n") else led_old + "\n"
    led_new += entry if entry.endswith("\n") else entry + "\n"
    parsed = yaml.safe_load(led_new)["entries"]
    assert parsed[-1]["id"] == "FL-053" and len(parsed) == len(yaml.safe_load(led_old)["entries"]) + 1
    out[LEDGER] = (led_old, led_new)

    old_sha, new_sha = sha_text(led_old), sha_text(led_new)
    for m in MANIFESTS:
        t = read(m)
        assert t.count(old_sha) == 1, f"{m}: ledger hash not pinned exactly once"
        t2 = t.replace(old_sha, new_sha)
        t2, n = re.subn(r'("head_at_build":\s*")[0-9a-f]{40}(")', rf"\g<1>{head}\g<2>", t2)
        assert n == 1, f"{m}: head_at_build not found exactly once"
        out[m] = (t, t2)

    rb = read(RUNBOOK)
    n_old = len(yaml.safe_load(led_old)["entries"])
    phrase = f"ledger has {n_old} entries"
    assert rb.count(phrase) == 1, f"{RUNBOOK}: '{phrase}' not found exactly once"
    out[RUNBOOK] = (rb, rb.replace(phrase, f"ledger has {n_old + 1} entries"))

    imp = read(IMPACT)
    row = read(os.path.join(REL_PKG, "PI-006.paper_impact_entry.yaml"))
    row = row.replace("    ready_to_integrate: false\n", "    ready_to_integrate: true\n", 1)
    row = re.sub(r"    ready_reason: >-\n(      .*\n)+",
                 f"    ready_reason: >-\n      Adopted {today} by {decided_by} ({reference}) under FL-053. The\n"
                 "      figures are committed, re-derived and verified; the wording is the\n"
                 "      writing agents'.\n", row, count=1)
    imp_new = (imp if imp.endswith("\n") else imp + "\n") + row
    assert yaml.safe_load(imp_new)["entries"][-1]["id"] == "PI-006"
    out[IMPACT] = (imp, imp_new)

    st = read(STATE)
    note = (STATE_ANCHOR + "\n> **Gate 9, objection 2.3 -- superseded by FL-053 (adopted "
            f"{today}).** The dwell subtraction that closed 2.3 was itself the error:\n"
            "> the raw trust crossing is already detector-only, so the comparison is\n"
            "> 2.96 vs 8.72, 1.16 vs 3.36 and 0.72 vs 3.24 s, and SC-09 holds by a wider\n"
            "> margin. Authoritative statement:\n"
            f"> `{REL_PKG}/CORRECTION_RECORD.yaml`.\n"
            "> The gate-9 row above is kept as written, as the record of what was asserted.\n")
    out[STATE] = (st, st.replace(STATE_ANCHOR, note, 1))

    rec = read(RECORD)
    rec2 = rec.replace("\nstatus: PROPOSED\n", "\nstatus: ADOPTED\n", 1)
    rec2 = rec2.replace("  decided_by: null\n", f"  decided_by: {json.dumps(decided_by)}\n", 1)
    rec2 = rec2.replace("  decided_on: null\n", f"  decided_on: {today}\n", 1)
    rec2 = rec2.replace("  decision_reference: null\n",
                        f"  decision_reference: {json.dumps(reference)}\n", 1)
    if pins_decision is not None:
        rec2 = rec2.replace("  guard_pins_decision: null\n",
                            f"  guard_pins_decision: {json.dumps(pins_decision)}\n", 1)
    rec2 = rec2.replace("  fl_053_in_ledger: false\n", "  fl_053_in_ledger: true\n", 1)
    rec2 = rec2.replace("\nadoption:\n",
                        f"\n  - date: {today}\n    status: ADOPTED\n    by: adopt.py --apply, "
                        f"HEAD before adoption {head}\n\nadoption:\n", 1)
    assert yaml.safe_load(rec2)["status"] == "ADOPTED"
    out[RECORD] = (rec, rec2)
    return out


def unified(changes):
    parts = []
    for rel, (a, b) in changes.items():
        parts.extend(difflib.unified_diff(a.splitlines(True), b.splitlines(True),
                                          fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--decided-by")
    ap.add_argument("--decision-reference")
    ap.add_argument("--guard-pins-decision")
    ap.add_argument("--patch-out")
    args = ap.parse_args(argv)

    record = yaml.safe_load(read(RECORD))
    errs = preflight(record)
    if errs:
        print("REFUSED:\n  " + "\n  ".join(errs))
        return 2
    if args.apply and not (args.decided_by and args.decision_reference):
        print("REFUSED: --apply needs --decided-by and --decision-reference (rule R8: the owner's decision)")
        return 2
    pins = ledger_code_pins(sha_text(read(LEDGER)))
    if args.apply and pins and not args.guard_pins_decision:
        print("REFUSED: these files pin the ledger's exact SHA-256 and fail on any append:\n  "
              + "\n  ".join(pins) + "\n--guard-pins-decision must name the owner's decision about them "
              "(README section 5, item f). This tool does not edit them.")
        return 2
    head = git("rev-parse", "HEAD")
    today = dt.date.today().isoformat()
    pins_decision = args.guard_pins_decision or ("<GUARD-PINS-DECISION>" if pins else None)
    changes = build(record, args.decided_by or "<OWNER>", args.decision_reference or "<DECISION-REFERENCE>",
                    head, today, pins_decision)
    diff = unified(changes)
    if args.patch_out:
        with open(args.patch_out, "w", encoding="utf-8", newline="") as fh:
            fh.write(diff)
        print(f"wrote {args.patch_out} ({len(changes)} files)")
    if not args.apply:
        if not args.patch_out:
            sys.stdout.write(diff)
        print(f"\nPREVIEW ONLY: {len(changes)} files would change; nothing was written.")
        if pins:
            print(f"ALSO REQUIRED (decision f): {len(pins)} files pin the ledger's exact SHA-256 and "
                  "would fail after the append; this tool does not edit them:\n  " + "\n  ".join(pins))
        return 0
    for rel, (_a, b) in changes.items():
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as fh:
            fh.write(b)
    print(f"ADOPTED in the working tree: {len(changes)} files changed. Review, run the suite, and commit.")
    if pins:
        print("NOT YET HANDLED: the ledger-hash guards below must be dealt with under the recorded "
              "guard-pins decision before the suite can pass:\n  " + "\n  ".join(pins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
