"""Concatenate the evidence export into plain-text transfer bundles.

Why this exists: the `.tar.gz` handoff failed twice. A tarball is one opaque
blob that either arrives or does not. A `.txt` bundle degrades gracefully --
it can be attached, pasted, split, or read straight from the GitHub blob view,
and a partial transfer is visibly partial rather than silently corrupt.

Nothing here summarizes, truncates or reflows. Each file is copied byte for
byte between delimiters. The only bytes this tool adds are the delimiters.

Outputs:
  PAPER1_EVIDENCE_BUNDLE.txt    all 16 files, in canonical order
  PAPER1_CRITICAL_STARTER.txt   the 8 a writer cannot start without, for the
                                case where the full bundle exceeds an
                                attachment limit

Both are scanned with the SAME rules as the archives -- the patterns come from
PUBLIC_RELEASE_MANIFEST.yaml, not from a second copy that could drift. A hit
deletes the bundle.

Run:  python publication/system_paper_i/build_text_bundles.py
"""

import hashlib
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "evidence_export")
MANIFEST = os.path.join(HERE, "PUBLIC_RELEASE_MANIFEST.yaml")

RULE = "=" * 60

ALL_FILES = [
    "00_README.md",
    "01_PHASE1_SCOPE.md",
    "02_FROZEN_DEFINITIONS.md",
    "03_SELF_OCCLUSION_RESULT.md",
    "04_REPAIR_EXPERIMENT.md",
    "05_ESCALATION_RESULT.md",
    "06_EXPOSURE_RESULTS.md",
    "07_HARNESS_CONTRACT.md",
    "08_REAL_LOG_RESULTS.md",
    "09_STRUCTURAL_RESULTS.md",
    "10_CORRECTIONS_LEDGER.md",
    "11_CLAIM_LEDGER.yaml",
    "12_ARTIFACT_MAP.yaml",
    "13_REFERENCE_AUDIT.md",
    "14_REPRODUCTION_COMMANDS.md",
    "15_REPOSITORY_STATE.json",
]

# The eight a writer cannot begin without: the scope that bounds every
# sentence, the definitions without which no exposure number means anything,
# the primary run, the escalation and exposure results, the claim ledger, the
# artifact map that binds each number to a hash, and the commit provenance.
STARTER_FILES = [
    "01_PHASE1_SCOPE.md",
    "02_FROZEN_DEFINITIONS.md",
    "03_SELF_OCCLUSION_RESULT.md",
    "05_ESCALATION_RESULT.md",
    "06_EXPOSURE_RESULTS.md",
    "11_CLAIM_LEDGER.yaml",
    "12_ARTIFACT_MAP.yaml",
    "15_REPOSITORY_STATE.json",
]


def block(name, body):
    """One file, verbatim, between delimiters."""
    if not body.endswith("\n"):
        body += "\n"
    return (f"{RULE}\nBEGIN FILE: {name}\n{RULE}\n"
            f"{body}"
            f"{RULE}\nEND FILE: {name}\n{RULE}\n\n")


def build(names):
    out = []
    for name in names:
        path = os.path.join(SRC, name)
        with open(path, encoding="utf-8") as fh:
            out.append(block(name, fh.read()))
    return "".join(out)


def sanitize(names, san):
    """Scan the SOURCE files, each under its own name.

    Scanning the concatenated bundle would break the Phase-II context rule:
    once the files are joined, a token legitimately carried by
    01_PHASE1_SCOPE.md (which states what the paper excludes) would look like
    a token in every other file. So the check runs per source file, exactly as
    it does per archive member.
    """
    pats = {k: re.compile(v) for k, v in san["forbidden_patterns"].items()}
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    email_ok = tuple(san.get("email_allowed_in", []))
    ph_tokens = san.get("phase_ii_context_tokens", [])
    ph_ok = tuple(san.get("phase_ii_context_allowed_in", []))

    failures = []
    for name in names:
        arc = f"evidence_export/{name}"
        with open(os.path.join(SRC, name), encoding="utf-8") as fh:
            text = fh.read()
        for label, pat in pats.items():
            m = pat.search(text)
            if m:
                fp = hashlib.sha256(m.group(0).encode()).hexdigest()[:12]
                failures.append(f"{name}: forbidden [{label}] "
                                f"redacted-sha256:{fp}")
        if not arc.endswith(email_ok):
            m = email.search(text)
            if m:
                fp = hashlib.sha256(m.group(0).encode()).hexdigest()[:12]
                failures.append(f"{name}: email outside LICENSE "
                                f"redacted-sha256:{fp}")
        if not arc.endswith(ph_ok):
            for tok in ph_tokens:
                if tok in text:
                    failures.append(
                        f"{name}: Phase-II token {tok!r} in a file not "
                        f"allowed to carry one")
    return failures


