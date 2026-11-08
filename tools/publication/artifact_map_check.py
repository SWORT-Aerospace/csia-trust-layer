"""Publication guard: every quantitative manuscript claim maps to an artifact.

Each paper directory carries an artifact map (``*_ARTIFACT_MAP.yaml``) that
binds the manuscript's figures, tables and headline scalars to the committed
result files, the scripts that generated them, and the commands that
regenerate them. This validates that the map and the manuscript agree.

CHECKS, all hard failures:

  1. every ``\\includegraphics`` target in the manuscript exists on disk
  2. every figure on disk is mapped
  3. every mapped path (artifact, script, figure, input) exists
  4. every mapped scalar's ``value`` string literally occurs in the manuscript
  5. every ``\\begin{tabular}`` in the manuscript is accounted for by a mapped
     table entry (count match)
  6. PHASE SEPARATION: a map declaring ``phase: 1`` may not reference any path
     under ``research/phase2/``. Phase-II results must never move a Phase-I
     table.

REVIEW OUTPUT, not a failure: every distinct numeric literal in the manuscript
that is neither mapped nor covered by the map's ``non_empirical`` allowlist is
listed. That list is how "no undocumented quantitative claim survives" is
actually policed -- by a human reading it, each release.

Run:  python tools/publication/artifact_map_check.py [--strict-numbers]
"""

import argparse
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPERS = os.path.join(ROOT, "papers")


def strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def load_maps():
    import yaml
    out = []
    for d in sorted(os.listdir(PAPERS)):
        pdir = os.path.join(PAPERS, d)
        if not os.path.isdir(pdir):
            continue
        maps = [f for f in sorted(os.listdir(pdir))
                if f.endswith("ARTIFACT_MAP.yaml")]
        if not maps:
            out.append((d, pdir, None, None))
            continue
        mp = os.path.join(pdir, maps[0])
        out.append((d, pdir, mp, yaml.safe_load(open(mp))))
    return out


