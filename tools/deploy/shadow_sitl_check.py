"""Run the SHADOW stack end to end against a live autopilot.

Everything else in the deployment tree is tested against a `FakeConnection`.
This is the first thing that puts the whole chain on real telemetry:

    ArduPilot/PX4 SITL
      -> pymavlink UDP/TCP
      -> ReadOnlyMavlinkConnection   (real socket, real transmit denial)
      -> PlatformAdapter             (real messages, real units, real staleness)
      -> AircraftSample
      -> OnlineTrustLayer            (FROZEN v1)
      -> FailsafePolicy              (recommendations only)
      -> FlightLog                   (a real file on disk)

It answers two questions no unit test can:

  1. Does the pipeline survive a live stream at all -- rates, gaps, message
     types nobody anticipated, a flight controller that reboots?
  2. Does it hold R13 (<= 2 ms per tick) THROUGH THE NEW STACK? The 297-356
     us/tick figure in the freeze document is the OLD ingestion path. The
     adapter and the qualification layer add per-tick work that has never
     been measured.

Latency is reported as a distribution, not a mean. A mean hides the tail, and
the tail is what misses a deadline.

  python tools/deploy/shadow_sitl_check.py --platform ardupilot --seconds 30
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import statistics
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.deploy.guard import CommandAuthorityError          # noqa: E402
from csia.deploy.shadow import Mode, ShadowConfig, ShadowRunner  # noqa: E402
from csia.simulation.rigs import (LAUNCHERS, PASSIVE_LINKS, connect,  # noqa: E402
                                  fly)

R13_BUDGET_US = 2000.0


def summarise(latencies):
    if not latencies:
        return {}
    s = sorted(latencies)

    def pct(p):
        return s[min(len(s) - 1, int(len(s) * p))]

    return {
        "n": len(s),
        "min_us": round(s[0], 2),
        "median_us": round(statistics.median(s), 2),
        "mean_us": round(statistics.fmean(s), 2),
        "p95_us": round(pct(0.95), 2),
        "p99_us": round(pct(0.99), 2),
        "max_us": round(s[-1], 2),
        "budget_us": R13_BUDGET_US,
        "over_budget": sum(1 for x in s if x > R13_BUDGET_US),
        "worst_headroom_x": round(R13_BUDGET_US / s[-1], 2) if s[-1] else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=sorted(LAUNCHERS),
                    default="ardupilot")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--speedup", type=int, default=1)
    ap.add_argument("--fly", action="store_true",
                    help="arm and climb first, so the stack sees a moving "
                         "airframe rather than a parked one")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    workdir = os.path.join(ROOT, "build", f"shadow-{args.platform}")
    logdir = os.path.join(ROOT, "logs", f"shadow-sitl-{args.platform}")
    proc, conn_str = LAUNCHERS[args.platform](workdir, args.speedup)
    print(f"=== {args.platform} SITL launched (pid {proc.pid}) -> {conn_str}")

    result = {"platform": args.platform, "seconds": args.seconds}
    try:
        # The rig holds the COMMAND link (SERIAL0) for the whole run. It is
        # what asks the autopilot to stream, because a shadow monitor cannot:
        # request_data_stream_send is a transmit, and the guard denies it. On
        # a real aircraft that request comes from the GCS or from the FC's own
        # SR*_ parameters -- see docs/deployment/AIRCRAFT_INTEGRATION.md.
        # It is NOT closed early: the streams stop when the requester leaves.
        rig_conn = connect(conn_str, args.platform)

        # NO stream-rate configuration happens here, and that is the finding.
        #
        # This block used to write SR1_* parameters and print "rig set SR1_*
        # stream rates (the documented install step)". Those parameters DO NOT
        # EXIST on ArduCopter 4.8: a full dump shows 1409 parameters whose only
        # SR* group is SRTL_* (SmartRTL), and the GCS group is prefixed MAV
        # (ArduCopter/Parameters.cpp:591) holding no stream rates at all
        # (GCS.cpp:43-75). A parameter write to an unknown name returns no
        # error, so the harness asserted success while writing into the void
        # for four consecutive runs.
        #
        # Stream rates on Copter are per-link runtime state set by a transmit
        # on that link, and they do not persist (GCS.h:537,
        # persist_streamrates() == false). The rig cannot configure SERIAL1
        # from SERIAL0, and CSIA cannot configure its own link without
        # transmitting -- which SHADOW mode forbids by construction.
        #
        # So this harness CANNOT currently produce a valid R13 measurement on
        # a dedicated passive link. That is a real deployment constraint, not
        # a harness bug, and it is written up in
        # docs/deployment/AIRCRAFT_INTEGRATION.md 2.0. The positive control
        # below reports INVALID_MEASUREMENT rather than a number, which is the
        # correct outcome until the telemetry-tee arrangement is built.
        print("=== rig holds the command link")
        if args.fly:
            print("=== rig: arming and climbing (rig authority, not CSIA)")
            ev = fly(rig_conn, args.platform)
            print(f"    armed={ev['armed']} climbed={ev['climbed_m']:.2f} m")
            result["rig_flight"] = {"armed": ev["armed"],
                                    "climbed_m": round(ev["climbed_m"], 2)}

        from pymavlink import mavutil

        passive = PASSIVE_LINKS[args.platform]

        def factory():
            # A SEPARATE, passive link. Not the rig's command link.
            c = mavutil.mavlink_connection(passive)
            c.wait_heartbeat(timeout=60)
            return c

        cfg = ShadowConfig(platform=args.platform, connection=passive,
                           mode=Mode.SHADOW, tick_hz=25.0, log_dir=logdir,
                           max_runtime_s=args.seconds,
                           autopilot_version=args.platform)
        runner = ShadowRunner(cfg, connection_factory=factory)
        runner.connect()
        print(f"=== command authority: "
              f"{runner.authority_evidence['result']} "
              f"(write_half={runner.authority_evidence.get('write_half_state')})")

        # An adversarial probe on the LIVE socket: prove the real connection
        # refuses to transmit, not just the fake one in the unit tests.
        denied = []
        for call in ("command_long_send", "set_mode_send",
                     "rc_channels_override_send"):
            try:
                getattr(runner.conn.mav, call)(1, 1, 400, 0, 1, 0, 0)
                denied.append(f"{call}: REACHED THE WIRE")
            except CommandAuthorityError:
                denied.append(f"{call}: denied")
        print("=== live transmit probe: " + "; ".join(denied))
        result["live_transmit_probe"] = denied

        print(f"=== running SHADOW for {args.seconds:.0f} s")
        t0 = time.time()
        header = runner.run()
        wall = time.time() - t0

        lat = getattr(runner, "tick_latencies", None)
        if not lat:
            lat = [runner.stats["max_latency_us"]] if runner.stats["ticks"] \
                else []
        result.update({
            "flight_id": header.flight_id,
            "wall_s": round(wall, 2),
            "stats": runner.stats,
            "adapter_counters": runner.adapter.counters,
            "unmapped_types": runner.adapter.unmapped_types(),
            "latency": summarise(lat),
            "command_authority": runner.authority_evidence,
            "log_dir": os.path.relpath(logdir, ROOT),
        })

        print(f"\n=== ticks: {runner.stats['ticks']}  "
              f"messages: {runner.stats['messages']}")

        # POSITIVE CONTROL on the latency instrument, and it is not optional.
        #
        # The first version of this script reported "R13: PASS, median 168.8
        # us, 8x headroom" on a run that ingested ZERO messages. Those were
        # the cost of an EMPTY tick -- the adapter had nothing to convert, the
        # core had nothing to score. Certifying a timing budget from that is
        # the same error as scoring a fault injection that never reached the
        # vehicle: ticks ran is not telemetry was processed.
        #
        # An R13 verdict therefore requires a stream that actually flowed AND
        # channels that actually reached the core.
        usable = len(runner.adapter.sample(t_mono=0.0).usable_channels())
        control = {
            "messages_ingested": runner.stats["messages"],
            "usable_channels_at_end": usable,
            "satisfied": runner.stats["messages"] > 0 and usable > 0,
            "rule": "a latency figure from an idle tick measures the loop, "
                    "not the workload",
        }
        result["latency_positive_control"] = control

        L = result["latency"]
        if not L:
            result["R13"] = "NOT_MEASURED: no ticks"
        elif not control["satisfied"]:
            result["R13"] = (
                f"INVALID_MEASUREMENT: {runner.stats['messages']} messages "
                f"ingested, {usable} usable channels -- these ticks were "
                f"idle, so the latency below is the empty-loop cost and is "
                f"NOT an R13 result")
        else:
            print(f"=== tick latency through the FULL v1.1 stack")
            print(f"    median {L['median_us']:.1f} us | p95 {L['p95_us']:.1f} "
                  f"| p99 {L['p99_us']:.1f} | max {L['max_us']:.1f} us")
            print(f"    R13 budget {R13_BUDGET_US:.0f} us -> "
                  f"{L['over_budget']} tick(s) over budget, "
                  f"worst-case headroom {L['worst_headroom_x']}x")
            result["R13"] = ("PASS" if L["over_budget"] == 0
                             else f"FAIL: {L['over_budget']} ticks over budget")
        if L and not control["satisfied"]:
            print(f"    (idle-loop cost, NOT R13: median "
                  f"{L['median_us']:.1f} us over {L['n']} empty ticks)")
        print(f"=== R13: {result['R13']}")
    finally:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    out = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                   f"shadow_sitl_{args.platform}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(out, ROOT)}")
    return 0 if str(result.get("R13", "")).startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