def verify_roundtrip(bundle, names):
    """Every source file must be recoverable from the bundle byte for byte.

    This is the property the whole transfer rests on: if a writer can only
    reach the bundle, splitting it back into files must give exactly what the
    export directory holds. Checked here rather than assumed.
    """
    problems = []
    for name in names:
        with open(os.path.join(SRC, name), encoding="utf-8") as fh:
            original = fh.read()
        start = f"{RULE}\nBEGIN FILE: {name}\n{RULE}\n"
        end = f"{RULE}\nEND FILE: {name}\n{RULE}\n"
        i = bundle.find(start)
        if i < 0:
            problems.append(f"{name}: BEGIN delimiter missing")
            continue
        j = bundle.find(end, i)
        if j < 0:
            problems.append(f"{name}: END delimiter missing")
            continue
        extracted = bundle[i + len(start):j]
        expected = original if original.endswith("\n") else original + "\n"
        if extracted != expected:
            problems.append(f"{name}: extracted content differs from source "
                            f"({len(extracted)} vs {len(expected)} chars)")
        # A delimiter line occurring inside a file's own body would let a
        # splitter cut in the wrong place.
        if f"\n{RULE}\nBEGIN FILE:" in extracted:
            problems.append(f"{name}: body contains a BEGIN delimiter")
    return problems


def emit(path, names, san, label):
    body = build(names)

    failures = sanitize(names, san)
    problems = verify_roundtrip(body, names)

    print(f"=== {label}")
    print(f"    files:        {len(names)}")

    if failures or problems:
        for f in failures:
            print(f"    SANITIZATION FAIL  {f}")
        for p in problems:
            print(f"    ROUNDTRIP FAIL     {p}")
        if os.path.exists(path):
            os.remove(path)
        print("    bundle not written; a failed bundle does not ship")
        return 1

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)

    data = open(path, "rb").read()
    print(f"    path:         {os.path.relpath(path, ROOT)}")
    print(f"    bytes:        {len(data):,}")
    print(f"    lines:        {body.count(chr(10)):,}")
    print(f"    sha256:       {hashlib.sha256(data).hexdigest()}")
    print("    ROUNDTRIP:    PASS (every file extracts byte-identical)")
    print("    SANITIZATION: PASS (no username, home path, credential, "
          "strategy document, interceptor tooling, or unlabelled Phase-II "
          "token)")
    print()
    return 0


def main() -> int:
    with open(MANIFEST, encoding="utf-8") as fh:
        san = yaml.safe_load(fh)["sanitization"]

    missing = [n for n in ALL_FILES
               if not os.path.isfile(os.path.join(SRC, n))]
    if missing:
        print("FAIL: evidence export incomplete: " + ", ".join(missing))
        return 1

    rc = 0
    rc |= emit(os.path.join(HERE, "PAPER1_EVIDENCE_BUNDLE.txt"),
               ALL_FILES, san, "PAPER1_EVIDENCE_BUNDLE.txt  (complete)")
    rc |= emit(os.path.join(HERE, "PAPER1_CRITICAL_STARTER.txt"),
               STARTER_FILES, san,
               "PAPER1_CRITICAL_STARTER.txt  (fallback subset)")

    print("TEXT BUNDLES: " + ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
