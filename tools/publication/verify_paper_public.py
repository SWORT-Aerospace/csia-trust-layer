#!/usr/bin/env python3
"""Reviewer-facing verification: what a referee can check, and what they cannot.

Peer-review hardening campaign, sections 16 and 24.

WHAT THIS IS FOR
----------------
A referee who downloads this repository has one question and no time: *which
of these numbers can I re-derive right now, from committed artifacts, without
a simulator, without network access, and without trusting the authors?*

Nothing answered that. The repository has thorough guards, but they are
addressed to maintainers: `make check` runs thirty things, most of which are
about packaging discipline, and a referee cannot tell from its output which
lines are evidence and which are hygiene.

This composes the checks that ARE evidence, per paper, and prints them as an
evidence capsule. It runs no simulator, writes no artifact, and needs no
network. It composes existing checks rather than reimplementing them, so it
cannot disagree with the guards it stands in front of.

IT ALSO PRINTS WHAT CANNOT BE VERIFIED, AND WHY
-----------------------------------------------
That half matters more. A capsule that lists only successes is an
advertisement. Every item under NOT VERIFIABLE below is a real limitation of
the evidence base, recorded elsewhere in the repository and repeated here so a
referee meets it at the same moment as the successes:

  * the bibliography: no publisher record was reachable from the authoring
    environment. Nothing is VERIFIED. `papers/BIB_VERIFICATION_LEDGER.yaml`
  * the public-log exposure study: NOT RUN. Every fetch route is blocked.
    `research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json`
  * the current-stack self-occlusion trials: n=1 per platform.
    `research/systems-paper/CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md`
  * the SITL campaigns: re-running them needs an autopilot binary this
    repository does not vendor.

Exit code is 0 only if every VERIFIABLE item passes. The NOT VERIFIABLE list
never affects the exit code -- it is a disclosure, not a failure.

Run:  python tools/publication/verify_paper_public.py --paper systems
      python tools/publication/verify_paper_public.py --paper math
      python tools/publication/verify_paper_public.py --paper both
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

#: (label, pytest node or script) pairs. Each entry is EVIDENCE: it re-derives
#: a number a paper states, or checks a structural property a paper claims.
#: Packaging, sanitisation and repository-hygiene guards are deliberately NOT
#: here -- they belong to `make check`, and mixing them in is what made the
#: existing output unreadable to a referee.
CHECKS = {
    "systems": [
        ("headline scalars re-derived from their artifacts",
         ["-m", "pytest", "-q", "tests/test_systems_paper_numeric_claims.py"]),
        ("every prose number is bound or audited",
         ["-m", "pytest", "-q", "tests/test_numeric_literal_audit_is_closed.py"]),
        ("figures and tables match the artifact map",
         ["tools/publication/artifact_map_check.py"]),
        ("prose numbers still equal what the artifacts say",
         ["-m", "pytest", "-q", "tests/test_prose_numeric_bindings.py"]),
        ("the flight trajectory is byte-identical across seeds, as claimed",
         ["-m", "pytest", "-q", "tests/test_flight_truth_determinism.py"]),
        ("terminology: the produced quantity is not called a posterior",
         ["-m", "pytest", "-q", "tests/test_manuscript_terminology_lint.py"]),
    ],
    "math": [
        ("every proposition, re-verified symbolically and numerically",
         ["-m", "pytest", "-q", "tests/test_math_paper_proofs.py"]),
        ("the committed proof audit was produced by the committed script",
         ["tools/publication/proof_audit_check.py"]),
        ("prose numbers still equal what the artifacts say",
         ["-m", "pytest", "-q", "tests/test_prose_numeric_bindings.py"]),
        ("terminology: q and p are posteriors; the deployed output is not",
         ["-m", "pytest", "-q", "tests/test_manuscript_terminology_lint.py"]),
    ],
}

NOT_VERIFIABLE = {
    "systems": [
        ("no bibliography entry is verified",
         "every publisher host is blocked from the authoring environment. "
         "Corroborating DOIs by search also found three entries carrying "
         "WRONG metadata and one probable duplicate; all four are disclosed "
         "in papers/BIB_EXTERNAL_VERIFICATION_PACKET.md. Counts are in "
         "papers/BIB_VERIFICATION_LEDGER.yaml and are checked against it by "
         "tests/test_evidence_capsule_counts.py"),
        ("the public-log exposure study was NOT RUN",
         "SC-22's artifact field is literally 'NONE - NOT RUN'. "
         "research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json "
         "records every route attempted and blocked"),
        ("the current-stack self-occlusion trials are n=1 per platform",
         "one fault trial and one matched fix-preserving control on each of "
         "ArduPilot 4.8 and PX4 SIH. A demonstration, not a replication base. "
         "research/systems-paper/CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md"),
        ("the SITL campaigns cannot be re-run here",
         "no ArduPilot binary is vendored. The campaigns' RESULTS are "
         "committed and are what the checks above re-derive from"),
        ("no operational harm is demonstrated",
         "and none is claimed. papers/csia_systems/main.tex, Limitations"),
    ],
    "math": [
        ("no bibliography entry is verified",
         "same blockage. Heitjan & Rubin 1991 underwrites C2's KNOWN label "
         "and is corroborated, not read"),
        ("20 of 21 prior-art rows are unread or unverified",
         "research/math-paper/PRIOR_ART_MATRIX.csv. The concessions are as "
         "unverified as anything else, which is the honest state"),
        ("the baseline q is a counterfactual",
         "and in the measured case it is not evaluable at all: the gate "
         "closes because the receiver stopped reporting, so the withheld "
         "term has no observed value. FORMAL_CORE.md section 1.1"),
        ("every proposition is labelled KNOWN",
         "research/math-paper/NOVELTY_AUDIT.md. The paper claims a "
         "formulation, a diagnosis and a measured instance -- no theorem"),
    ],
}


def run(cmd):
    """Run one check from the repository root. Returns (ok, tail_of_output)."""
    argv = [sys.executable] + cmd if cmd[0].startswith("-") or \
        cmd[0].endswith(".py") else cmd
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip().split("\n")
    return proc.returncode == 0, out[-1] if out else ""


def verify(paper):
    print(f"\n{'=' * 70}\nEVIDENCE CAPSULE -- {paper.upper()} PAPER\n{'=' * 70}")
    print("\nVERIFIABLE FROM COMMITTED ARTIFACTS, HERE, WITH NO NETWORK:\n")
    failed = []
    for label, cmd in CHECKS[paper]:
        ok, tail = run(cmd)
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
        if not ok:
            print(f"          {tail}")
            failed.append(label)

    print("\nNOT VERIFIABLE, AND WHY -- these do not affect the exit code:\n")
    for label, why in NOT_VERIFIABLE[paper]:
        print(f"  [    ]  {label}")
        for line in _wrap(why, 62):
            print(f"          {line}")
    return failed


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paper", choices=("systems", "math", "both"),
                    default="both")
    args = ap.parse_args()

    papers = ("systems", "math") if args.paper == "both" else (args.paper,)
    failed = []
    for p in papers:
        failed += verify(p)

    print(f"\n{'=' * 70}")
    if failed:
        print(f"VERIFICATION: FAIL -- {len(failed)} check(s) did not pass")
        for f in failed:
            print(f"  {f}")
        return 1
    print("VERIFICATION: PASS -- every verifiable claim re-derives from a "
          "committed artifact")
    print("The NOT VERIFIABLE list above is part of the result, not a caveat "
          "on it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
