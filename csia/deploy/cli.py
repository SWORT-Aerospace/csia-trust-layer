"""`csia-shadow` — the companion-computer entry point.

Deterministic startup, monotonic clock, explicit config, no command path.

    csia-shadow --config configs/vehicle/example_quad.yaml

The mode comes from `CSIA_MODE` (default SHADOW) or `--mode`. An unrecognised
value is a hard error: silently downgrading a typo to SHADOW would be safe,
silently upgrading one would not, so neither is allowed.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

import yaml

from ..aircraft.qualification import (CONTEXT_HARDWARE, CONTEXT_SIMULATOR,
                                      SemanticContract)
from ..aircraft.sample import Quality
from .shadow import Mode, ShadowConfig, ShadowRunner, env_mode

log = logging.getLogger("csia.shadow")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def build_contract(cfg: dict, context: str) -> SemanticContract:
    """Apply this vehicle's channel overrides, each with its stated reason."""
    contract = SemanticContract(context=context)
    for ov in cfg.get("channel_overrides") or []:
        contract.override(ov["channel"], Quality(ov["quality"]),
                          bool(ov["may_use"]), ov.get("reason", ""))
        log.warning("channel override: %s -> %s (%s)", ov["channel"],
                    ov["quality"], ov.get("reason", "")[:80])
    return contract


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="csia-shadow")
    ap.add_argument("--config", default="configs/vehicle/example_quad.yaml")
    ap.add_argument("--mode", default=None,
                    help="SHADOW or ADVISORY; overrides CSIA_MODE")
    ap.add_argument("--connection", default=None)
    ap.add_argument("--platform", default=None)
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--context", choices=[CONTEXT_SIMULATOR,
                                          CONTEXT_HARDWARE],
                    default=CONTEXT_HARDWARE,
                    help="qualification context; HARDWARE on a real vehicle")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    cfg = load_config(args.config)
    csia_cfg = cfg.get("csia", {})
    link = cfg.get("link", {})

    mode = Mode(args.mode.upper()) if args.mode else env_mode()
    if mode.may_command:                                # pragma: no cover
        raise SystemExit("refusing to start: mode claims command authority")

    connection = args.connection or link.get("connection")
    if not connection and link.get("transport") == "serial":
        connection = f"{link.get('device')},{link.get('baud', 921600)}"
    if not connection:
        connection = "udp:0.0.0.0:14550"

    run_cfg = ShadowConfig(
        platform=(args.platform or cfg.get("autopilot", {}).get("stack",
                                                                "ardupilot")),
        connection=connection,
        mode=mode,
        tick_hz=float(csia_cfg.get("tick_hz", 25.0)),
        log_dir=args.log_dir or csia_cfg.get("log_dir", "logs/shadow"),
        profile=args.profile or csia_cfg.get("profile",
                                             "FIELD_DERIVED_NOISE"),
        field_mode=bool(csia_cfg.get("field_mode", True)),
        max_runtime_s=args.max_seconds,
        watchdog_timeout_s=float(csia_cfg.get("watchdog_timeout_s", 5.0)),
        autopilot_version=cfg.get("autopilot", {}).get("firmware", "unknown"),
        vehicle_config=cfg,
        log_max_bytes=int(csia_cfg.get("log_max_bytes", 64 * 1024 * 1024)),
    )

    runner = ShadowRunner(run_cfg)
    runner.adapter.contract = build_contract(cfg, args.context)

    def stop(_sig, _frm):
        log.info("stopping on signal")
        runner.stop()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    log.info("csia-shadow: platform=%s mode=%s connection=%s profile=%s",
             run_cfg.platform, mode.value, connection, run_cfg.profile)
    header = runner.run()
    log.info("flight %s complete: %s", header.flight_id, runner.stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
