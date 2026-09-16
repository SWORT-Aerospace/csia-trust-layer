"""Check the E2M sensor inventory, and refuse claims it cannot support.

    python tools/hardware/validate_inventory.py

Two states -- `DISCOVERED_ON_BUS` and `MEASUREMENT_VERIFIED` -- are assertions
about a physical event. They are rejected unless `evidence_run` names a run
manifest that exists on disk and is marked complete, because a YAML file
cannot otherwise be distinguished from an intention.
"""
from __future__ import annotations

import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "hardware/inventory/e2m_sensors.yaml"

STATES = ("PLANNED", "ORDERED", "OWNER_REPORTED_ON_HAND", "VISUALLY_IDENTIFIED",
          "DATASHEET_VERIFIED", "ELECTRICALLY_VERIFIED", "DISCOVERED_ON_BUS",
          "MEASUREMENT_VERIFIED")

#: States that assert a physical event happened and therefore need an artifact.
NEED_EVIDENCE = ("DISCOVERED_ON_BUS", "MEASUREMENT_VERIFIED")

REQUIRED = ("logical_id", "manufacturer", "part_number", "datasheet_path",
            "i2c_address", "supply_voltage_v", "logic_voltage_v",
            "measurement_units", "channel", "state")


def validate(document: dict, root: pathlib.Path = ROOT) -> list:
    problems = []
    sensors = document.get("sensors") or []
    if not isinstance(sensors, list):
        return ["`sensors` must be a list"]

    seen_channels = {}
    seen_ids = set()
    for index, sensor in enumerate(sensors):
        where = sensor.get("logical_id") or f"sensors[{index}]"
        state = sensor.get("state")
        if state not in STATES:
            problems.append(f"{where}: state {state!r} is not one of {STATES}")

        for field in REQUIRED:
            if sensor.get(field) in (None, ""):
                problems.append(f"{where}: {field} is unset")

        if state in NEED_EVIDENCE:
            run = sensor.get("evidence_run")
            if not run:
                problems.append(
                    f"{where}: state {state} asserts a physical event but "
                    f"evidence_run is unset. That state may not be claimed "
                    f"from a document alone")
            else:
                path = root / run
                if not path.is_file():
                    problems.append(
                        f"{where}: evidence_run {run} does not exist")
                else:
                    try:
                        manifest = json.loads(path.read_text())
                    except json.JSONDecodeError as error:
                        problems.append(f"{where}: {run} is not JSON: {error}")
                        continue
                    if not manifest.get("complete"):
                        problems.append(
                            f"{where}: evidence_run {run} is marked "
                            f"incomplete; an interrupted run does not "
                            f"establish {state}")
                    if manifest.get("device") == "FAKE":
                        problems.append(
                            f"{where}: evidence_run {run} is a FAKE run. A "
                            f"synthetic run can never establish {state}")

        channel = sensor.get("channel")
        if channel is not None:
            if not isinstance(channel, int) or not 0 <= channel <= 7:
                problems.append(f"{where}: channel {channel!r} outside 0..7")
            elif channel in seen_channels:
                problems.append(
                    f"{where}: channel {channel} already used by "
                    f"{seen_channels[channel]}")
            else:
                seen_channels[channel] = where

        logical = sensor.get("logical_id")
        if logical:
            if logical in seen_ids:
                problems.append(f"{where}: duplicate logical_id")
            seen_ids.add(logical)
    return problems


def main() -> int:
    if not INVENTORY.is_file():
        print(f"missing {INVENTORY.relative_to(ROOT)}", file=sys.stderr)
        return 1
    document = yaml.safe_load(INVENTORY.read_text()) or {}
    sensors = document.get("sensors") or []
    problems = validate(document)

    if problems:
        print(f"{len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if not sensors:
        print("inventory is EMPTY and valid.")
        print("Gate 2 is OPEN: no sensor is declared, so no real driver may "
              "be written and E2M-1 cannot run.")
        return 0
    print(f"inventory valid: {len(sensors)} sensor(s)")
    for sensor in sensors:
        print(f"  {sensor['logical_id']:16s} ch{sensor['channel']} "
              f"{sensor['part_number']:16s} {sensor['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
