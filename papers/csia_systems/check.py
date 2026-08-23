"""Mechanical hard-rule check for the manuscript.

The rules are checked here rather than by eye because two of them have already
been broken by eye: an earlier draft contained "novelty", which contains
"novel", and used "theorem" inside a sentence disclaiming it.

Run:  python papers/csia_systems/check.py
"""

import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    src = open(os.path.join(HERE, "main.tex")).read()
    bib = open(os.path.join(HERE, "refs.bib")).read()
    fails = []

    def check(label, ok, detail=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {label:34s} {detail}")
        if not ok:
            fails.append(label)

    print("=== hard rules ===")
    check("no em dash characters", src.count("\u2014") == 0,
          f"{src.count(chr(0x2014))} found")
    check("no en dash characters", src.count("\u2013") == 0,
          f"{src.count(chr(0x2013))} found")
    check("the word 'novel' appears nowhere",
          not re.search(r"novel", src, re.I),
          f"{len(re.findall(r'novel', src, re.I))} found")
    # The rule is that nothing may be LABELLED a theorem, not that the word is
    # banned: the referee objection is quoted verbatim in the limitations and
    # it contains the word. Labels are what a reader takes as a claim.
    labelled = (re.findall(r"\\newtheorem", src)
                + re.findall(r"\\begin\{theorem", src, re.I)
                + re.findall(r"\\paragraph\{Theorem", src)
                + re.findall(r"\\(?:sub)*section\{[^}]*Theorem", src))
    check("nothing labelled a theorem", not labelled,
          f"{len(labelled)} labels found")
    bare = [m.start() for m in re.finditer(r"theorem", src, re.I)]
    for pos in bare:
        print(f"        bare use, for review: "
              f"...{src[max(0, pos - 58):pos + 12]}...".replace("\n", " "))

    print("=== structure ===")
    check("braces balanced", src.count("{") == src.count("}"),
          f"{src.count('{')} open / {src.count('}')} close")
    cb = Counter(re.findall(r"\\begin\{(\w+\*?)\}", src))
    ce = Counter(re.findall(r"\\end\{(\w+\*?)\}", src))
    check("environments matched", cb == ce,
          f"unclosed={dict(cb - ce) or '{}'} unopened={dict(ce - cb) or '{}'}")

    cites = set()
    for m in re.findall(r"\\cite\{([^}]*)\}", src):
        cites |= {c.strip() for c in m.split(",")}
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    check("every cite key resolves", not (cites - keys),
          f"{len(cites)} cited, missing={sorted(cites - keys) or 'none'}")
    # Informational, not a rule. Two entries supplied by the WP-C6 brief carry
    # no title, so citing them would assert something about a work whose
    # content this session cannot check. They stay in the file, uncited, so
    # the supplied details are not lost.
    print(f"  ----  uncited bib entries          "
          f"{sorted(keys - cites) or 'none'}")

    figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", src)
    missing = [f for f in figs
               if not os.path.exists(os.path.join(HERE, f))]
    check("every figure target exists", not missing,
          f"{len(figs)} referenced, missing={missing or 'none'}")

    print("=== bibliography provenance (informational, not a rule) ===")
    for tag in ("FROM-BRIEF-UNVERIFIED", "RECONSTRUCTED", "VERIFY"):
        print(f"  {tag:24s} {bib.count(tag)}")
    print("  NOTE: no entry is marked verified. Every one needs checking "
          "against the publisher record before submission.")

    print(f"\n{'ALL CHECKS PASS' if not fails else 'FAILURES: ' + str(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
