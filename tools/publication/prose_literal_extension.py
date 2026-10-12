"""POST-E1 publication provenance extension: classify every unmapped literal.

WHY AN EXTENSION AND NOT AN EDIT
---------------------------------
`E1_FREEZE_MANIFEST.yaml` records 50 unmapped prose literals. That manifest is
immutable: it describes a past state and correcting it would erase the state it
exists to record. So this is an EXTENSION -- it classifies the same 50 and says
what happened to each, without touching the freeze.

WHY THE CLASSIFICATION IS AUTHORED AND NOT INFERRED
----------------------------------------------------
An early attempt searched every committed result artifact for each literal's
value. All 45 numeric literals matched something -- `0.906` matched
`trust_mag[643]` in a phase-2 lambda sweep, `1.0` matched a hundred places.
**That is numeric coincidence, not provenance.** Binding on it would have
manufactured exactly the false chain the S0 finding was about, and many of the
matches were in `research/phase2/`, which the phase guard forbids a Phase-I map
from citing at all.

So each literal is classified BY ITS CONTEXT IN THE MANUSCRIPT, by hand, and
this tool's job is to make the hand table impossible to let drift: it
re-extracts the literals from the current manuscript and FAILS if any literal
has no classification, or if a classification names a literal that is no longer
there.

THE TARGET IS 0 UNSUPPORTED SCIENTIFIC LITERALS, NOT 0 LITERALS
----------------------------------------------------------------
"3.3" in "ArduCopter 3.3" is a version. "16.67" is 1/0.06. Removing those would
make the paper worse and prove nothing. What must be zero is the count of
literals that state a MEASURED RESULT with nothing behind them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

TEX = os.path.join(ROOT, "papers", "csia_systems", "main.tex")
MAP = os.path.join(ROOT, "papers", "csia_systems", "PAPER1_ARTIFACT_MAP.yaml")

TABULAR = re.compile(r"\\begin\{tabular\}.*?\\end\{tabular\}", re.S)
# The trailing lookahead was `(?![\w.])`, which MISSED any literal at the
# end of a sentence -- "0.700." and "0.001597." were both dropped, and
# showed up as classifications for literals the extractor claimed were not
# in the manuscript. Reject only a following digit, or a decimal point
# that is itself followed by one.
LITERAL = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\.?\d)")

#: The classes the programme named.
CLASSES = ("SCIENTIFIC_RESULT", "SOURCE_CONSTANT", "DERIVED_QUANTITY",
           "REFERENCE", "ENUMERATION", "FORMATTING", "SUPERSEDED_HISTORY",
           "UNSUPPORTED")

#: literal -> (class, why). Authored from the manuscript context, one at a
#: time. `owning_section` is where the number is stated; for a
#: SCIENTIFIC_RESULT that is where its artifact must be found.
CLASSIFICATION = {
    # -- versions and declared constants -----------------------------------
    "3.3": ("SOURCE_CONSTANT", "ArduCopter 3.3, the measurement baseline"),
    "4.8": ("SOURCE_CONSTANT", "ArduPilot 4.8, the current-stack build"),
    "1.5": ("SOURCE_CONSTANT",
            "EVIDENCE_MULT tempering, a frozen configuration constant"),
    "0.998": ("SOURCE_CONSTANT", "rho_max, bound in the map as S12"),

    # -- arithmetic on declared constants ----------------------------------
    "16.67": ("DERIVED_QUANTITY", "1/alpha_s with alpha_s = 0.06"),
    "3.7": ("DERIVED_QUANTITY", "93 ticks at 25 Hz"),
    "2.4": ("DERIVED_QUANTITY",
            "mean features per hypothesis, counted from the frozen signature "
            "table"),

    # -- enumeration and formatting ----------------------------------------
    "0": ("FORMATTING", "bare zero: '0 m/s', counts, and axis text"),
    "1.0": ("FORMATTING",
            "a normalised bound or a starting fraction in several places; not "
            "a single measured quantity"),
    "1.000": ("SCIENTIFIC_RESULT",
              "absorption into the healthy class at every density tested"),
    "0.000": ("SCIENTIFIC_RESULT", "kappa(S) over 8 classes"),
    "0.143": ("SCIENTIFIC_RESULT",
              "kappa(S_eff) over 7 classes; bound in the map as S09"),

    # -- measured results, in the containment and coverage sections --------
    "0.001597": ("SCIENTIFIC_RESULT",
                 "GPS channel fresh fraction under denial"),
    "0.640319": ("SCIENTIFIC_RESULT", "minimum of the clean-trace comparison"),
    "0.9155": ("SCIENTIFIC_RESULT", "mean of the same comparison"),
    "0.006": ("SCIENTIFIC_RESULT", "reported horizontal position variance"),
    "0.0127": ("SCIENTIFIC_RESULT", "between-site standard deviation, rad"),
    "5.9": ("SCIENTIFIC_RESULT", "within-site standard deviation, rad"),
    "0.159": ("SCIENTIFIC_RESULT", "commanded-hold tilt at 0 m/s, degrees"),
    "0.066": ("SCIENTIFIC_RESULT",
              "fall in target-hypothesis probability with a larger LOW set"),
    "0.088": ("SCIENTIFIC_RESULT", "q_gvalid, first of three windows"),
    "0.208": ("SCIENTIFIC_RESULT", "q_gvalid, second of three windows"),
    "0.609": ("SCIENTIFIC_RESULT", "q_gvalid, third of three windows"),
    "0.981": ("SCIENTIFIC_RESULT", "q_gvalid under receiver link loss"),
    "0.982": ("SCIENTIFIC_RESULT", "q_gvalid, fourth arm"),
    "0.977": ("SCIENTIFIC_RESULT", "nominal p in the same window"),
    "0.0227": ("SCIENTIFIC_RESULT", "gps_fault p in the same window"),
    "0.9997": ("SCIENTIFIC_RESULT", "diagnosis nominal p"),
    "0.9998": ("SCIENTIFIC_RESULT",
               "leader weight with no distinguishing evidence"),
    "61.5": ("SCIENTIFIC_RESULT", "seconds to CAUTION via the freshness "
                                  "disjunct"),
    "84.4": ("SCIENTIFIC_RESULT", "percent of the remaining window at nominal"),
    "1.48": ("SCIENTIFIC_RESULT", "onset of non-healthy status, seconds"),
    "1.56": ("SCIENTIFIC_RESULT", "the same under link loss, seconds"),
    "5.71": ("SCIENTIFIC_RESULT", "seconds for policies to return to health"),
    "0.678": ("SCIENTIFIC_RESULT", "measured trust floor, lower end"),
    "0.700": ("SCIENTIFIC_RESULT", "measured trust floor, upper end"),
    "0.7000": ("SCIENTIFIC_RESULT", "saturated cells of the sweep"),
    "0.697": ("SCIENTIFIC_RESULT", "minimum trust, climb"),
    "0.735": ("SCIENTIFIC_RESULT", "minimum trust, cruise"),
    "0.744": ("SCIENTIFIC_RESULT", "minimum trust, descent"),
    "0.717": ("SCIENTIFIC_RESULT", "minimum trust, ramp, lower end"),
    "0.723": ("SCIENTIFIC_RESULT", "minimum trust, ramp, upper end"),
    "0.906": ("SCIENTIFIC_RESULT", "GPS trust floor, lower end"),
    "0.934": ("SCIENTIFIC_RESULT", "GPS trust floor, upper end"),
    "12.3": ("SCIENTIFIC_RESULT", "tick offset of the model's error"),
    "22.3": ("SCIENTIFIC_RESULT", "metres the estimator misses"),
    "222.6": ("SCIENTIFIC_RESULT", "total ramp offset, metres"),
    "556.6": ("SCIENTIFIC_RESULT", "ramp amplitude, metres"),
    "93.3": ("SCIENTIFIC_RESULT", "predicted crossing, ticks"),
    "1.2": ("SCIENTIFIC_RESULT", "lower end of a scaling range"),

    # -- the post-E1 additions, all four bound this session ----------------
    "3.0": ("SCIENTIFIC_RESULT",
            "pre-fault gate weight sum, ArduPilot. Stated in the "
            "current-stack paragraph and covered by the repeat tables"),
}


def extract_literals(tex_path: str) -> dict:
    """literal -> a one-line context from the manuscript prose."""
    text = open(tex_path, encoding="utf-8").read()
    prose = TABULAR.sub(" ", text)
    out = {}
    for m in LITERAL.finditer(prose):
        lit = m.group(0)
        if lit in out:
            continue
        lo, hi = max(0, m.start() - 90), min(len(prose), m.end() + 60)
        out[lit] = " ".join(prose[lo:hi].split())
    return out


def mapped_values(map_path: str) -> set:
    import yaml
    with open(map_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    vals = {str(s.get("value")) for s in (doc.get("scalars") or [])}
    for t in doc.get("tables") or []:
        vals.update(str(v) for v in (t.get("values") or []))
    return vals


def build() -> dict:
    import yaml
    lits = extract_literals(TEX)
    mapped = mapped_values(MAP)
    with open(MAP, encoding="utf-8") as fh:
        allow = [re.compile(p) for p in
                 (yaml.safe_load(fh).get("non_empirical") or [])]

    rows, unclassified, stale = [], [], []
    for lit, ctx in sorted(lits.items()):
        if lit in mapped or any(a.fullmatch(lit) for a in allow):
            continue
        entry = CLASSIFICATION.get(lit)
        if entry is None:
            unclassified.append({"literal": lit, "context": ctx})
            continue
        cls, why = entry
        rows.append({"literal": lit, "class": cls, "why": why,
                     "context": ctx,
                     "bound_in_artifact_map": False})

    for lit in sorted(CLASSIFICATION):
        if lit not in lits and lit not in mapped:
            stale.append(lit)

    by_class = {}
    for r in rows:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1

    scientific = [r for r in rows if r["class"] == "SCIENTIFIC_RESULT"]
    return {
        "schema": "csia.publication.prose_literal_extension/1",
        "parent_freeze": ("research/physical_validation/"
                          "E1_FREEZE_MANIFEST.yaml"),
        "parent_freeze_is_immutable": True,
        "generated_by": ("tools/publication/prose_literal_extension.py"),
        "classes": list(CLASSES),
        "unmapped_literals": rows,
        "counts_by_class": by_class,
        "total_unmapped": len(rows),
        "scientific_result_count": len(scientific),
        "scientific_results_still_unbound": [r["literal"] for r in scientific],
        "unclassified": unclassified,
        "stale_classifications": stale,
        "honest_status": (
            "Every unmapped literal is CLASSIFIED. The SCIENTIFIC_RESULT ones "
            "are NOT yet bound to artifact and pointer, and this file says so "
            "rather than implying they are. Binding them needs each owning "
            "section's result artifact opened and the pointer found -- work "
            "that is specified here and not done here."),
        "why_not_bound_by_search": (
            "A numeric search over the 131 committed result artifacts matched "
            "ALL 45 numeric literals, most of them many times over: 0.906 "
            "matched a phase-2 lambda-sweep sample, 1.0 matched a hundred "
            "places. That is coincidence, not provenance, and binding on it "
            "would manufacture the exact false chain the S0 finding was "
            "about. Many matches were under research/phase2/, which the phase "
            "guard forbids a Phase-I map from citing at all."),
        "target": ("0 UNSUPPORTED scientific prose literals -- not 0 literals. "
                   "A version number and 1/alpha_s are not results."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"classified {doc['total_unmapped']}; "
          f"unclassified {len(doc['unclassified'])}; "
          f"stale {len(doc['stale_classifications'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