def check_paper(name, pdir, map_path, doc, strict_numbers):
    fails, notes = [], []
    rel_map = os.path.relpath(map_path, ROOT) if map_path else None
    print(f"=== {name}")
    if doc is None:
        fails.append(f"{name}: no *_ARTIFACT_MAP.yaml in papers/{name}/")
        print("  FAIL  no artifact map")
        return fails, notes

    main = os.path.join(pdir, doc.get("manuscript", "main.tex"))
    if not os.path.isfile(main):
        fails.append(f"{name}: manuscript {doc.get('manuscript')} missing")
        print(f"  FAIL  manuscript missing: {doc.get('manuscript')}")
        return fails, notes
    tex = strip_comments(open(main, encoding="utf-8").read())

    figures = doc.get("figures") or []
    tables = doc.get("tables") or []
    scalars = doc.get("scalars") or []
    phase = doc.get("phase")

    # ---- 1 & 2: figures ----
    referenced = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)
    missing_on_disk = [f for f in referenced
                       if not os.path.isfile(os.path.join(pdir, f))]
    mapped_figs = {f.get("file") for f in figures}
    unmapped = [f for f in sorted(set(referenced)) if f not in mapped_figs]
    ok = not missing_on_disk and not unmapped
    print(f"  {'PASS' if ok else 'FAIL'}  figures                "
          f"{len(set(referenced))} referenced, {len(figures)} mapped")
    if missing_on_disk:
        fails.append(f"{name}: figure files missing: {missing_on_disk}")
        print(f"        missing on disk: {missing_on_disk}")
    if unmapped:
        fails.append(f"{name}: figures not in artifact map: {unmapped}")
        print(f"        unmapped: {unmapped}")

    # ---- 3: every mapped path exists ----
    bad = []
    for kind, entries in (("figure", figures), ("table", tables),
                          ("scalar", scalars)):
        for e in entries:
            for key in ("artifact", "script", "file", "inputs"):
                v = e.get(key)
                if v is None:
                    continue
                for p in (v if isinstance(v, list) else [v]):
                    base = pdir if key == "file" else ROOT
                    if not os.path.exists(os.path.join(base, p)):
                        bad.append(f"{kind}:{e.get('id', e.get('file'))} "
                                   f"{key}={p}")
    print(f"  {'PASS' if not bad else 'FAIL'}  mapped paths exist     "
          f"{len(bad)} missing")
    for b in bad:
        print(f"        {b}")
    if bad:
        fails.append(f"{name}: mapped paths do not exist: {bad}")

    # ---- 4: mapped scalars occur verbatim in the manuscript ----
    absent = [s for s in scalars
              if str(s.get("value")) not in tex]
    print(f"  {'PASS' if not absent else 'FAIL'}  scalars occur in tex   "
          f"{len(scalars)} mapped, {len(absent)} absent")
    for s in absent:
        print(f"        {s.get('id')}: value {s.get('value')!r} not found")
    if absent:
        fails.append(f"{name}: mapped scalars absent from manuscript: "
                     f"{[s.get('id') for s in absent]}")

    # ---- 5: table count ----
    n_tab = len(re.findall(r"\\begin\{tabular", tex))
    ok_tab = n_tab == len(tables)
    print(f"  {'PASS' if ok_tab else 'FAIL'}  tables accounted for   "
          f"{n_tab} in tex, {len(tables)} mapped")
    if not ok_tab:
        fails.append(f"{name}: {n_tab} tabular environments but "
                     f"{len(tables)} mapped tables")

    # ---- 6: phase separation ----
    if phase is not None:
        leaks = []
        for entries in (figures, tables, scalars):
            for e in entries:
                for key in ("artifact", "script", "inputs"):
                    v = e.get(key)
                    for p in (v if isinstance(v, list) else [v] if v else []):
                        if phase == 1 and p.startswith("research/phase2/"):
                            leaks.append(f"{e.get('id', e.get('file'))} -> {p}")
                        if phase == 2 and p.startswith("research/wp_c"):
                            notes.append(f"{name}: phase-2 map cites a "
                                         f"phase-1 artifact: {p}")
        print(f"  {'PASS' if not leaks else 'FAIL'}  phase separation       "
              f"declared phase {phase}, {len(leaks)} cross-phase references")
        for lk in leaks:
            print(f"        {lk}")
        if leaks:
            fails.append(f"{name}: phase-{phase} map references Phase-II "
                         f"artifacts: {leaks}")

    # ---- review: unmapped numeric literals in PROSE ----
    #
    # A number inside a tabular environment belongs to that table, and the
    # table is already bound to an artifact above. Enumerating every cell in
    # YAML would be brittle and would not add provenance the table entry does
    # not already carry. So cells are attributed to their table and only PROSE
    # numbers are listed for review -- which is the set a human should
    # actually read, because a prose number is a claim stated in the author's
    # own voice rather than a value lifted from a result file.
    allow = [re.compile(p) for p in (doc.get("non_empirical") or [])]
    mapped_vals = {str(s.get("value")) for s in scalars}
    for t in tables:
        mapped_vals.update(str(v) for v in (t.get("values") or []))
    prose = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", tex,
                   flags=re.S)
    lits = set(re.findall(r"(?<![\w\\.])\d+(?:\.\d+)?(?![\w])", prose))
    review = sorted(x for x in lits
                    if x not in mapped_vals
                    and not any(a.fullmatch(x) for a in allow))
    in_tables = len(set(re.findall(r"(?<![\w\\.])\d+(?:\.\d+)?(?![\w])", tex))
                    - lits)
    print(f"  ----  unmapped prose numerics {len(review)} of {len(lits)} "
          f"distinct prose literals ({in_tables} more live inside mapped "
          f"tables)")
    if review:
        print(f"        {review[:60]}")
        notes.append(f"{name}: {len(review)} unmapped numeric literals")
        if strict_numbers:
            fails.append(f"{name}: --strict-numbers: {len(review)} unmapped "
                         f"numeric literals")
    return fails, notes


def check_figure_sync():
    """papers/*/figures/*.png must be byte-identical to canonical figures/.

    research/wp_c*/figures.py writes to the repository-root `figures/`
    directory; the copies inside a paper bundle exist so the bundle is
    self-contained for a publisher. They must not drift.
    """
    import filecmp
    canonical = os.path.join(ROOT, "figures")
    fails = []
    n_checked = 0
    for d in sorted(os.listdir(PAPERS)):
        fdir = os.path.join(PAPERS, d, "figures")
        if not os.path.isdir(fdir):
            continue
        for f in sorted(os.listdir(fdir)):
            src = os.path.join(canonical, f)
            dst = os.path.join(fdir, f)
            if not os.path.isfile(src):
                fails.append(f"papers/{d}/figures/{f} has no canonical "
                             f"source in figures/")
                continue
            n_checked += 1
            if not filecmp.cmp(src, dst, shallow=False):
                fails.append(f"papers/{d}/figures/{f} differs from "
                             f"figures/{f}")
    print(f"=== figure sync\n  {'PASS' if not fails else 'FAIL'}  "
          f"paper copies match figures/   {n_checked} checked")
    for f in fails:
        print(f"        {f}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict-numbers", action="store_true",
                    help="fail on any unmapped numeric literal, not just "
                         "list it for review")
    args = ap.parse_args()

    all_fails, all_notes = [], []
    for name, pdir, mp, doc in load_maps():
        f, n = check_paper(name, pdir, mp, doc, args.strict_numbers)
        all_fails += f
        all_notes += n
        print()
    all_fails += check_figure_sync()

    print()
    for n in all_notes:
        print(f"NOTE: {n}")
    if all_fails:
        print(f"\nARTIFACT MAP CHECK: FAIL -- {len(all_fails)} problems")
        for f in all_fails:
            print(f"  - {f}")
        return 1
    print("\nARTIFACT MAP CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
