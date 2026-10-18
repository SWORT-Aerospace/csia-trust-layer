"""Trace GPS_RAW_INT.fix_type all the way to gvalid, verified against the tree.

This artifact is not a transcription. Every claim below is a PATTERN that must
occur EXACTLY ONCE in the named file; the script resolves it to a line number,
records the line verbatim, and fails loudly if the pattern is missing or
ambiguous. A refactor that moves the behaviour breaks this script rather than
silently invalidating the report.

  python research/invalidity_masking/source_to_gate_trace.py

Writes results/SOURCE_TO_GATE_TRACE.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# (fact_id, path, regex, what this line establishes)
FACTS = [
    # --- stage 1: the protocol observation -------------------------------
    ("P1_FIX_TYPE_READ",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+fix = g\("fix_type", 0\)$',
     "the adapter reads GPS_RAW_INT.fix_type"),
    ("P2_INVALID_PREDICATE",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+if fix is None or fix < 3:$',
     "fix_type < 3 (or absent) is the invalidity predicate"),

    # --- stage 2: what the adapter does with it --------------------------
    ("A1_FORGET_POSITION",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+self\._latest\.pop\("gnss\.position", None\)$',
     "the previously accepted position is DELETED, not marked invalid"),
    ("A2_FORGET_VELOCITY",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+self\._latest\.pop\("gnss\.velocity", None\)$',
     "the previously accepted velocity is DELETED, not marked invalid"),
    ("A3_REJECT_REASON",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+reason=MissingReason\.NO_3D_FIX\)$',
     "the adapter records the DISTINCT reason NO_3D_FIX for the rejection"),
    ("A4_EARLY_RETURN",
     "csia/aircraft/adapters/ardupilot.py",
     r'^[ \t]+reason=MissingReason\.NO_3D_FIX\)\n[ \t]+return$',
     "no channel value of any kind is produced from an invalid fix"),

    # --- stage 3: the hand-off to the frozen core ------------------------
    ("H1_ALL_CHANNELS_REQUIRED",
     "csia/aircraft/adapters/base.py",
     r'^[ \t]+complete = False$',
     "a sensor with any unusable channel is withheld entirely"),
    ("H2_VALID_IS_HARDCODED_TRUE",
     "csia/aircraft/adapters/base.py",
     r'^[ \t]+chans\["valid"\] = True$',
     "EVERY emitted core sample carries valid=True unconditionally: this "
     "hand-off has no way to express OBSERVED_INVALID"),
    ("H3_GPS_CORE_MAP",
     "csia/aircraft/adapters/base.py",
     r'^[ \t]+"gps": \{"pos": "gnss\.position", "vel": "gnss\.velocity"\},$',
     "both gps core channels come from the two channels the reject deletes, "
     "so an invalid fix withholds the whole gps sensor"),

    # --- stage 4: core slot update semantics -----------------------------
    ("C1_SLOT_DEFAULT_INVALID",
     "csia/runtime/online.py",
     r'^[ \t]+valid: bool = False$',
     "a slot starts invalid"),
    ("C2_SLOT_DEFAULT_LAST_T",
     "csia/runtime/online.py",
     r'^[ \t]+last_t: float = -1e9$',
     "a slot starts infinitely stale"),
    ("C3_SLOTS_CONSTRUCTED_ONCE",
     "csia/runtime/online.py",
     r'^[ \t]+self\.slots = \{n: _SensorSlot\(\) for n in SENSORS\}$',
     "slots are built once in __init__ and never rebuilt"),
    ("C4_APPLY_SETS_SEEN",
     "csia/runtime/online.py",
     r'^[ \t]+slot\.seen = True$',
     "seen is set on every accepted sample and cleared nowhere"),
    ("C5_APPLY_SETS_LAST_T",
     "csia/runtime/online.py",
     r'^[ \t]+slot\.last_t = t$',
     "last_t advances ONLY on an accepted sample"),
    ("C6_APPLY_SETS_VALID",
     "csia/runtime/online.py",
     r'^[ \t]+slot\.valid = bool\(ch\.get\("valid", True\)\)$',
     "valid is written ONLY here, from the sample's own flag, defaulting "
     "True; no sample means no write, so the previous value persists"),

    # --- stage 5: the gates ----------------------------------------------
    ("G1_GVALID_HAS_NO_STALENESS",
     "csia/runtime/online.py",
     r'^[ \t]+gvalid = 1\.0 if s\["gps"\]\.valid and s\["gps"\]\.seen else 0\.0$',
     "gvalid is a pure retained-state predicate: no time term at all"),
    ("G2_FRESH_HAS_STALENESS",
     "csia/runtime/online.py",
     r'^[ \t]+fresh = \{n: s\[n\]\.valid and s\[n\]\.seen\n'
     r'[ \t]+and \(tau - s\[n\]\.last_t\) <= self\._stale\[n\]$',
     "fresh is gvalid's predicate PLUS a timeout against last_t"),
    ("G3_EDGES_MULTIPLIED_BY_FRESH",
     "csia/runtime/online.py",
     r'^[ \t]+E = \{key: \(lam, gate \* float\(fresh\[self\._edge_meta\[key\]\[0\]\]\)$',
     "every edge gate is multiplied by BOTH endpoints' freshness"),
    ("G4_PHYS_MULTIPLIED_BY_FRESH",
     "csia/runtime/online.py",
     r'^[ \t]+P = \{n: \(lam, gate \* float\(fresh\[n\]\)\) for n, \(lam, gate\) in P\.items\(\)\}$',
     "every physics gate is multiplied by its own sensor's freshness"),
    ("G5_GPS_TIMEOUT_VALUE",
     "csia/runtime/online.py",
     r'^[ \t]+"imu0": 0\.05, "imu1": 0\.05, "baro": 0\.1, "mag": 0\.1, "gps": 0\.5,$',
     "the gps staleness timeout is 0.5 s"),
    ("G6_TRUST_UPDATE_GATED_ON_FRESH",
     "csia/trust_engine/engine.py",
     r'^[ \t]+if avail and fresh\.get\(n, True\):$',
     "the node's Beta belief updates only while that node is fresh"),

    # --- the two OTHER ingest paths, same core ---------------------------
    ("X1_V1_MAVLINK_PROPAGATES_INVALID",
     "csia/runtime/plugins.py",
     r'^[ \t]+"vz_valid": False, "valid": False\}\)\)$',
     "the v1 live-MAVLink path EMITS a gps sample carrying valid=False on "
     "fix_type < 3 instead of withholding it"),
    ("X2_V1_MAVLINK_INVALID_PREDICATE",
     "csia/runtime/plugins.py",
     r'^[ \t]+if msg\.fix_type < 3:$',
     "same raw predicate as the v1.1 adapter, opposite handling"),
    ("X3_V1_MAVLINK_ZERO_PAYLOAD",
     "csia/runtime/plugins.py",
     r'^[ \t]+out\.append\(\("gps", t, \{"pos": _np\.zeros\(3\), "vel": _np\.zeros\(3\),$',
     "the propagated invalid sample carries ZEROS, which still reach the "
     "step detector and the Holt filters (see DIAGNOSTIC_CONSEQUENCES)"),
    ("X4_ULOG_PROPAGATES_INVALID",
     "csia/runtime/ulog_source.py",
     r'^[ \t]+"pos": pos, "vel": vel, "valid": bool\(fix\[i\] >= 3\)\}\)\)$',
     "the ULog replay path also emits the sample and propagates validity"),

    # --- the unconditional side effects on an accepted gps sample --------
    ("S1_STEP_PEAK_UNCONDITIONAL",
     "csia/runtime/online.py",
     r'^[ \t]+self\._gps_step_peak = max\(self\._gps_step_peak,$',
     "the step detector is fed by EVERY emitted gps sample regardless of "
     "its valid flag"),
    ("S2_HIST_FED_UNCONDITIONAL",
     "csia/runtime/online.py",
     r'^[ \t]+lams\.append\(\(h\.innovation\(float\(x\)\) / sigma\) \*\* 2\)$',
     "the historical predictor is fed by EVERY emitted sample regardless "
     "of its valid flag"),
    ("S3_GPS_IN_HIST_CHANNELS",
     "csia/prediction/predictors.py",
     r'^[ \t]+"gps":[ \t]+\[\("pos", 2, 0\.60\), \("vel", 0, 0\.50\), '
     r'\("vel", 1, 0\.50\),$',
     "gps has historical channels, so an emitted invalid sample is not "
     "inert inside the core"),
]

# Relations whose gate carries gvalid, and the edge endpoints that decide
# which freshness flags multiply them. Resolved from source, not asserted.
GVALID_RELATIONS = ("altitude_baro", "velocity_gps_doppler_0",
                    "velocity_gps_doppler_1", "heading_course")


def _resolve(path, pattern):
    """Return (line_no, verbatim_text) for the unique match, or raise."""
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as fh:
        text = fh.read()
    hits = list(re.finditer(pattern, text, re.MULTILINE))
    if len(hits) != 1:
        raise AssertionError(
            f"{path}: pattern matched {len(hits)} times, expected exactly 1\n"
            f"  {pattern}")
    start = hits[0].start()
    line_no = text.count("\n", 0, start) + 1
    snippet = hits[0].group(0)
    # Independent re-read: index the file by line and confirm the number we
    # are about to publish really points at the matched text. `\s` matches
    # newlines, so a pattern written with `\s+` after a blank line silently
    # resolved one line early -- caught here, then fixed at the patterns.
    lines = text.splitlines()
    if lines[line_no - 1] != snippet.splitlines()[0]:
        raise AssertionError(
            f"{path}:{line_no} does not contain the matched text\n"
            f"  matched: {snippet.splitlines()[0]!r}\n"
            f"  line is: {lines[line_no - 1]!r}")
    return line_no, snippet


def _sha(path):
    with open(os.path.join(ROOT, path), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def gvalid_relation_endpoints():
    """Which freshness flags actually multiply each gvalid-carrying gate.

    Read from csia.trust_graph.EDGES plus the two dual-doppler keys that
    online.py rebinds explicitly, rather than assumed.
    """
    sys.path.insert(0, ROOT)
    from csia.trust_graph.graph import EDGES
    meta = {}
    for a, b, relation, _ in EDGES:
        meta.setdefault(relation, (a, b))
    meta["velocity_gps_doppler_0"] = ("imu0", "gps")
    meta["velocity_gps_doppler_1"] = ("imu1", "gps")
    meta.pop("velocity_gps_doppler", None)
    out = {}
    for rel in GVALID_RELATIONS:
        a, b = meta[rel]
        out[rel] = {"endpoints": [a, b], "gps_is_endpoint": "gps" in (a, b)}
    return out


def main() -> int:
    facts, files = [], {}
    failures = []
    for fid, path, pattern, meaning in FACTS:
        files.setdefault(path, _sha(path))
        try:
            line_no, snippet = _resolve(path, pattern)
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        facts.append({
            "fact_id": fid,
            "file": path,
            "line": line_no,
            "cite": f"{path}:{line_no}",
            "source": snippet,
            "establishes": meaning,
        })

    if failures:
        print("SOURCE TRACE FAILED -- the tree no longer matches the trace:")
        for f in failures:
            print("  " + f)
        return 1

    rel = gvalid_relation_endpoints()
    every_gvalid_relation_touches_gps = all(
        v["gps_is_endpoint"] for v in rel.values())

    payload = {
        "artifact": "SOURCE_TO_GATE_TRACE",
        "question": "GPS_RAW_INT.fix_type -> adapter -> to_core_samples -> "
                    "slot -> freshness -> gvalid",
        "file_sha256": files,
        "facts": facts,
        "gvalid_relations": rel,
        "every_gvalid_relation_has_gps_as_an_endpoint":
            every_gvalid_relation_touches_gps,
        "n_facts_verified": len(facts),
    }
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, "SOURCE_TO_GATE_TRACE.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"  {len(facts)} source facts verified against the tree")
    print(f"  every gvalid relation has gps as an endpoint: "
          f"{every_gvalid_relation_touches_gps}")
    print(f"  -> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
