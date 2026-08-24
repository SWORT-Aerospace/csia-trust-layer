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
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.deploy.guard import CommandAuthorityError          # noqa: E402
from csia.deploy.shadow import Mode, ShadowConfig, ShadowRunner  # noqa: E402
from csia.simulation.rigs import LAUNCHERS, connect, fly   # noqa: E402
from csia.simulation.host_noise import (                 # noqa: E402
    measure as measure_host_noise, r13_verdict)
from csia.simulation.tee import MavlinkTee               # noqa: E402

R13_BUDGET_US = 2000.0
# Where the tee publishes and CSIA listens. UDP because a listener
# binding a port cannot accidentally become a client of anything.
TEE_OUT = ("127.0.0.1", 14561)
# The rig commands here; the tee owns SERIAL0.
RIG_LINK = "tcp:127.0.0.1:5762"


def start_tee_process(source, out_addr, platform, profile, status_path,
                      timeout=30.0, min_types=5):
    """Run the tee in its own interpreter and wait for real traffic.

    The positive control is unchanged in substance and is now read from the
    tee's status file instead of an attribute: "did the feed carry sensor
    data before we started timing" is the question, and a separate process
    cannot be interrogated by touching `self.stats`.
    """
    if os.path.exists(status_path):
        os.unlink(status_path)
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    cmd = [sys.executable, "-m", "csia.simulation.tee",
           "--source", source, "--out", f"{out_addr[0]}:{out_addr[1]}",
           "--platform", platform, "--profile", profile,
           "--status", status_path]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout
    seen = 0
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"tee process exited early (rc {proc.returncode})")
        try:
            with open(status_path, encoding="utf-8") as fh:
                seen = len(json.load(fh).get("by_type", {}))
        except (OSError, ValueError):
            seen = 0
        if seen >= min_types:
            return proc, seen
        time.sleep(0.5)
    proc.kill()
    raise SystemExit(
        f"tee process never carried sensor traffic ({seen} message types). "
        f"Without it this run would measure an idle loop again.")


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
    ap.add_argument("--stream-profile", choices=("full", "companion"),
                    default="full",
                    help="companion = only the streams CSIA reads")
    ap.add_argument("--tee-mode", choices=("process", "thread"),
                    default="process",
                    help="process (default) runs the tee in its own "
                         "interpreter so it cannot steal GIL time from the "
                         "tick being measured; thread is the old in-process "
                         "arrangement, kept as the null control that shows "
                         "the difference")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    workdir = os.path.join(ROOT, "build", f"shadow-{args.platform}")
    logdir = os.path.join(ROOT, "logs", f"shadow-sitl-{args.platform}")
    proc, conn_str = LAUNCHERS[args.platform](workdir, args.speedup)
    print(f"=== {args.platform} SITL launched (pid {proc.pid}) -> {conn_str}")

    result = {"platform": args.platform, "seconds": args.seconds}
    tee = None
    try:
        # The rig holds the COMMAND link (SERIAL0) for the whole run. It is
        # what asks the autopilot to stream, because a shadow monitor cannot:
        # request_data_stream_send is a transmit, and the guard denies it. On
        # a real aircraft that request comes from the GCS or from the FC's own
        # SR*_ parameters -- see docs/deployment/AIRCRAFT_INTEGRATION.md.
        # It is NOT closed early: the streams stop when the requester leaves.
        # THE TELEMETRY TEE. This is what makes an R13 measurement possible.
        #
        # Stream rates are per-link and require a transmit on that link, and
        # CSIA cannot transmit. So the tee takes the GCS role: it holds
        # SERIAL0, requests the streams there, and forwards every byte to a
        # UDP endpoint that CSIA merely listens on. CSIA never asks for
        # anything -- it reads a feed someone else established, which is what
        # a tee is on a real aircraft.
        #
        # The rig commands on SERIAL1 instead. Commands work on any link;
        # only STREAMS are per-link, which is precisely the distinction that
        # took four runs to establish.
        #
        # OUT OF PROCESS BY DEFAULT. The tee used to run as a thread here, and
        # under the GIL every byte it decoded was time stolen from the tick
        # this script exists to time. Controlled measurement, synthetic tick
        # against N competing GIL threads: 679.5 us at 0, 954.6 us at 1,
        # 1598.3 us at 2 -- against a live figure of ~1590 us. Most of the R13
        # FAIL was the instrument.
        #
        # It is also the faithful arrangement: on a real aircraft the tee is
        # the GCS or a UART split, never a thread inside CSIA.
        tee, tee_proc, status_path = None, None, None
        if args.tee_mode == "process":
            status_path = os.path.join(workdir, "tee_status.json")
            tee_proc, types = start_tee_process(
                conn_str, TEE_OUT, args.platform, args.stream_profile,
                status_path)
            print(f"=== tee: {conn_str} -> udp {TEE_OUT}  "
                  f"({types} message types flowing, pid {tee_proc.pid}, "
                  f"SEPARATE INTERPRETER)")
        else:
            tee = MavlinkTee(conn_str, [TEE_OUT], platform=args.platform,
                             profile=args.stream_profile)
            tee.start()
            if not tee.wait_for_traffic(min_types=5, timeout=25.0):
                raise SystemExit(
                    f"tee never carried sensor traffic: "
                    f"{sorted(tee.stats['by_type'])}. Without it this run "
                    f"would measure an idle loop again.")
            types = len(tee.stats["by_type"])
            print(f"=== tee: {conn_str} -> udp {TEE_OUT}  "
                  f"({types} message types flowing, IN-PROCESS THREAD -- "
                  f"this contends for the GIL with the measured tick)")
        result["tee"] = {"source": conn_str, "out": f"{TEE_OUT[0]}:{TEE_OUT[1]}",
                         "profile": args.stream_profile,
                         "mode": args.tee_mode,
                         "shares_interpreter_with_csia":
                             args.tee_mode == "thread",
                         "types_flowing_before_measurement": types}
        rig_conn = connect(RIG_LINK, args.platform)

        print("=== rig commands on SERIAL1 (streams are per-link)")
        if args.fly:
            print("=== rig: arming and climbing (rig authority, not CSIA)")
            ev = fly(rig_conn, args.platform)
            print(f"    armed={ev['armed']} climbed={ev['climbed_m']:.2f} m")
            result["rig_flight"] = {"armed": ev["armed"],
                                    "climbed_m": round(ev["climbed_m"], 2)}

        from pymavlink import mavutil

        passive = f"udpin:{TEE_OUT[0]}:{TEE_OUT[1]}"

        def factory():
            # The TEED feed. Bound, never dialled; CSIA only listens.
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
            "phases": {k: summarise(list(v))
                       for k, v in runner.phase_us.items()},
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
            # The tee runs as a THREAD in this interpreter. Under the GIL its
            # forwarding work is charged to the core's wall clock, and a
            # controlled test (same log, same core, varying only concurrent
            # in-process threads) measured 679 / 955 / 1598 us at 0 / 1 / 2
            # threads. An earlier run of this harness reported 1590 us and it
            # was recorded as an R13 failure of CSIA. It was not.
            #
            # For a clean core figure use
            # tools/deploy/profile_core_from_log.py, which replays a flight
            # log with nothing else in the process.
            # The caveat must match the run that produced the numbers. It
            # was printed unconditionally, so a process-mode run would have
            # carried a warning about a thread it did not have -- a stale
            # caveat is as misleading as a missing one.
            if args.tee_mode == "thread":
                result["timing_caveat"] = (
                    "phases include GIL contention from the IN-PROCESS tee "
                    "thread; NOT a clean core measurement. Re-run with "
                    "--tee-mode process. See W-8.")
                print("    NOTE: phases include in-process tee contention -- "
                      "not a clean core figure (see W-8)")
            else:
                result["timing_caveat"] = (
                    "tee ran in a SEPARATE interpreter, so no GIL contention "
                    "from it. Remaining contention is the host: this "
                    "container also runs SITL, and run-to-run spread on the "
                    "same command exceeds the tee effect. An R13 verdict from "
                    "shared cloud infrastructure is a statement about the "
                    "host as much as about CSIA.")
                print("    NOTE: tee is out-of-process; remaining variance is "
                      "the host (SITL shares this container)")
            ph = result["phases"]
            print(f"    phases (median us): "
                  + "  ".join(f"{k}={ph[k]['median_us']:.1f}"
                              for k in ("sample", "convert", "core")
                              if ph.get(k)))
            print(f"    R13 budget {R13_BUDGET_US:.0f} us -> "
                  f"{L['over_budget']} tick(s) over budget, "
                  f"worst-case headroom {L['worst_headroom_x']}x")
            # RULE A on the CLOCK. Before attributing an over-budget tick
            # to CSIA, measure what a constant workload does in the same
            # process on the same host -- see csia/simulation/host_noise.py
            # for the numbers that forced this. It cannot turn a real failure
            # into a pass: INDETERMINATE requires the control to fail too.
            noise = measure_host_noise(
                n_ticks=L["n"], target_us=L["median_us"],
                budget_us=R13_BUDGET_US, trials=3)
            result["host_noise_control"] = noise
            w = noise["worst_trial"]
            print(f"    host-noise control (constant work, same process): "
                  f"median {w['median_us']:.0f} us, max {w['max_us']:.0f} us, "
                  f"{w['over_budget']}/{w['n']} over budget")
            result["R13"] = r13_verdict(L["over_budget"], noise, L["n"])
        if L and not control["satisfied"]:
            print(f"    (idle-loop cost, NOT R13: median "
                  f"{L['median_us']:.1f} us over {L['n']} empty ticks)")
        print(f"=== R13: {result['R13']}")
    finally:
        try:
            if tee is not None:
                tee.stop()
        except Exception:
            pass
        if tee_proc is not None:
            tee_proc.send_signal(signal.SIGINT)
            try:
                tee_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tee_proc.kill()
            if status_path and os.path.exists(status_path):
                try:
                    with open(status_path, encoding="utf-8") as fh:
                        result.setdefault("tee", {})["final_status"] = \
                            json.load(fh)
                except Exception:
                    pass
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
    # INDETERMINATE is not a pass. It exits non-zero, with its own code, so
    # a CI job cannot read "the host was too noisy to tell" as success.
    r13 = str(result.get("R13", ""))
    if r13.startswith("PASS"):
        return 0
    return 2 if r13.startswith("INDETERMINATE") else 1


if __name__ == "__main__":
    sys.exit(main())
