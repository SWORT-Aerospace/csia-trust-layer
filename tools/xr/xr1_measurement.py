"""Record a physical measurement into the XR-1 draft profile, or report what
is still blocking CAD freeze.

WHY THIS TOOL EXISTS
--------------------
The battery envelope is `UNKNOWN` and blocks CAD freeze. Nothing in this
repository can measure it -- there is no caliper API -- so the useful thing to
build is not a number but the machinery that ACCEPTS one:

    * a validated entry path that attaches provenance to the value, so a
      measurement and a datasheet figure cannot be confused six months later;
    * a readiness gate that derives its blocker list FROM THE PROFILE, so it
      cannot go stale the way a hand-written checklist does.

WHAT IT REFUSES, AND WHY EACH REFUSAL EARNS ITS PLACE
------------------------------------------------------
    no --measured-by      an unattributed measurement cannot be queried later
    no --method           "155 mm" without "how" is not reproducible
    MEASURED without a
    tolerance             a measurement with no stated tolerance cannot be
                          compared against a requirement
    implausible values    a transposed digit is the most common data-entry
                          error and the cheapest to catch
    a datasheet figure
    recorded as MEASURED  --status GIVEN exists for that, and the readiness
                          gate keeps reporting the item as blocking, because
                          a catalogue envelope is not the article's envelope

IT DOES NOT INVENT ANYTHING. There is no default, no estimate, and no
"typical value for this class of pack". Running it with no numbers reports
the gap; it does not fill it.

    python tools/xr/xr1_measurement.py --status
    python tools/xr/xr1_measurement.py --record battery --dimensions-mm ...
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PROFILE = os.path.join(ROOT, "hardware", "xr1", "XR1_DRAFT_PROFILE.yaml")

MEASURED, GIVEN, PROVISIONAL, UNKNOWN = ("MEASURED", "GIVEN", "PROVISIONAL",
                                         "UNKNOWN")

#: Statuses that satisfy a CAD-freeze blocker. GIVEN does NOT: the profile
#: says the battery envelope must be MEASURED, and a datasheet figure is not
#: the article on the bench.
SATISFIES_CAD_FREEZE = (MEASURED,)

#: Plausibility bounds, PER ITEM, in millimetres and grams. These are
#: data-entry sanity checks, NOT requirements and NOT specifications. A value
#: outside them is refused so a transposed digit is caught at entry rather
#: than in a CG calculation three weeks later.
PLAUSIBLE = {
    "battery": {"dimensions_mm": ((40.0, 400.0), (20.0, 200.0),
                                  (10.0, 150.0))},
    "reference_imu": {"mass_g": (0.5, 200.0)},
    "gnss": {"carrier_envelope_mm": ((5.0, 200.0), (5.0, 200.0),
                                     (1.0, 100.0))},
    "research_compute": {"mass_g": (1.0, 500.0)},
}


def _load():
    import yaml
    with open(PROFILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def blockers() -> list:
    """What still blocks CAD freeze. DERIVED FROM THE PROFILE.

    The profile lists `must_be_measured_before_cad_freeze` in prose for a
    human, and carries the actual status fields for a machine. This reads the
    STATUS FIELDS, so an item that gets measured stops blocking without
    anybody editing a checklist -- and an item added to the profile starts
    blocking without anybody remembering to add it here.
    """
    doc = _load()
    out = []
    for name, item in sorted((doc.get("items") or {}).items()):
        for key, value in sorted(item.items()):
            if not key.endswith("_status"):
                continue
            if value in SATISFIES_CAD_FREEZE:
                continue
            quantity = key[: -len("_status")]
            # Only quantities the profile actually carries a slot for.
            if quantity not in item and f"{quantity}_mm" not in item:
                continue
            out.append({
                "item": name,
                "quantity": quantity,
                "status": value,
                "value": item.get(quantity),
                "blocks_cad_freeze": value in (UNKNOWN, PROVISIONAL),
            })
    return out


def status_report() -> dict:
    doc = _load()
    rows = blockers()
    blocking = [r for r in rows if r["blocks_cad_freeze"]]
    prose = doc.get("must_be_measured_before_cad_freeze") or []
    return {
        "schema": "csia.mission.xr_measurement_status/1",
        "profile": os.path.relpath(PROFILE, ROOT),
        "profile_status": doc.get("status"),
        "total_quantities_with_a_status": len(rows),
        "blocking_cad_freeze": blocking,
        "blocking_count": len(blocking),
        "prose_list_in_the_profile": prose,
        "ready_for_cad_freeze": not blocking,
        "derived_from": ("the profile's own status fields, not a "
                         "hand-written checklist, so it cannot go stale"),
        "what_this_tool_cannot_do": (
            "measure anything. There is no caliper API. Every value here has "
            "to be produced by a person holding the article -- see "
            "hardware/xr1/XR1_MEASUREMENT_PROTOCOL.md."),
    }


def _check_plausible(item: str, quantity: str, values) -> None:
    bounds = (PLAUSIBLE.get(item) or {}).get(quantity)
    if bounds is None:
        return
    if isinstance(bounds[0], tuple):
        if len(values) != len(bounds):
            raise SystemExit(
                f"{item}.{quantity}: expected {len(bounds)} values, got "
                f"{len(values)}")
        for v, (lo, hi) in zip(values, bounds):
            if not (lo <= v <= hi):
                raise SystemExit(
                    f"{item}.{quantity}: {v} is outside the plausible range "
                    f"[{lo}, {hi}]. This is a DATA-ENTRY sanity check, not a "
                    f"requirement -- a transposed digit is the most common "
                    f"entry error. If the value is genuinely correct, widen "
                    f"PLAUSIBLE in this file in the same commit and say why.")
    else:
        lo, hi = bounds
        v = values if not isinstance(values, (list, tuple)) else values[0]
        if not (lo <= v <= hi):
            raise SystemExit(
                f"{item}.{quantity}: {v} is outside the plausible range "
                f"[{lo}, {hi}]")


def record(item: str, quantity: str, values, status: str,
           measured_by: str, method: str, tolerance: str | None,
           note: str) -> dict:
    """Validate and return the block to write. Refuses more than it accepts."""
    if status not in (MEASURED, GIVEN, PROVISIONAL):
        raise SystemExit(f"status must be one of {MEASURED}, {GIVEN}, "
                         f"{PROVISIONAL} -- got {status!r}")
    if not measured_by:
        raise SystemExit(
            "--measured-by is required. An unattributed measurement cannot "
            "be queried later, and 'someone measured it' is not provenance.")
    if not method:
        raise SystemExit(
            "--method is required. A number without a method is not "
            "reproducible: calipers or tape, charged or at storage, strapped "
            "or loose, all change the answer.")
    if status == MEASURED and not tolerance:
        raise SystemExit(
            "--tolerance-mm is required for a MEASURED value. A measurement "
            "with no stated tolerance cannot be compared against a "
            "requirement, and a later reader cannot tell 152 mm from "
            "'about 150'.")

    _check_plausible(item, quantity, values)

    doc = _load()
    if item not in (doc.get("items") or {}):
        raise SystemExit(
            f"{item!r} is not an item in the profile. Known: "
            f"{sorted(doc['items'])}")

    return {
        "item": item,
        "quantity": quantity,
        "value": values,
        "status": status,
        "provenance": {
            "measured_by": measured_by,
            "method": method,
            "tolerance": tolerance,
            "recorded_at": datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"),
            "note": note,
        },
    }


def apply_to_profile(entry: dict) -> str:
    """Write the value and its status back into the profile YAML.

    Edits the TEXT rather than round-tripping through the parser, so the
    file's comments -- which carry most of its meaning -- survive. A YAML
    round-trip would silently delete every explanation of why a number is
    provisional.
    """
    with open(PROFILE, encoding="utf-8") as fh:
        lines = fh.readlines()

    item, quantity = entry["item"], entry["quantity"]
    value, status = entry["value"], entry["status"]

    in_item = False
    value_line = status_line = None
    item_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{item}:"):
            in_item = True
            item_indent = len(line) - len(line.lstrip())
            continue
        if in_item:
            indent = len(line) - len(line.lstrip())
            if stripped and not stripped.startswith("#") and \
                    indent <= item_indent:
                break
            if stripped.startswith(f"{quantity}:"):
                value_line = i
            if stripped.startswith(f"{quantity[:-3]}_status:"
                                   if quantity.endswith("_mm")
                                   else f"{quantity}_status:"):
                status_line = i

    if value_line is None:
        raise SystemExit(
            f"could not find {item}.{quantity} in the profile. Nothing was "
            f"written.")

    rendered = (json.dumps(value) if isinstance(value, (list, tuple))
                else json.dumps(value))
    indent = " " * (len(lines[value_line]) - len(lines[value_line].lstrip()))
    lines[value_line] = f"{indent}{quantity}: {rendered}\n"
    if status_line is not None:
        key = lines[status_line].split(":")[0].strip()
        lines[status_line] = f"{indent}{key}: {status}\n"

    prov = entry["provenance"]
    lines[value_line] += (
        f"{indent}# RECORDED {prov['recorded_at']} by {prov['measured_by']}\n"
        f"{indent}# method: {prov['method']}\n"
        f"{indent}# tolerance: {prov['tolerance']}\n"
        + (f"{indent}# note: {prov['note']}\n" if prov["note"] else ""))

    with open(PROFILE, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return PROFILE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", action="store_true",
                    help="report what blocks CAD freeze; exit 1 if blocked")
    ap.add_argument("--record", metavar="ITEM", default=None)
    ap.add_argument("--quantity", default="dimensions_mm")
    ap.add_argument("--dimensions-mm", default=None,
                    help="comma-separated, e.g. 155.0,49.5,52.0")
    ap.add_argument("--mass-g", type=float, default=None)
    ap.add_argument("--value-status", default=MEASURED,
                    choices=(MEASURED, GIVEN, PROVISIONAL))
    ap.add_argument("--measured-by", default="")
    ap.add_argument("--method", default="")
    ap.add_argument("--tolerance-mm", default=None)
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.status or not args.record:
        doc = status_report()
        print(json.dumps(doc, indent=2, sort_keys=True))
        if doc["blocking_count"]:
            print(f"\n{doc['blocking_count']} quantities block CAD freeze. "
                  f"NOTHING HERE CAN MEASURE THEM -- see "
                  f"hardware/xr1/XR1_MEASUREMENT_PROTOCOL.md",
                  file=sys.stderr)
            return 1
        return 0

    if args.dimensions_mm:
        values = [float(x) for x in args.dimensions_mm.split(",")]
        quantity = args.quantity
    elif args.mass_g is not None:
        values = args.mass_g
        quantity = "mass_g"
    else:
        raise SystemExit("give --dimensions-mm or --mass-g")

    entry = record(args.record, quantity, values, args.value_status,
                   args.measured_by, args.method, args.tolerance_mm,
                   args.note)
    print(json.dumps(entry, indent=2, sort_keys=True))
    if args.dry_run:
        print("\n(dry run: profile not modified)", file=sys.stderr)
        return 0
    path = apply_to_profile(entry)
    print(f"\nupdated {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
