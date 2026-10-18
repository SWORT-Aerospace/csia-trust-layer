"""The semantic authorities, each pinned to an independently checkable source.

Item 1 names four candidate authorities and item 2 forbids assuming any of
them is truth. Item 58-I demands every authority correspond to an
independently identifiable source, so each entry below carries a citation
that `verify()` re-reads from disk.

    C_spec       the MAVLink message definition (attribute + description)
    C_producer   ArduPilot's own executable source, i.e. what actually fills
                 the field on the wire
    C_consumer_* the three committed CSIA ingest paths
    C_observed_* what those paths actually put into the frozen core, measured

No C_test, C_documentation or C_operator: item 1 says not to inflate the
authority set, and nothing in the three cases needed them.

A FIFTH VALUE that turned out to matter more than any authority: SILENT.
An authority that says nothing about a raw state does not disagree about it.
Item 8 defines conflict as |{C_a(r)}| > 1, which would count a silence as a
disagreement if silence were encoded as an interpretation. It is not.

  python research/semantic_authority_conflict/authorities.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
AP = "/home/user/ardupilot/ardupilot"
MAVLINK = os.path.join(AP, "modules/mavlink/message_definitions/v1.0")

SILENT = "SILENT"          # the authority does not speak to this raw state


def cite(path, line, quote, base=ROOT):
    """A citation that can be re-read. Whitespace-normalised comparison.

    `line` is a line number or range for source files, and a MESSAGE.field
    reference for a protocol schema.
    """
    return {"locator": f"{path}:{line}", "quote": quote, "_base": base}


def _verify_schema(c):
    """`common.xml:MESSAGE.field` -- the field's attributes and description.

    The first version cited the schema by LINE NUMBER, wrote `:1` as a
    placeholder, and every schema citation failed. Recorded rather than
    silently repaired: the checker caught its own author.
    """
    import xml.etree.ElementTree as ET
    path, ref = c["locator"].rsplit(":", 1)
    full = os.path.join(MAVLINK, os.path.basename(path))
    if not os.path.exists(full) or "." not in ref:
        return False, f"bad schema locator {c['locator']}"
    msg_name, field_name = ref.split(".", 1)
    for msg in ET.parse(full).getroot().iter("message"):
        if msg.get("name") != msg_name:
            continue
        for f in msg.findall("field"):
            if f.get("name") != field_name:
                continue
            blob = " ".join([f'{k}="{v}"' for k, v in sorted(f.attrib.items())]
                            + [(f.text or "")])
            blob = re.sub(r"\s+", " ", blob).strip()
            want = re.sub(r"\s+", " ", c["quote"]).strip()
            return (want in blob), ("" if want in blob else
                                    f"quote not in {ref}: {blob[:120]}")
        return False, f"field {field_name} not in {msg_name}"
    return False, f"message {msg_name} not in {path}"


# The commit at which THIS package's citations were taken. Not the v1.0
# diagnostic-core tag: that tag predates the adapter work entirely, and
# `csia/aircraft/adapters/ardupilot.py` does not exist in it.
CITED_REVISION = "76eaa17"


def _v1_source(rel: str, path: str):
    """Read a cited CSIA file AS IT WAS WHEN THE CITATION WAS TAKEN.

    This package's findings are findings about **v1**. Reading the citation
    out of the working tree silently re-points a v1 claim at whatever CSIA
    happens to be today, which is wrong in both directions: an engineering fix
    makes a true historical claim look unsupported, and an unrelated edit can
    make a false one look supported.

    The revision is this package's own commit, not the v1.0 tag: the v1.0
    tag froze the diagnostic core before the aircraft adapters existed, so
    `csia/aircraft/adapters/ardupilot.py` is absent from it.

    The v1.1 engineering pass proved the point. Fixing the battery-sentinel
    and magnetometer defects shifted line numbers in
    `csia/aircraft/adapters/ardupilot.py` and removed the retained-value
    behaviour entirely, so four citations that were correct about v1 stopped
    resolving. The claims did not become wrong; the pointer became wrong.

    Non-CSIA citations (ArduPilot, PX4, the MAVLink schema) are read from disk
    as before: they live outside this repository and are pinned by their own
    revisions, recorded in the package README.
    """
    rel = rel.replace(os.sep, "/")
    if rel.startswith("csia/"):
        try:
            r = subprocess.run(["git", "show", f"{CITED_REVISION}:{rel}"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout
        except OSError:
            pass                       # no git; fall through to the worktree
    if not os.path.exists(path):
        return None
    return open(path, encoding="utf-8", errors="replace").read()


def verify(c):
    if c["locator"].rsplit(":", 1)[0].endswith(".xml"):
        return _verify_schema(c)
    full = c["locator"].rsplit(":", 1)[0]
    line = int(c["locator"].rsplit(":", 1)[1].split("-")[0])
    last = int(c["locator"].rsplit(":", 1)[1].split("-")[-1])
    path = full if os.path.isabs(full) else os.path.join(c["_base"], full)
    text = _v1_source(full, path)
    if text is None:
        return False, f"missing file {path}"
    lines = text.splitlines()
    if last > len(lines):
        return False, "line out of range"
    blob = re.sub(r"\s+", " ", " ".join(lines[line - 1:last])).strip()
    want = re.sub(r"\s+", " ", c["quote"]).strip()
    return (want in blob), ("" if want in blob else f"not at {c['locator']}")


# ===========================================================================
# CASE 1 -- BATTERY. Raw state: BATTERY_STATUS.current_battery == -1
# ===========================================================================
BATTERY = {
    "case": "battery.current_not_measured",
    "raw_state": "BATTERY_STATUS.current_battery == -1",
    "authorities": {
        "C_spec": {
            "aspect": "value_semantics",
            "interpretation": "NOT_MEASURED",
            "declared": "the autopilot does not measure the current",
            "support": [cite("common.xml", "BATTERY_STATUS.current_battery",
                             'invalid="-1"', base=MAVLINK),
                        cite("common.xml", "BATTERY_STATUS.current_battery",
                             "-1: autopilot does not measure the current",
                             base=MAVLINK)],
            "support_kind": "PROTOCOL_SCHEMA",
            "note": "carried as a machine-readable attribute AND in the "
                    "field description: 'Battery current, -1: autopilot does "
                    "not measure the current.'",
        },
        "C_producer": {
            "aspect": "value_semantics",
            "interpretation": "NOT_MEASURED",
            "declared": "ArduPilot writes -1 exactly when it has no current "
                        "reading to give",
            "support": [cite("libraries/GCS_MAVLink/GCS_Common.cpp",
                             "390-393",
                             "if (battery.current_amps(current, instance)) {",
                             base=AP)],
            "support_kind": "PRODUCER_SOURCE",
            "note": "the else branch is literally `current = -1;`. A second "
                    "site, GCS_Common.cpp:6003-6007, does the same for "
                    "SYS_STATUS and additionally requires battery.healthy().",
        },
        "C_consumer_A": {
            "aspect": "value_semantics",
            "interpretation": "RETAIN_PREVIOUS",
            "declared": "record a sentinel, then keep serving the last value",
            "support": [cite("csia/aircraft/adapters/ardupilot.py", 181,
                             'self._reject_sentinel("battery.current")')],
            "support_kind": "CONSUMER_SOURCE",
            "note": "_latest is not popped, so base.py:199's `entry is None` "
                    "guard never reaches the sentinel branch",
        },
        "C_consumer_B": {
            "aspect": "value_semantics",
            "interpretation": "SUBSTITUTE_ZERO",
            "declared": "clamp the sentinel to zero and mark the sample valid",
            "support": [cite("csia/runtime/plugins.py", 194,
                             '"current": max(msg.current_battery, 0) / 100.0,')],
            "support_kind": "CONSUMER_SOURCE",
        },
        "C_consumer_C": {
            "aspect": "value_semantics",
            "interpretation": "LITERAL_MINUS_ONE",
            "declared": "pass the number through as a measurement",
            "support": [cite("csia/runtime/ulog_source.py", "196-199",
                             '"current": float(d["current_a"][i]), "valid": True}))')],
            "support_kind": "CONSUMER_SOURCE",
            "note": "there is no branch that could read a sentinel; valid is "
                    "unconditionally True",
        },
    },
}

# ===========================================================================
# CASE 2 -- GNSS. Raw state: GPS_RAW_INT.fix_type < 3
# ===========================================================================
GNSS = {
    "case": "gnss.no_3d_fix",
    "raw_state": "GPS_RAW_INT.fix_type < 3",
    "authorities": {
        "C_spec": {
            # speaks about what fix_type MEANS, not about what the
            # position fields contain. Comparing it against an authority
            # about the position fields was a category error in the first
            # version and produced a spurious SPEC_VS_PRODUCER conflict.
            "aspect": "fix_type_meaning",
            "interpretation": "NO_POSITION_INFORMATION",
            "declared": "fix_type 1 = NO_FIX, 'No position information, GPS "
                        "is connected'",
            "support": [cite("common.xml", "GPS_RAW_INT.fix_type",
                             'enum="GPS_FIX_TYPE"', base=MAVLINK)],
            "support_kind": "PROTOCOL_SCHEMA",
            "note": "the enum GPS_FIX_TYPE settles what fix_type MEANS.",
        },
        "C_spec_position_fields": {
            "aspect": "position_fields",
            "interpretation": SILENT,
            "declared": "the schema says NOTHING about what lat/lon/alt hold "
                        "when fix_type < 3",
            "support": [cite("common.xml", "GPS_RAW_INT.lat",
                             "Latitude (WGS84, EGM96 ellipsoid)",
                             base=MAVLINK)],
            "support_kind": "PROTOCOL_SCHEMA",
            "note": "lat, lon and alt carry NO `invalid=` attribute and no "
                    "description clause covering the no-fix case. This is "
                    "UNDERSPECIFICATION, not disagreement, and it is the "
                    "single most consequential fact in this package.",
        },
        "C_producer": {
            "aspect": "position_fields",
            "interpretation": "STALE_POSITION_WITH_HONEST_FIX_TYPE",
            "declared": "send the last known Location with whatever fix_type "
                        "currently holds; do not blank the position",
            "support": [cite("libraries/AP_GPS/AP_GPS.cpp", "1399-1417",
                             "const Location &loc = location(0);", base=AP)],
            "support_kind": "PRODUCER_SOURCE",
            "note": "loc.lat/lng/alt are sent unconditionally alongside "
                    "(uint8_t)status(0). The producer's position is that "
                    "fix_type is the authority and the coordinates are "
                    "whatever the driver last had.",
        },
        "C_producer_absence": {
            # SCOPE CORRECTION, caught before reporting: this authority
            # describes a DIFFERENT raw state (no GPS configured at all), not
            # fix_type < 3. Pooling it into the no-fix resolution made
            # IMPLEMENTATION_FIRST look self-inconsistent when it is not.
            # Retained as context, excluded from precedence resolution.
            "scope": "different_raw_state: GPS_TYPE_NONE, no message sent",
            "interpretation": "NO_MESSAGE_AT_ALL",
            "declared": "with no GPS configured the message is not sent",
            "support": [cite("libraries/AP_GPS/AP_GPS.cpp", "1394-1396",
                             "if (get_type(0) == GPS_TYPE_NONE) {", base=AP)],
            "support_kind": "PRODUCER_SOURCE",
            "note": "so at the producer, 'no fix' and 'no message' are "
                    "genuinely different conditions -- which is what makes "
                    "the consumer-side collapse a loss rather than a "
                    "convention.",
        },
        "C_consumer_A": {
            "aspect": "position_fields",
            "interpretation": "DROP_AND_RECORD_REASON",
            "declared": "discard the retained fix and record NO_3D_FIX",
            "support": [cite("csia/aircraft/adapters/ardupilot.py", "232-235",
                             'self._latest.pop("gnss.position", None)')],
            "support_kind": "CONSUMER_SOURCE",
        },
        "C_consumer_B": {
            "aspect": "position_fields",
            "interpretation": "SUBSTITUTE_ZERO_MARK_INVALID",
            "declared": "emit a zero position with valid=False",
            "support": [cite("csia/runtime/plugins.py", "157-159",
                             'out.append(("gps", t, {"pos": _np.zeros(3), "vel": _np.zeros(3),')],
            "support_kind": "CONSUMER_SOURCE",
        },
        "C_consumer_C": {
            "aspect": "position_fields",
            "interpretation": "PASS_THROUGH_MARK_INVALID",
            "declared": "emit the real position with valid=(fix>=3)",
            "support": [cite("csia/runtime/ulog_source.py", "188-189",
                             '"pos": pos, "vel": vel, "valid": bool(fix[i] >= 3)}))')],
            "support_kind": "CONSUMER_SOURCE",
        },
    },
}

# ===========================================================================
# CASE 3 -- item 17. CHOSEN BEFORE ANY DOWNSTREAM OUTCOME WAS INSPECTED.
# ===========================================================================
THIRD_CASE_RATIONALE = """
Item 17 offers the magnetometer all-zero sentinel OR the estimator-health
signal, and requires the choice to be made and justified before looking at
the downstream outcome.

