"""Report the hardware configuration gate's status, and touch nothing.

    python tools/hardware/hardware_gate_status.py
    python tools/hardware/hardware_gate_status.py --mode FAKE
    python tools/hardware/hardware_gate_status.py --json

Read-only. It opens no port, writes no register and creates no run. With no
--mode it classifies the static configuration; with --mode it reports what
that mode would resolve to.

EXIT CODES, so a script can branch without parsing prose:
    0  VERIFIED_STATIC_CONFIGURATION, FAKE_DRIVER or REPLAY
    3  BLOCKED_CONFIGURATION
    4  LIVE_HARDWARE_NOT_REACHABLE

3 and 4 differ on purpose. 3 says a constant needs a document; 4 says a device
needs plugging in. A single "live failed" code would let the first be read as
the second, and they are not the same day's work.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import csia_hardware_gate as hw        # noqa: E402
from csia_hardware_gate import registry as reg    # noqa: E402

EXIT = {hw.VERIFIED_STATIC_CONFIGURATION: 0, hw.FAKE_DRIVER: 0, hw.REPLAY: 0,
        hw.BLOCKED_CONFIGURATION: 3, hw.LIVE_HARDWARE_NOT_REACHABLE: 4}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=hw.MODES, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    decision = (hw.resolve(args.mode) if args.mode
                else hw.static_configuration_status())

    try:
        summary = reg.summarise()
    except reg.RegistryMalformed as error:
        summary = {"error": str(error)}

    report = {"status": decision.status, "mode": decision.mode,
              "hardware_touched": decision.hardware_touched,
              "hardware_validated": False,
              "detail": decision.detail,
              "registry": summary,
              "what_this_is_not": (
                  "No status here is evidence that any device behaved. "
                  "VERIFIED_STATIC_CONFIGURATION describes files on disk. "
                  "FAKE_DRIVER and REPLAY describe synthetic or recorded "
                  "data. None of them is a hardware validation.")}

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"STATUS: {decision.status}")
        print(f"  mode              {decision.mode}")
        print(f"  hardware touched  {decision.hardware_touched}")
        print(f"  hardware validated False  (always; there is no path to True)")
        print(f"  {decision.detail}")
        if "by_status" in summary:
            print(f"\n  governed constants: {summary['total']}")
            for status, count in sorted(summary["by_status"].items()):
                print(f"    {status:12s} {count:3d}")
        for c in decision.blocking_constants:
            cited = c.declared_in or "nowhere"
            print(f"    [{c.status:10s}] {c.name}  ({c.units}; value in "
                  f"{cited})")
            for problem in c.problems:
                print(f"                 problem: {problem}")

    return EXIT.get(decision.status, 1)


if __name__ == "__main__":
    raise SystemExit(main())
