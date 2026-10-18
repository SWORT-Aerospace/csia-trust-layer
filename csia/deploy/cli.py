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



def self_test(runner, seconds: float) -> int:
    """Pre-flight: does telemetry actually arrive on this link?

    Exists because a shadow monitor CANNOT ask an autopilot to stream --
    requesting is transmitting, and the guard denies it. If the vehicle's
    SR*_ parameters are not set for this port, CSIA receives one heartbeat and
    nothing else, forever, with no error anywhere. That failure is invisible
    in the air and obvious here.

    Exit 0 only if at least one channel reached the diagnostic core.
    """
    import time as _t
    runner.connect()
    log.info("self-test: listening %.0f s on %s", seconds,
             runner.cfg.connection)
    t0 = _t.monotonic()
    while _t.monotonic() - t0 < seconds:
        try:
            m = runner.conn.recv_match(blocking=True, timeout=1.0)
        except Exception as exc:                        # pragma: no cover
            log.warning("receive error: %s", exc)
            continue
        if m is not None:
            runner.adapter.ingest(m)

    sample = runner.adapter.sample(t_mono=_t.monotonic() - t0)
    usable = sample.usable_channels()
    blocked = sample.blocked_channels()
    counters = runner.adapter.counters

    print(f"\n=== self-test over {seconds:.0f} s on {runner.cfg.connection}")
    print(f"    messages seen:   {counters['messages']}")
    print(f"    channels mapped: {counters['mapped']}")
    print(f"    USABLE channels: {len(usable)}")
    for cv in sorted(usable, key=lambda c: c.channel):
        print(f"        {cv.channel:26s} age {cv.age_s:.3f}s")
    absent = [cv for cv in sample.channels()
              if not cv.usable and cv not in blocked]
    if absent:
        print(f"    NOT ARRIVING ({len(absent)}):")
        for cv in sorted(absent, key=lambda c: c.channel):
            print(f"        {cv.channel:26s} "
                  f"{cv.missing.value if cv.missing else '-'}")
    if blocked:
        print(f"    blocked by contract ({len(blocked)}): "
              + ", ".join(sorted(cv.channel for cv in blocked)))
    unmapped = runner.adapter.unmapped_types()
    if unmapped:
        print(f"    unmapped message types: {sorted(unmapped)}")

    if not usable:
        print("\nSELF-TEST: FAIL -- no channel reached the diagnostic core.")
        print("  Most likely the vehicle is not streaming on this port. CSIA "
              "cannot request streams (that would be transmitting).")
        print("  Set SR*_ parameters for this serial port on the flight "
              "controller. See docs/deployment/AIRCRAFT_INTEGRATION.md 2.0.")
        return 1
    print(f"\nSELF-TEST: PASS -- {len(usable)} channel(s) usable.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="csia-shadow",
        description="Run the CSIA trust layer alongside a vehicle as a "
                    "companion-computer observer. It reads telemetry and "
                    "writes a flight log; it has NO command path to the "
                    "autopilot in any mode.",
        epilog="Run --self-test before a shadow flight: it connects, listens "
               "briefly and reports which channels actually arrive. Zero "
               "usable channels means the vehicle is not configured to "
               "stream, and the run would produce an empty log. Mode comes "
               "from CSIA_MODE (default SHADOW) unless --mode overrides it; "
               "an unrecognised value is a hard error rather than a silent "
               "downgrade.")
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
    ap.add_argument("--self-test", action="store_true",
                    help="connect, listen briefly, report which channels "
                         "actually arrive, then exit. Run this BEFORE a "
                         "shadow flight: zero usable channels means the "
                         "vehicle is not configured to stream.")
    ap.add_argument("--self-test-seconds", type=float, default=10.0)
    ap.add_argument("--data-loss-supervision", action="store_true",
                    help="add the SR-003 loss-of-data rule for the seven "
                         "sensors the frozen failsafe does not cover on "
                         "ABSENCE (it covers GPS only). The overlay can "
                         "only RAISE the level, never lower it. OFF by "
                         "default: shadow logs are evidence, and the two "
                         "policies are not comparable, so the header "
                         "records which was in force.")
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
        data_loss_supervision=bool(
            args.data_loss_supervision
            or csia_cfg.get("data_loss_supervision", False)),
    )

    runner = ShadowRunner(run_cfg)
    runner.adapter.contract = build_contract(cfg, args.context)

    def stop(_sig, _frm):
        log.info("stopping on signal")
        runner.stop()

    if args.self_test:
        return self_test(runner, args.self_test_seconds)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    log.info("csia-shadow: platform=%s mode=%s connection=%s profile=%s",
             run_cfg.platform, mode.value, connection, run_cfg.profile)
    header = runner.run()
    log.info("flight %s complete: %s", header.flight_id, runner.stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
