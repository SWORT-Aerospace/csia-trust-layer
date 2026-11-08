"""Refresh the self-contained figure copies inside each paper bundle.

`research/wp_c*/figures.py` writes to the repository-root `figures/`
directory, which is canonical. Each paper keeps its own copy so the submission
bundle is self-contained for a publisher who receives only that directory.
This copies canonical -> bundle and reports drift.

`--check` copies nothing and exits non-zero if any bundle copy differs, which
is what CI runs.

Run:  python tools/publication/sync_paper_figures.py [--check]
"""

import argparse
import filecmp
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CANON = os.path.join(ROOT, "figures")
PAPERS = os.path.join(ROOT, "papers")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    drift, orphan, copied, same = [], [], [], 0
    for d in sorted(os.listdir(PAPERS)):
        fdir = os.path.join(PAPERS, d, "figures")
        if not os.path.isdir(fdir):
            continue
        for f in sorted(os.listdir(fdir)):
            src, dst = os.path.join(CANON, f), os.path.join(fdir, f)
            rel = f"papers/{d}/figures/{f}"
            if not os.path.isfile(src):
                orphan.append(rel)
                continue
            if filecmp.cmp(src, dst, shallow=False):
                same += 1
                continue
            if args.check:
                drift.append(rel)
            else:
                shutil.copy2(src, dst)
                copied.append(rel)

    print(f"in sync: {same}")
    for r in copied:
        print(f"  copied  {r}")
    for r in drift:
        print(f"  DRIFT   {r}")
    for r in orphan:
        print(f"  ORPHAN  {r}  (no canonical figures/ source)")

    if orphan or (args.check and drift):
        print("\nFAIL: bundle figures are not a faithful copy of figures/.")
        print("Regenerate with research/wp_c*/figures.py, then run this "
              "without --check.")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
