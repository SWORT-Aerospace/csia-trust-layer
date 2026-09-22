"""Verify the claim-artifact register. READ-ONLY, by construction.

WHAT IT DOES
------------
Loads research/assurance/CLAIM_ARTIFACT_REGISTER.yaml and, for every entry,
checks what can be checked without running anything:

    the artifact exists
    its SHA-256 still matches what the register recorded
    the generator named for it exists
    every input artifact named for it exists
    the entry itself is well formed

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never regenerates an artifact, never refreshes one, and never opens a file
for writing except its own JSON report. There is no --fix, no --regenerate
and no --update-hashes: a verifier that can rewrite what it verifies is a
verifier whose green result means nothing. If a hash has drifted, the answer
is to find out why, not to restamp the register.

LOCKED RESULTS ARE NEVER REGENERATED, AND NOT ONLY BECAUSE NOTHING HERE
REGENERATES. Entries whose regeneration_status is VERIFIABLE_ONLY or
NOT_REGENERABLE are reported UNREGENERABLE, and that is a terminal state
rather than an outstanding task: they derive from SITL campaigns behind a
preregistration, needing an autopilot this repository does not vendor.
"Regenerate it" is the wrong instruction for them.

UNKNOWN OUTRANKS UNREGENERABLE. An entry that is both unregenerable AND
missing its provenance is reported UNKNOWN, because burying a provenance gap
behind the milder fact is how a gap stops being looked at.

HASH PINNING IS NOT EVIDENCE GATING
-----------------------------------
A matching hash here says the file has not changed since the register
recorded it. It says nothing about whether the result may be generated or
refreshed, or about what state the tree was in when it was produced. This
tool reports VALID for an artifact that is ungated, because VALID is a
statement about integrity and not about governance, and the report says so in
its own output so the two cannot be read as one.

PER-ARTIFACT VERDICTS

    VALID           exists, hash matches, declared provenance resolves
    DRIFT           exists but the hash differs from the register
    MISSING         the artifact, its generator or a declared input is absent
    UNKNOWN         provenance the register could not establish
    UNREGENERABLE   verifiable, but cannot be regenerated here

EXIT CODE
    0  every entry VALID or UNREGENERABLE
    1  any DRIFT, or any MISSING required provenance
    2  the register itself is unreadable or malformed

    python tools/assurance/claim_artifact_verify.py
    python tools/assurance/claim_artifact_verify.py --out report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REGISTER = os.path.join(ROOT, "research", "assurance",
                        "CLAIM_ARTIFACT_REGISTER.yaml")

VALID = "VALID"
DRIFT = "DRIFT"
MISSING = "MISSING"
UNKNOWN = "UNKNOWN"
UNREGENERABLE = "UNREGENERABLE"

#: Every field an entry must carry. A register entry missing one of these is
#: malformed: the point of the register is that the gaps are NAMED, and an
#: absent field is not a named gap, it is an unasked question.
REQUIRED_FIELDS = (
    "artifact_path", "paper", "claim_id", "claim_description",
    "artifact_kind", "source_commit", "sha256", "generator_path",
    "generator_commit", "input_artifacts", "environment_requirements",
    "regeneration_status", "freeze_status", "limitations",
    "current_verdict",
)

VALID_KINDS = ("RAW_CAPTURE", "DERIVED_RESULT", "REPRODUCIBLE_GENERATION",
               "MANIFEST", "PROVENANCE", "OTHER")
VALID_REGEN = ("REGENERABLE", "VERIFIABLE_ONLY", "NOT_REGENERABLE", "UNKNOWN")

#: Sentinels the register uses where a fact could not be established. They are
#: values, not absences, and the distinction matters: MISSING means somebody
#: looked and found nothing.
SENTINELS = ("MISSING", "UNKNOWN")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_register(path=REGISTER):
    """Read the register. Never writes, never repairs."""
    import yaml
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError("register is not a mapping")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("register has no entries")
    return doc


def check_entry_shape(entry):
    """Problems with the ENTRY, before anything about the artifact."""
    problems = []
    if not isinstance(entry, dict):
        return ["entry is not a mapping"]
    for field in REQUIRED_FIELDS:
        if field not in entry:
            problems.append(f"missing required field {field!r}")
    kind = entry.get("artifact_kind")
    if kind is not None and kind not in VALID_KINDS:
        problems.append(f"artifact_kind {kind!r} is not one of {VALID_KINDS}")
    regen = entry.get("regeneration_status")
    if regen is not None and regen not in VALID_REGEN:
        problems.append(
            f"regeneration_status {regen!r} is not one of {VALID_REGEN}")
    digest = entry.get("sha256")
    if isinstance(digest, str) and digest not in SENTINELS:
        if len(digest) != 64 or any(c not in "0123456789abcdef"
                                    for c in digest):
            problems.append("sha256 is neither a 64-hex digest nor a sentinel")
    return problems


def verify_entry(entry, root=ROOT):
    """One entry. Returns (verdict, detail). Opens nothing for writing."""
    shape = check_entry_shape(entry)
    if shape:
        return UNKNOWN, {"malformed": True, "problems": shape,
                         "artifact_path": (entry.get("artifact_path")
                                           if isinstance(entry, dict)
                                           else None)}

    art = entry["artifact_path"]
    full = os.path.join(root, art)
    detail = {"artifact_path": art,
              "regeneration_status": entry["regeneration_status"],
              "problems": [], "notes": []}

    if not os.path.exists(full):
        detail["problems"].append(f"artifact absent: {art}")
        return MISSING, detail

    recorded = entry["sha256"]
    if recorded in SENTINELS:
        detail["notes"].append(
            "the register records no digest for this artifact, so its "
            "integrity is UNKNOWN rather than verified")
        verdict_hash = UNKNOWN
    else:
        actual = sha256(full)
        detail["recorded_sha256"] = recorded
        detail["actual_sha256"] = actual
        if actual != recorded:
            detail["problems"].append(
                f"hash drift: register records {recorded[:16]}..., "
                f"file is {actual[:16]}...")
            return DRIFT, detail
        verdict_hash = VALID

    gen = entry["generator_path"]
    if gen in SENTINELS:
        detail["notes"].append(
            f"generator is {gen}: the register could not establish one, and "
            f"none was guessed")
    elif not os.path.exists(os.path.join(root, gen)):
        detail["problems"].append(f"generator named but absent: {gen}")
        return MISSING, detail

    inputs = entry["input_artifacts"]
    if isinstance(inputs, str):
        inputs = [inputs]
    for item in (inputs or []):
        if item in SENTINELS:
            detail["notes"].append(
                "input artifacts are not declared by the map or the script")
            continue
        if not os.path.exists(os.path.join(root, item)):
            detail["problems"].append(f"declared input absent: {item}")
            return MISSING, detail

    unregenerable = entry["regeneration_status"] in ("VERIFIABLE_ONLY",
                                                     "NOT_REGENERABLE")
    if unregenerable:
        detail["notes"].append(
            "verified but NOT regenerated, and not regenerable here; this is "
            "a terminal state, not an outstanding task")

    # UNKNOWN OUTRANKS UNREGENERABLE. An artifact that cannot be regenerated
    # AND whose provenance could not be established is in the weaker of the
    # two states, and reporting it as merely unregenerable would bury the
    # gap behind the milder fact. The unregenerable note is still attached,
    # so nothing is lost by ordering it this way.
    if verdict_hash == UNKNOWN or gen in SENTINELS:
        detail["notes"].append(
            "reported UNKNOWN rather than UNREGENERABLE because the "
            "provenance gap is the more serious of the two"
            if unregenerable else
            "provenance could not be established from the register")
        return UNKNOWN, detail

    if unregenerable:
        return UNREGENERABLE, detail
    return VALID, detail


def verify(register_path=REGISTER, root=ROOT):
    doc = load_register(register_path)
    results, counts = [], {}
    for entry in doc["entries"]:
        verdict, detail = verify_entry(entry, root)
        detail["verdict"] = verdict
        results.append(detail)
        counts[verdict] = counts.get(verdict, 0) + 1

    drifted = [r for r in results if r["verdict"] == DRIFT]
    missing = [r for r in results if r["verdict"] == MISSING]
    unknown = [r for r in results if r["verdict"] == UNKNOWN]

    return {
        "artifact": "CLAIM_ARTIFACT_VERIFICATION",
        "register": os.path.relpath(register_path, root),
        "entries_checked": len(results),
        "by_verdict": counts,
        "drift": [r["artifact_path"] for r in drifted],
        "missing": [r["artifact_path"] for r in missing],
        "unknown": [r["artifact_path"] for r in unknown],
        "read_only": ("this tool regenerated nothing, refreshed nothing and "
                      "modified no artifact. It has no flag that would let "
                      "it."),
        "a_valid_hash_is_not_a_gate": (
            "VALID means the file is unchanged since the register recorded "
            "it. It does not mean the artifact is evidence-gated. Hash "
            "pinning DETECTS later modification; evidence gating controls "
            "whether a result may be generated or refreshed at all, and "
            "these artifacts remain ungated."),
        "results": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--register", default=REGISTER)
    ap.add_argument("--out", default=None,
                    help="write the JSON report here (the only file written)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        report = verify(args.register)
    except (OSError, ValueError) as exc:
        print(f"REGISTER UNREADABLE: {exc}", file=sys.stderr)
        return 2

    print("CLAIM-ARTIFACT VERIFICATION  (read-only)")
    print("=" * 72)
    for r in report["results"]:
        if args.quiet and r["verdict"] in (VALID, UNREGENERABLE):
            continue
        print(f"  [{r['verdict']:14s}] {r['artifact_path']}")
        for p in r.get("problems", []):
            print(f"       problem: {p}")
        if not args.quiet:
            for n in r.get("notes", []):
                print(f"       note:    {n}")
    print("=" * 72)
    for verdict in (VALID, UNREGENERABLE, UNKNOWN, DRIFT, MISSING):
        n = report["by_verdict"].get(verdict, 0)
        if n:
            print(f"  {verdict:14s} {n:4d}")
    print()
    print(f"  {report['a_valid_hash_is_not_a_gate']}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.out}")

    if report["drift"]:
        print(f"\nFAIL: {len(report['drift'])} artifact(s) drifted from the "
              f"register", file=sys.stderr)
        return 1
    if report["missing"]:
        print(f"\nFAIL: {len(report['missing'])} entry(ies) name provenance "
              f"that is absent", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
