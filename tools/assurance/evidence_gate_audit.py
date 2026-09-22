"""Which committed evidence artifacts can be rewritten without showing a good tree?

WHY THIS EXISTS
---------------
FL-049 found that BUILD_PROVENANCE.json had no evidence gate: `protected_write`
refuses to clobber a committed artifact without `--regenerate`, which guards
against ACCIDENT, but nothing asked whether the tree being described was in a
state worth recording. The record could be rewritten from a red suite, failing
blocking guards or a drifted frozen core and would look exactly as
authoritative as one written from a good tree.

That gap was never specific to the provenance record. This asks the same
question of every committed artifact, mechanically, so the answer is a
measurement rather than a recollection.

WHAT IT CLASSIFIES

For every tracked `.json`/`.csv` evidence artifact, the strongest guard any of
its generators carries:

  EVIDENCE_GATED    the writer requires a green suite, passing blocking
                    guards, an unchanged frozen core and verifying manifests
                    before it writes
  ACCIDENT_GUARDED  the writer uses `protected_write`, so it refuses to
                    overwrite a committed file without `--regenerate`. It
                    does NOT ask whether the tree is good
  UNGUARDED         the writer opens the path and writes
  NO_GENERATOR      no tracked `.py` names this artifact at all

AND THE MITIGATION, WHICH IS REPORTED SEPARATELY

An artifact pinned by a SHA256 manifest carries tamper-evidence independent of
its writer: rewriting it makes a manifest check fail. That does not make the
writer gated -- it means an ungated rewrite is DETECTED rather than PREVENTED.
The two are different properties and collapsing them would overstate how much
is guarded, so they are reported as separate columns.

WHAT THIS IS NOT
----------------
It is not a vulnerability report and it does not claim any artifact is wrong.
Every artifact in this repository was written by its author on purpose. This
measures which ones COULD be rewritten from a tree nobody checked, which is a
statement about process, not about the numbers.

The generator search is by filename, so it is approximate in one direction and
exact in the other: a script that builds a path from pieces will be missed and
its artifact reported NO_GENERATOR, and that is the conservative error --
it over-reports the ungoverned set rather than under-reporting it.

    python tools/assurance/evidence_gate_audit.py
    python tools/assurance/evidence_gate_audit.py --out <json>
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EVIDENCE_GATED = "EVIDENCE_GATED"
ACCIDENT_GUARDED = "ACCIDENT_GUARDED"
UNGUARDED = "UNGUARDED"
NO_GENERATOR = "NO_GENERATOR"

STRENGTH = {NO_GENERATOR: 0, UNGUARDED: 1, ACCIDENT_GUARDED: 2,
            EVIDENCE_GATED: 3}

#: Trees whose files are not evidence about this system's behaviour.
EXCLUDED_PREFIXES = (
    "Gate_Conditioning_v2_2_REPRO_PACKAGE/",   # a separate deliverable with
                                               # its own verifier
    "docs/", "papers/", ".github/", "tests/",
)

#: Markers that a writer demands the tree be shown good, not merely that it
#: refuses to clobber by accident.
EVIDENCE_MARKERS = ("gather_evidence", "provenance_workflow",
                    "frozen_core_evidence", "guards_evidence")


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True).stdout.split()


def tracked_artifacts():
    return sorted(p for p in _git("ls-files")
                  if p.endswith((".json", ".csv"))
                  and not p.startswith(EXCLUDED_PREFIXES))


def tracked_python():
    return sorted(p for p in _git("ls-files", "*.py")
                  if not p.startswith(("tests/",)))


HEX64 = __import__("re").compile(r"^[0-9a-f]{64}$")


def _pin_targets(obj, out):
    """Every {path-ish key: 64-hex} pair anywhere in a parsed document.

    Manifests in this repository take several shapes -- {path: digest},
    {path: {"sha256": digest}}, and lists of {"path":..., "sha256":...} --
    so the structure is walked rather than assumed. Looking only at
    SHA256_MANIFEST* files (the first version of this) found 28 pinned
    artifacts and missed FREEZE.json, FROZEN_BASELINE.json,
    E1_FREEZE_MANIFEST.yaml, the golden corpus and the RAW_CHECKSUMS files,
    which would have overstated how much of the tree is undetectable.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and HEX64.match(v) and isinstance(k, str):
                out.add(k)
            elif isinstance(v, dict) and isinstance(v.get("sha256"), str) \
                    and HEX64.match(v["sha256"]) and isinstance(k, str):
                out.add(k)
            else:
                _pin_targets(v, out)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and isinstance(item.get("path"), str) \
                    and isinstance(item.get("sha256"), str):
                out.add(item["path"])
            else:
                _pin_targets(item, out)


