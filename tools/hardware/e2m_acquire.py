"""Run one E2M acquisition and close a manifest over it.

    # E2M-0, runnable today with no hardware at all
    python tools/hardware/e2m_acquire.py --fake --sweeps 20 \
        --run-id e2m0-001 --out runs/

    # E2M-1, only after the gates pass and hardware is in front of you
    python tools/hardware/e2m_acquire.py --port /dev/ttyACM0 --baud 115200 \
        --run-id e2m1-001 --out runs/

`--fake` and `--port` are mutually exclusive and the manifest records which was
used. A fake run writes ``device: "FAKE"`` and can never be reported as a bench
run; `tools/hardware/e2m_report.py` refuses to describe it as one.

`--port` additionally passes through the hardware configuration gate
(`csia_hardware_gate`) BEFORE the port is opened. If any governed constant is
UNVERIFIED or MISSING the command exits 3 with a typed
HardwareConfigurationBlocked report and opens nothing. It never falls back to
`--fake`: choosing a different run on the operator's behalf is how a synthetic
result comes to be filed as a bench result.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_e2m.fake_controller import (FAKE_DEVICE, FakeController,  # noqa: E402
                                      default_bench)
from csia_e2m.logging import RunLogger                              # noqa: E402
from csia_e2m.transport import (FakeTransport, SerialTransport,     # noqa: E402
                                available_ports)
from csia_hardware_gate import (HardwareConfigurationBlocked,  # noqa: E402
                                require_live_hardware_permitted)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fake", action="store_true",
                        help="synthetic controller; NOT a physical run")
    source.add_argument("--port", help="serial device, e.g. /dev/ttyACM0")
    source.add_argument("--list-ports", action="store_true",
                        help="enumerate serial devices and exit")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--sweeps", type=int, default=10)
    parser.add_argument("--sensors", type=int, default=3)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "runs")
    parser.add_argument("--experiment", default=None)
    parser.add_argument("--no-verify-readback", action="store_true",
                        help="fake only: omit the register readback, which is "
                             "what makes a misattribution invisible")
    args = parser.parse_args(argv)

    if args.list_ports:
        ports = available_ports()
        print("\n".join(ports) if ports else "no serial ports enumerated")
        return 0

    if not args.run_id:
        parser.error("--run-id is required; runs are never overwritten")

    experiment = args.experiment or ("E2M-0" if args.fake else "E2M-1")
    if args.fake:
        controller = FakeController(
            sensors=default_bench(args.sensors),
            verify_readback=not args.no_verify_readback)
        transport = FakeTransport(list(controller.frames(args.sweeps)))
    else:
        # THE GATE. Before the port is opened, before any byte is written:
        # every governed hardware constant must be VERIFIED against a hashed
        # primary document. If one is not, this raises and the run ends. It
        # does NOT fall back to --fake; a live request that quietly became a
        # synthetic run would produce a manifest indistinguishable from a
        # bench run, which is the failure the whole policy exists to prevent.
        try:
            require_live_hardware_permitted(
                f"open {args.port} and drive the E2M bench")
        except HardwareConfigurationBlocked as blocked:
            print(json.dumps(blocked.as_dict(), indent=1, sort_keys=True))
            print(f"\n{blocked}", file=sys.stderr)
            return 3
        transport = SerialTransport(args.port, args.baud)
        transport.open()

    log_path = pathlib.Path(args.out) / f"{args.run_id}.jsonl"
    logger = RunLogger(path=log_path, run_id=args.run_id,
                       device=transport.device, baud=transport.baud,
                       experiment=experiment,
                       notes="synthetic controller; not a physical run"
                       if args.fake else "")
    logger.open()
    interrupted = True
    try:
        for line in transport.lines():
            logger.ingest(line)
        interrupted = False
    finally:
        # An interrupted run is closed and MARKED interrupted rather than
        # left open, so a half-run is visible as one instead of looking like
        # a file somebody forgot to finish.
        manifest = logger.close(interrupted=interrupted)
        if isinstance(transport, SerialTransport):
            transport.close()

    print(json.dumps(manifest, indent=1, sort_keys=True))
    if manifest and manifest["device"] == FAKE_DEVICE:
        print("\nNOTE: device=FAKE. This is a synthetic run and is NOT "
              "evidence about any hardware.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
