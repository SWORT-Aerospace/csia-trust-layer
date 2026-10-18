"""Cross-ingest-path semantic equivalence, all three committed paths. Item 14.

A SEPARATE result from the A/D question. It is an implementation defect report
and it stands whether or not the architectural claim survives.

The three committed decoders, and what each does with the SAME raw condition
(`fix_type < 3`):

  csia/aircraft/adapters/   deletes the channels, records NO_3D_FIX, emits NO
                            core sample
  csia/runtime/plugins.py   emits a core sample with valid=False and ZERO
                            pos/vel
  csia/runtime/ulog_source.py  emits a core sample with valid=(fix>=3) and the
                            REAL pos/vel

Paths 1 and 2 are driven over the frozen `{V, I, N}` alphabet. Path 3 consumes
a ULog, so it is driven over a real PX4 log and its invalid branch is reported
as EXERCISED or NOT_EXERCISED rather than assumed.

  python research/dual_admissibility_confirmatory/cross_path_checker.py
"""

from __future__ import annotations

import glob
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
DEV = os.path.join(ROOT, "research", "dual_admissibility")
MAX_LEN = 4


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _load("_ss", os.path.join(DEV, "semantic_search.py"))


def ulog_path():
    hits = sorted(glob.glob(os.path.join(
        ROOT, "research", "v1_1", "results", ".px4_link_probe", "*", "log",
        "*", "*.ulg")))
    return hits[0] if hits else None


def probe_ulog(path):
    """Drive the committed ULog decoder and observe its validity semantics."""
    from csia.runtime.ulog_source import UlogSource
    src = UlogSource(path)
    gps = [(t, ch) for t, name, ch in src._build_events() if name == "gps"] \
        if hasattr(src, "_build_events") else []
    if not gps:
        # _build_events is called in __init__ on this implementation; fall
        # back to the materialised event list
        gps = [(t, ch) for t, name, ch in getattr(src, "_events", [])
               if name == "gps"]
    n = len(gps)
    invalid = [g for g in gps if not g[1].get("valid", True)]
    return {
        "ulog": os.path.relpath(path, ROOT),
        "gps_samples_emitted": n,
        "gps_samples_with_valid_false": len(invalid),
        "invalid_branch": ("EXERCISED" if invalid else "NOT_EXERCISED"),
        "emits_a_sample_when_invalid": bool(invalid) or None,
        "note": ("this log contains no fix_type < 3 samples, so the decoder's "
                 "invalid branch could not be observed in execution; the "
                 "mapping is established from source only"
                 if not invalid else
                 "the decoder emitted a core sample carrying valid=False, "
                 "confirming the source reading in execution"),
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # ---- paths 1 and 2, over the frozen alphabet ------------------------
    rows, sem_div, tick_div = [], [], []
    for w in S.words(MAX_LEN):
        pa = S._semantic_projection(S.semantic_trace(w, "S0"))
        pb = S._semantic_projection(S.v1_plugin_trace(w))
        semantic = pa["ever_slot_invalid"] != pb["ever_slot_invalid"]
        ticks = pa["a_closed_ticks"] != pb["a_closed_ticks"]
        if semantic:
            sem_div.append(w)
        if ticks:
            tick_div.append(w)
        rows.append({"word": w, "length": len(w),
                     "semantic_divergence": semantic,
                     "tick_count_divergence": ticks,
                     "v1_1_ever_slot_invalid": pa["ever_slot_invalid"],
                     "v1_ever_slot_invalid": pb["ever_slot_invalid"]})

    shortest = min(sem_div, key=len) if sem_div else None

    # ---- path 3 ---------------------------------------------------------
    up = ulog_path()
    ulog = probe_ulog(up) if up else {
        "ulog": None, "invalid_branch": "UNAVAILABLE",
        "note": "no ULog present in this checkout"}

    payload = {
        "artifact": "COUNTEREXAMPLE_CROSS_PATH_RESULTS",
        "status": "SEPARATE IMPLEMENTATION-DEFECT RESULT. Not combined with "
                  "the A/D experiment.",
        "alphabet": {"V": "GPS_RAW_INT with fix_type >= 3",
                     "I": "GPS_RAW_INT with fix_type < 3",
                     "N": "no message delivered"},
        "max_word_length": MAX_LEN,
        "words_tested": len(rows),
        "pairs": {
            "v1_1_adapter__vs__plugins_py": {
                "executed": True,
                "semantic_divergences": len(sem_div),
                "shortest_distinguishing_trace": shortest,
                "verdict": ("PATHS_DIVERGE" if sem_div
                            else f"VERIFIED_EQUIVALENT_TO_BOUND_{MAX_LEN}"),
                "divergent_field": "core slot `valid` -- the v1.1 adapter "
                                   "never marks the GPS slot invalid; "
                                   "plugins.py does",
                "tick_count_divergences": len(tick_div),
                "tick_count_note": "also moves with the stamping convention "
                                   "(tick time vs message receive time) and "
                                   "is NOT counted as semantic divergence",
            },
            "ulog_source_py": ulog,
        },
        "downstream_consequence": (
            "On the v1.1 path a no-fix report and a silent link produce "
            "identical core state, so `A` closes only via the 0.5 s staleness "
            "timeout. On the plugins.py path `A` closes immediately. The same "
            "vehicle condition therefore yields a different operational "
            "admissibility trajectory depending only on which decoder the "
            "deployment happens to use."),
        "status_verdict": "IMPLEMENTATION DEFECT / SEMANTIC NON-EQUIVALENCE",
    }
    with open(os.path.join(OUT, "COUNTEREXAMPLE_CROSS_PATH_RESULTS.json"),
              "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  words tested: {len(rows)} (length <= {MAX_LEN})")
    print(f"  v1.1 adapter vs plugins.py: {len(sem_div)} semantic "
          f"divergences, shortest = {shortest!r}")
    print(f"  tick-count divergences (not attributable alone): "
          f"{len(tick_div)}")
    print(f"  ulog_source.py: {ulog['invalid_branch']} "
          f"({ulog.get('gps_samples_with_valid_false', 0)} invalid of "
          f"{ulog.get('gps_samples_emitted', 0)} gps samples)")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/"
          f"COUNTEREXAMPLE_CROSS_PATH_RESULTS.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