CHOSEN: magnetometer.

Reason, recorded in advance: the estimator-health channel is absent from
CORE_MAP entirely (research/evidence_semantics/CROSS_SENSOR_AUDIT.csv), so it
cannot cross the core boundary and its downstream consequence is known to be
empty BEFORE any measurement. Choosing it would guarantee a null result by
construction and would test nothing about authority conflict. The
magnetometer does cross the boundary, so its downstream consequence is an
open question at the time of choosing.

This rationale is committed with the artifact and the estimator-health case
is left as a documented structural row only.
"""

MAG = {
    "case": "mag.all_zero_triple",
    "raw_state": "SCALED_IMU.xmag == ymag == zmag == 0",
    "authorities": {
        "C_spec": {
            "aspect": "value_semantics",
            "interpretation": SILENT,
            "declared": "the schema defines no sentinel for the magnetometer "
                        "axes and says nothing about an all-zero triple",
            "support": [cite("common.xml", "SCALED_IMU.xmag",
                             "X Magnetic field", base=MAVLINK)],
            "support_kind": "PROTOCOL_SCHEMA",
            "note": "no `invalid=` attribute on xmag/ymag/zmag.",
        },
        "C_consumer_A": {
            "aspect": "value_semantics",
            "interpretation": "TREAT_AS_ABSENT_SILENTLY",
            "declared": "an all-zero triple is absence; nothing is stored and "
                        "nothing is recorded",
            "support": [cite("csia/aircraft/adapters/ardupilot.py", 146,
                             "if any(mag) and all(finite(x) for x in mag):")],
            "support_kind": "CONSUMER_SOURCE",
            "note": "there is no else branch: no _put AND no "
                    "_reject_sentinel, so not even a reason is recorded.",
        },
        "C_consumer_B": {
            "aspect": "value_semantics",
            "interpretation": "TREAT_AS_ABSENT_SILENTLY",
            "declared": "same test, same silence",
            "support": [cite("csia/runtime/plugins.py", 140,
                             'if sensor == "imu0" and (msg.xmag or msg.ymag or msg.zmag):')],
            "support_kind": "CONSUMER_SOURCE",
        },
        "C_consumer_C": {
            "aspect": "value_semantics",
            "interpretation": "LITERAL_ZERO_FIELD",
            "declared": "emit the zero vector as a valid magnetic field",
            "support": [cite("csia/runtime/ulog_source.py", "162-163",
                             '{"field_ut": _frd_to_zup(f), "valid": True}))')],
            "support_kind": "CONSUMER_SOURCE",
        },
    },
}

CASES = [BATTERY, GNSS, MAG]


def main() -> int:
    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)
    rows, bad = [], []
    for case in CASES:
        for name, a in case["authorities"].items():
            oks = []
            for c in a["support"]:
                ok, why = verify(c)
                oks.append(ok)
                if not ok:
                    bad.append((case["case"], name, c["locator"], why))
            rows.append({
                "case": case["case"], "raw_state": case["raw_state"],
                "authority": name,
                "interpretation": a["interpretation"],
                "declared_meaning": a["declared"],
                "support_kind": a["support_kind"],
                "citations": " ; ".join(c["locator"] for c in a["support"]),
                "aspect": a.get("aspect", "value_semantics"),
                "citations_verified": all(oks),
                "note": a.get("note", ""),
            })

    with open(os.path.join(_HERE, "AUTHORITY_TABLE.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(_HERE, "results", "AUTHORITIES.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "AUTHORITIES",
                   "third_case_rationale": THIRD_CASE_RATIONALE.strip(),
                   "silent_marker": SILENT,
                   "unverified_citations": bad,
                   "rows": rows}, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  authorities: {len(rows)} rows across {len(CASES)} cases")
    for r in rows:
        flag = "" if r["citations_verified"] else "  <-- CITATION FAILED"
        print(f"    {r['case']:<32} {r['authority']:<26} "
              f"{r['interpretation']}{flag}")
    if bad:
        print(f"\n  {len(bad)} CITATIONS DID NOT RESOLVE:")
        for b in bad:
            print(f"    {b}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