def manifest_pinned_paths():
    """Every artifact path pinned by ANY integrity file, with its pinner.

    A key may be repo-relative or relative to the pinning file's own
    directory; both are recorded, and the caller matches on either.
    """
    pinned = collections.defaultdict(list)
    for rel in _git("ls-files"):
        base = os.path.basename(rel)
        full = os.path.join(ROOT, rel)
        keys = set()
        if rel.endswith((".json", ".yaml", ".yml")):
            try:
                if rel.endswith(".json"):
                    doc = json.load(open(full, encoding="utf-8"))
                else:
                    import yaml
                    doc = yaml.safe_load(open(full, encoding="utf-8"))
            except Exception:
                continue
            _pin_targets(doc, keys)
        elif base.endswith(".sha256") or base == "CORPUS_SHA256":
            try:
                for line in open(full, encoding="utf-8", errors="ignore"):
                    parts = line.split()
                    if len(parts) == 2 and HEX64.match(parts[0]):
                        keys.add(parts[1].lstrip("*"))
            except OSError:
                continue
        else:
            continue
        here = os.path.dirname(rel)
        for key in keys:
            pinned[key].append(rel)
            joined = os.path.normpath(os.path.join(here, key))
            if joined != key:
                pinned[joined].append(rel)
    return pinned


WRITE_MARKERS = ("json.dump", "protected_write", "DictWriter",
                 "csv.writer", "write_text", '"w"', "'w'", ".write(")

_ASSIGN = __import__("re").compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def mentions_as_writer(source: str, names) -> bool:
    """Does this script write the artifact, as opposed to merely naming it?

    Two passes, because each alone gets it wrong in a different direction.

    PROXIMITY. A write marker within a few lines of the mention. Alone this
    MISSES the normal good pattern, where the path is a module constant far
    from the write: provenance_workflow.py writes its record through
    `RECORD = os.path.join(..., "BUILD_PROVENANCE.json")`, and by proximity
    alone it stopped counting as that record's writer at all.

    ASSIGNMENT CHASE. If the mention is an assignment, take the name bound
    and look for it near a write marker anywhere in the file. That recovers
    the constant-path pattern.

    Mention without either is a READ. Counting reads as writes is what made
    three SHA256 manifests look EVIDENCE_GATED when provenance_workflow.py
    only reads them as a precondition -- an error that inflates the gated
    count, which is the one direction an audit of missing gates must not err
    in quietly.
    """
    lines = source.splitlines()
    bound = set()
    for i, line in enumerate(lines):
        if not any(n in line for n in names):
            continue
        window = "\n".join(lines[max(0, i - 4):i + 5])
        if any(m in window for m in WRITE_MARKERS):
            return True
        # The mention may sit on a CONTINUATION line of a multi-line
        # assignment -- `RECORD = os.path.join(ROOT, ...,` on one line and
        # `"BUILD_PROVENANCE.json")` on the next -- so the assignment head
        # is looked for backwards as well as on the line itself.
        for back in range(0, 4):
            j = i - back
            if j < 0:
                break
            m = _ASSIGN.match(lines[j])
            if m:
                bound.add(m.group(1))
                break
    if not bound:
        return False
    for i, line in enumerate(lines):
        if not any(m in line for m in WRITE_MARKERS):
            continue
        window = "\n".join(lines[max(0, i - 3):i + 4])
        if any(b in window for b in bound):
            return True
    return False


