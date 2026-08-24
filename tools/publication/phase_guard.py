"""Publication guard: Phase-II results may not reach a Phase-I manuscript.

CSIA Systems Paper I reports measurements taken on ArduCopter 3.3 with the
frozen v1 layer. Phase II runs on ArduCopter 4.8, where two graph nodes are
live that were dead on 3.3 and where the ESC telemetry channel is a
placeholder. A Phase-II number landing in a Phase-I table would be a
different vehicle, a different information architecture and a different
software state, presented as the same measurement.

Nothing enforces that by convention alone, so it is enforced here.

CHECKS
  1. no Phase-I manuscript source references a research/phase2/ path
  2. no Phase-I artifact map references a research/phase2/ path
     (also checked structurally by artifact_map_check.py)
  3. Phase-I result directories referenced by a Phase-I map are unmodified
     relative to the frozen baseline commit, or the drift is reported
  4. the frozen benchmark campaigns/bench.json is unmodified relative to the
     frozen baseline commit

Check 3 and 4 are the ones that catch the dangerous case: a Phase-II
experiment quietly rewriting a Phase-I result file in place.

Run:  python tools/publication/phase_guard.py
"""

import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPERS = os.path.join(ROOT, "papers")
PHASE2 = "research/phase2/"


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args],
                          capture_output=True, text=True)


def main() -> int:
    import yaml
    fails, notes = [], []

    maps = []
    for d in sorted(os.listdir(PAPERS)):
        pdir = os.path.join(PAPERS, d)
        if not os.path.isdir(pdir):
            continue
        for f in sorted(os.listdir(pdir)):
            if f.endswith("ARTIFACT_MAP.yaml"):
                maps.append((d, pdir, yaml.safe_load(
                    open(os.path.join(pdir, f)))))

    # ---- 1: manuscript sources ----
    print("=== manuscript sources")
    for d, pdir, doc in maps:
        if doc.get("phase") != 1:
            continue
        main_tex = os.path.join(pdir, doc.get("manuscript", "main.tex"))
        if not os.path.isfile(main_tex):
            continue
        text = open(main_tex, encoding="utf-8").read()
        hits = sorted(set(re.findall(
            r"research/phase2/[A-Za-z0-9_./-]*", text)))
        print(f"  {'PASS' if not hits else 'FAIL'}  papers/{d}/"
              f"{doc.get('manuscript')}  {len(hits)} Phase-II references")
        for h in hits:
            print(f"        {h}")
        if hits:
            fails.append(f"papers/{d}: manuscript references Phase-II: {hits}")

    # ---- 2: artifact maps ----
    #
    # Only PATH-BEARING values are inspected, not the raw file text. A first
    # version grepped the raw YAML and flagged the map's own comment
    # explaining that references to the Phase-II tree are forbidden -- the
    # guard failing on its own documentation. Parsing the fields is both
    # correct and narrower.
    print("=== artifact maps")
    PATH_KEYS = ("artifact", "script", "inputs", "file", "path")
    for d, pdir, doc in maps:
        if doc.get("phase") != 1:
            continue
        hits = []

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in PATH_KEYS:
                        for p in (v if isinstance(v, list) else [v]):
                            if isinstance(p, str) and p.startswith(PHASE2):
                                hits.append(p)
                    else:
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(doc)
        hits = sorted(set(hits))
        print(f"  {'PASS' if not hits else 'FAIL'}  papers/{d} map  "
              f"{len(hits)} Phase-II path references")
        for h in hits:
            print(f"        {h}")
        if hits:
            fails.append(f"papers/{d}: artifact map references Phase-II: "
                         f"{hits}")

    # ---- 3 & 4: frozen-baseline drift ----
    print("=== frozen-baseline integrity")
    baseline = None
    for _d, _p, doc in maps:
        if doc.get("phase") == 1 and doc.get("frozen_baseline"):
            baseline = doc["frozen_baseline"].get("commit")
            break
    if not baseline:
        print("  ----  no frozen_baseline commit declared; skipping")
        notes.append("no Phase-I map declares frozen_baseline.commit")
    else:
        rev = git("rev-parse", "--verify", f"{baseline}^{{commit}}")
        if rev.returncode != 0:
            print(f"  ----  baseline commit {baseline} not present in this "
                  f"clone (shallow?); skipping drift check")
            notes.append(f"baseline commit {baseline} unreachable")
        else:
            watch = ["campaigns/bench.json"]
            for _d, _p, doc in maps:
                if doc.get("phase") != 1:
                    continue
                for key in ("figures", "tables", "scalars"):
                    for e in (doc.get(key) or []):
                        a = e.get("artifact")
                        if a and a.startswith("research/wp_"):
                            watch.append(a)
            watch = sorted(set(watch))
            diff = git("diff", "--name-only", baseline, "--", *watch)
            changed = [x for x in diff.stdout.split() if x]
            print(f"  {'PASS' if not changed else 'FAIL'}  "
                  f"{len(watch)} Phase-I artifacts vs {baseline}  "
                  f"{len(changed)} changed")
            for c in changed:
                print(f"        CHANGED  {c}")
            if changed:
                fails.append(
                    f"Phase-I artifacts changed since the frozen baseline "
                    f"{baseline}: {changed}. A Phase-I paper's numbers must "
                    f"not move. If a change is intended, re-freeze the "
                    f"baseline explicitly and say so in RESEARCH_STATE.md.")

    print()
    for n in notes:
        print(f"NOTE: {n}")
    if fails:
        print(f"\nPHASE GUARD: FAIL -- {len(fails)} problems")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nPHASE GUARD: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