#: The artifact maps: what each paper says backs which claim. An artifact
#: cited here is load-bearing for a published number, so its gate status is
#: the part of this audit that matters most.
ARTIFACT_MAPS = (
    "papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml",
    "papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml",
)


def paper_cited_paths():
    """Every .json/.csv path named in a paper's artifact map."""
    import re as _re
    cited = set()
    for rel in ARTIFACT_MAPS:
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            continue
        text = open(full, encoding="utf-8", errors="ignore").read()
        cited.update(_re.findall(r"[\w/\.\-]+\.(?:json|csv)", text))
    return cited


def classify_writer(source: str) -> str:
    """The strongest guard this source carries."""
    if any(m in source for m in EVIDENCE_MARKERS):
        return EVIDENCE_GATED
    if "protected_write" in source:
        return ACCIDENT_GUARDED
    return UNGUARDED


def audit():
    artifacts = tracked_artifacts()
    pythons = tracked_python()
    pinned = manifest_pinned_paths()
    cited = paper_cited_paths()

    sources = {}
    for rel in pythons:
        try:
            sources[rel] = open(os.path.join(ROOT, rel), encoding="utf-8",
                                errors="ignore").read()
        except OSError:
            continue

    # Only files that actually emit structured data can be generators.
    writers = {rel: src for rel, src in sources.items()
               if ("json.dump" in src or "csv.writer" in src
                   or "DictWriter" in src or "write_text" in src)}

    rows = []
    for art in artifacts:
        base = os.path.basename(art)
        parent = os.path.dirname(art)
        # Two attributions, because they bias in OPPOSITE directions and
        # collapsing them would hide that. Naming the file or the full path
        # is strong evidence that a script writes it. Naming only the
        # containing directory finds the writers of template-named per-run
        # files, but it also credits any script that merely mentions the
        # directory -- which INFLATES the guarded count, the one error an
        # audit must not make quietly. So the headline uses the strict rule
        # and the permissive rule is reported beside it.
        strict = sorted(rel for rel, src in writers.items()
                        if (base in src or art in src)
                        and mentions_as_writer(src, (base, art)))
        loose = sorted(rel for rel, src in writers.items()
                       if rel not in strict and parent and parent in src
                       and mentions_as_writer(src, (parent,)))

        strict_guards = {g: classify_writer(writers[g]) for g in strict}
        loose_guards = {g: classify_writer(writers[g]) for g in loose}

        v_strict = (max(strict_guards.values(), key=lambda v: STRENGTH[v])
                    if strict_guards else NO_GENERATOR)
        combined = {**strict_guards, **loose_guards}
        v_loose = (max(combined.values(), key=lambda v: STRENGTH[v])
                   if combined else NO_GENERATOR)

        rows.append({
            "artifact": art,
            "verdict": v_strict,
            "verdict_if_directory_attribution_accepted": v_loose,
            "generators_by_name_or_path": strict_guards,
            "generators_by_directory_only": loose_guards,
            "manifest_pinned": bool(pinned.get(art)),
            "pinned_by": sorted(set(pinned.get(art, []))),
            "cited_by_a_paper_artifact_map": art in cited,
        })

    by_verdict = collections.Counter(r["verdict"] for r in rows)
    by_verdict_loose = collections.Counter(
        r["verdict_if_directory_attribution_accepted"] for r in rows)
    ungoverned = [r for r in rows
                  if STRENGTH[r["verdict"]] < STRENGTH[EVIDENCE_GATED]]
    undetected = [r for r in ungoverned if not r["manifest_pinned"]]
    claim_backing = [r for r in rows if r["cited_by_a_paper_artifact_map"]]
    claim_ungated = [r for r in claim_backing
                     if STRENGTH[r["verdict"]] < STRENGTH[EVIDENCE_GATED]]
    claim_unpinned = [r for r in claim_ungated if not r["manifest_pinned"]]

    return {
        "artifact": "EVIDENCE_GATE_AUDIT",
        "question": ("which committed evidence artifacts can be rewritten "
                     "without anyone showing the tree was in a good state?"),
        "artifacts_examined": len(rows),
        "python_writers_examined": len(writers),
        "by_verdict": dict(by_verdict),
        "by_verdict_if_directory_attribution_accepted":
            dict(by_verdict_loose),
        "manifest_pinned": sum(1 for r in rows if r["manifest_pinned"]),
        "not_evidence_gated": len(ungoverned),
        "not_gated_and_not_pinned": len(undetected),
        "claim_backing": {
            "artifacts_cited_by_a_paper_artifact_map": len(claim_backing),
            "of_those_not_evidence_gated": len(claim_ungated),
            "of_those_neither_gated_nor_pinned": len(claim_unpinned),
            "why_this_tier_matters": (
                "these are the artifacts a paper cites as backing a stated "
                "number. An ungated rewrite of one of them changes a "
                "published claim's evidence with nothing required to have "
                "been shown about the tree it came from."),
            "artifacts": [r["artifact"] for r in claim_ungated],
        },
        "what_pinning_means": (
            "a manifest makes an ungated rewrite DETECTED, not PREVENTED. "
            "It is a different property from a write gate and is reported "
            "separately so the two are not added together."),
        "what_this_is_not": (
            "not a vulnerability report and not a claim that any artifact is "
            "wrong. It measures which artifacts COULD be rewritten from an "
            "unchecked tree, which is a statement about process."),
        "search_is_by_filename": (
            "a generator that builds its path from pieces is missed, and its "
            "artifact is reported NO_GENERATOR. That error over-reports the "
            "ungoverned set rather than hiding it."),
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--show", type=int, default=12,
                    help="how many ungoverned artifacts to list")
    args = ap.parse_args(argv)

    doc = audit()

    print("EVIDENCE GATE AUDIT")
    print("=" * 72)
    print(f"  {doc['artifacts_examined']} committed artifacts, "
          f"{doc['python_writers_examined']} python writers")
    print()
    print(f"  {'':18s} {'strict':>7s} {'+dir':>7s}")
    for verdict in (EVIDENCE_GATED, ACCIDENT_GUARDED, UNGUARDED,
                    NO_GENERATOR):
        n = doc["by_verdict"].get(verdict, 0)
        m = doc["by_verdict_if_directory_attribution_accepted"].get(
            verdict, 0)
        print(f"  {verdict:18s} {n:7d} {m:7d}")
    print("    strict = a script names the file or its path")
    print("    +dir   = also crediting scripts that name only the directory")
    print()
    print(f"  manifest-pinned (rewrite DETECTED)      "
          f"{doc['manifest_pinned']:5d}")
    print(f"  not evidence-gated                      "
          f"{doc['not_evidence_gated']:5d}")
    print(f"  not gated AND not pinned                "
          f"{doc['not_gated_and_not_pinned']:5d}   <- neither prevented "
          f"nor detected")

    worst = [r for r in doc["rows"]
             if STRENGTH[r["verdict"]] < STRENGTH[EVIDENCE_GATED]
             and not r["manifest_pinned"]]
    worst.sort(key=lambda r: (STRENGTH[r["verdict"]], r["artifact"]))
    if worst:
        print()
        print(f"  neither gated nor pinned, first {min(args.show, len(worst))}:")
        for r in worst[:args.show]:
            print(f"    [{r['verdict']:16s}] {r['artifact']}")

    cb = doc["claim_backing"]
    print()
    print("  CLAIM-BACKING TIER (cited by a paper's artifact map)")
    print(f"    cited artifacts                       "
          f"{cb['artifacts_cited_by_a_paper_artifact_map']:5d}")
    print(f"    not evidence-gated                    "
          f"{cb['of_those_not_evidence_gated']:5d}")
    print(f"    neither gated nor pinned              "
          f"{cb['of_those_neither_gated_nor_pinned']:5d}")

    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out) as fh:
            fh.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
