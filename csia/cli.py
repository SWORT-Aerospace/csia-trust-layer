"""csia — command-line entry point.

  csia build    rebuild all scenario replays (data/replay/*.json)
  csia serve    serve the web dashboard (build first if replays missing)
  csia report   print detection/diagnosis summary for every scenario
  csia info     package + scenario catalog info

All commands run relative to the current working directory's data/ tree.
"""

import argparse
import logging
import os
import sys

import numpy as np


def _build(args) -> int:
    from .dashboard import export_replay
    from .scenarios import SCENARIO_PROFILE, SCENARIOS, run_scenario
    from .sensors import generate_flight
    from .trust_graph import build_trust_graph

    replay_dir = os.path.join(args.data_dir, "replay")
    os.makedirs(replay_dir, exist_ok=True)
    base = generate_flight()                      # shared baseline flight
    profile_truth = {}                            # cache non-default profiles
    graph = build_trust_graph()
    for name in SCENARIOS:
        prof = SCENARIO_PROFILE.get(name)
        if prof:
            truth = profile_truth.setdefault(prof, generate_flight(profile=prof))
        else:
            truth = base
        title, faults, td, hist, diag = run_scenario(name, truth=truth)
        export_replay(name, title, td, hist, diag, graph, faults, replay_dir)
        print(f"built {name}")
    print(f"replays -> {replay_dir}")
    return 0


def _serve(args) -> int:
    from .dashboard import serve
    replay_dir = os.path.join(args.data_dir, "replay")
    if not os.path.isdir(replay_dir) or not os.listdir(replay_dir):
        print("no replays found — building first")
        _build(args)
    serve(port=args.port, replay_dir=replay_dir, host=args.host)
    return 0


def _report(args) -> int:
    from .scenarios import SCENARIOS, run_scenario
    from .sensors import generate_flight

    truth = generate_flight()
    print(f"{'scenario':20s} {'target':10s} {'min trust':>9s} "
          f"{'detect [s]':>10s} {'peak diagnosis':40s} {'lat us':>7s}")
    for name in SCENARIOS:
        title, faults, td, hist, diag = run_scenario(name, truth=truth)
        target = faults[0].target if faults else "-"
        if faults and faults[0].kind != "dropout":
            c = hist.col(target)
            tmin = float(hist.trust[250:, c].min())
            onset = faults[0].start
            below = np.where((hist.t > onset)
                             & (hist.trust[:, c] < 0.85))[0]
            detect = f"{hist.t[below[0]] - onset:.1f}" if len(below) else ">n/a"
        else:
            tmin, detect = float(hist.trust[250:].min()), "-"
        nominal = diag.causes.index("nominal")
        non_nom = diag.posterior.copy()
        non_nom[:, nominal] = 0.0
        kk = int(np.argmax(non_nom.max(axis=1)))
        print(f"{name:20s} {target:10s} {tmin:9.2f} {detect:>10s} "
              f"{diag.callout(kk, 2):40s} "
              f"{float(hist.latency_us[10:].mean()):7.1f}")
    return 0


def _run(args) -> int:
    from .runtime import (FailsafeLevel, LoggingActuator,
                          SimulatedFlightSource, TrustLayerRuntime)
    if args.source == "sim":
        source = SimulatedFlightSource(scenario=args.scenario)
    elif args.source == "mavlink":
        from .runtime.plugins import MavlinkSource
        source = MavlinkSource(conn=args.conn)
    else:
        raise SystemExit(f"unknown source {args.source!r}")

    from .profiles import get_profile
    actuator = LoggingActuator()
    runtime = TrustLayerRuntime(
        source, actuators=[actuator],
        realtime=args.realtime, speed=args.speed,
        log_path=args.log, profile=get_profile(args.profile))
    print(f"runtime: source={args.source} scenario={getattr(source, 'scenario', '-')} "
          f"{'REALTIME' if args.realtime else 'fast-as-possible'}"
          f"{' x' + str(args.speed) if args.realtime else ''}")
    summary = runtime.run()

    print(f"\n=== run complete: {summary.ticks} ticks, "
          f"trust-core+failsafe mean {summary.mean_latency_us:.0f} us/tick ===")
    if summary.errors:
        print(f"WARNING: {summary.errors} trust-layer errors were contained "
              "during this run — inspect the log")
    print(f"final failsafe level: {summary.final_level}")
    for tr in summary.transitions:
        print(f"  t={tr.t:5.1f}s  {tr.previous.name} -> {tr.level.name}: "
              f"{'; '.join(tr.reasons)}")
        for a in tr.actions:
            print(f"           * {a.name} {a.params or ''}")
    worst = sorted(summary.min_trust.items(), key=lambda kv: kv[1])[:4]
    print("min trust (t>10s): "
          + "  ".join(f"{n}={v:.2f}" for n, v in worst))
    if args.log:
        print(f"state log -> {args.log}")
    return 0 if summary.final_level != FailsafeLevel.EMERGENCY.name \
        or args.scenario == "dual_imu_failure" else 1


def _analyze_logs(args) -> int:
    """Real-data validation: replay PX4 .ulg flight logs through the online
    trust layer + failsafe and report the number that matters commercially:
    FALSE ALARMS PER FLIGHT HOUR on presumed-healthy flights."""
    import glob
    import json as _json

    from .runtime import FailsafePolicy, OnlineTrustLayer, TrustLayerRuntime
    from .runtime.failsafe import FailsafeConfig
    from .runtime.ulog_source import UlogSource

    files = []
    for pattern in args.logs:
        files.extend(sorted(glob.glob(pattern)))
    if not files:
        raise SystemExit("no .ulg files matched")

    results = []
    total_hours = 0.0
    total_transitions = 0
    print(f"{'log':38s} {'dur':>6s} {'sensors':>7s} {'minT':>5s} "
          f"{'alarms':>6s}  worst sensor / notes")
    for path in files:
        try:
            src = UlogSource(path)
        except Exception as exc:
            print(f"{os.path.basename(path)[:38]:38s}  SKIP: {exc}")
            continue
        if src.duration < 30.0:
            print(f"{os.path.basename(path)[:38]:38s}  SKIP: too short "
                  f"({src.duration:.0f} s)")
            continue
        layer = OnlineTrustLayer(
            field_mode=True,                       # real-world tolerance pkg
            stale_timeout_s=src.stale_timeouts())  # log topic rates != live
        # Offline-validation posture: longer confirmation, and attitude
        # thresholds acknowledging that public logs carry a SINGLE usable
        # IMU stream (attitude evidence rests on 2 edges instead of 5 —
        # the SOW001 vehicle provides the full set by design).
        policy = FailsafePolicy(FailsafeConfig(
            arm_time=20.0, dwell_up=3.0, dwell_down=10.0,
            att_caution=0.45, att_emergency=0.30))
        runtime = TrustLayerRuntime(src, layer=layer, policy=policy)
        try:
            summary = runtime.run()
        except Exception as exc:
            print(f"{os.path.basename(path)[:38]:38s}  ERROR: {exc}")
            continue
        hours = src.duration / 3600.0
        total_hours += hours
        n_alarm = len(summary.transitions)
        total_transitions += n_alarm
        present = ",".join(n[:3] for n in src.sensors_present)
        worst = min(summary.min_trust.items(), key=lambda kv: kv[1])             if summary.min_trust else ("-", 1.0)
        results.append({
            "log": os.path.basename(path), "duration_s": round(src.duration, 1),
            "sensors": src.sensors_present,
            "min_trust": summary.min_trust,
            "transitions": [{"t": tr.t, "level": tr.level.name,
                             "reasons": tr.reasons}
                            for tr in summary.transitions],
            "bad_samples": layer.bad_samples,
            "excluded_channels": getattr(src, "excluded", {}),
        })
        print(f"{os.path.basename(path)[:38]:38s} {src.duration:5.0f}s "
              f"{len(src.sensors_present):7d} {worst[1]:5.2f} "
              f"{n_alarm:6d}  {worst[0]}"
              + (f" | {layer.bad_samples} bad samples rejected"
                 if layer.bad_samples else ""))

    if total_hours > 0:
        rate = total_transitions / total_hours
        print(f"\n=== REAL-DATA VALIDATION: {len(results)} flights, "
              f"{total_hours:.2f} flight hours ===")
        print(f"failsafe activations: {total_transitions}  ->  "
              f"{rate:.2f} activations per flight hour")
        print("(on presumed-healthy public logs every activation is a "
              "candidate false alarm — inspect reasons in the JSON report)")
    if args.out:
        with open(args.out, "w") as fh:
            _json.dump({"flights": results,
                        "total_hours": round(total_hours, 3),
                        "total_transitions": total_transitions}, fh, indent=1)
        print(f"report -> {args.out}")
    return 0


def _service(args) -> int:
    from .profiles import get_profile
    from .runtime.service import run_service
    replay_dir = os.path.join(args.data_dir, "replay")
    if not os.path.isdir(replay_dir) or not os.listdir(replay_dir):
        print("no replays found — building first")
        _build(args)
    print(f"CSIA service: live runtime ({args.scenario}, x{args.speed}) "
          f"+ dashboard at http://127.0.0.1:{args.port} — open the LIVE tab")
    run_service(scenario=args.scenario, port=args.port,
                replay_dir=replay_dir, speed=args.speed,
                profile=get_profile(args.profile))
    return 0


def _bench(args) -> int:
    from .validation import bench
    bench(args.out)
    return 0


def _mc(args) -> int:
    from .validation import monte_carlo
    monte_carlo(args.runs, True, args.seed, args.out)
    return 0


def _info(args) -> int:
    from . import __version__
    from .scenarios import SCENARIOS
    print(f"csia-trust-layer {__version__} — SWORT LLC CSIA Trust Layer")
    print("SIMULATION / RESEARCH PROTOTYPE — NOT FLIGHT SOFTWARE")
    print(f"scenarios: {', '.join(SCENARIOS)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="csia", description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--data-dir", default="data",
                    help="data tree root (default: ./data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="rebuild scenario replays").set_defaults(fn=_build)
    sp = sub.add_parser("serve", help="serve the web dashboard")
    sp.add_argument("--port", type=int, default=8017)
    sp.add_argument("--host", default="127.0.0.1")
    sp.set_defaults(fn=_serve)
    sub.add_parser("report", help="scenario detection summary").set_defaults(fn=_report)
    rp = sub.add_parser("run", help="run the real-time trust layer runtime")
    rp.add_argument("--source", choices=("sim", "mavlink"), default="sim")
    rp.add_argument("--scenario", default="clean",
                    help="simulated scenario (with --source sim)")
    rp.add_argument("--conn", default="udp:0.0.0.0:14550",
                    help="MAVLink connection string (with --source mavlink)")
    rp.add_argument("--realtime", action="store_true",
                    help="pace samples to wall clock")
    rp.add_argument("--speed", type=float, default=1.0,
                    help="realtime pacing multiplier")
    rp.add_argument("--log", default=None, help="write JSONL state log here")
    rp.add_argument("--profile", default="sow001_quad")
    rp.set_defaults(fn=_run)
    svc = sub.add_parser("service",
                         help="single-command product: live runtime + dashboard")
    svc.add_argument("--scenario", default="gps_spoof")
    svc.add_argument("--port", type=int, default=8017)
    svc.add_argument("--speed", type=float, default=2.0)
    svc.add_argument("--profile", default="sow001_quad")
    svc.set_defaults(fn=_service)
    al = sub.add_parser("analyze-logs",
                        help="replay real PX4 .ulg logs; report false alarms "
                             "per flight hour")
    al.add_argument("logs", nargs="+", help=".ulg files or globs")
    al.add_argument("--out", default=None, help="JSON report path")
    al.set_defaults(fn=_analyze_logs)
    bp = sub.add_parser("bench", help="C1 truth table: detection under "
                        "sim vs field configurations")
    bp.add_argument("--out", default="campaigns/bench.json")
    bp.set_defaults(fn=_bench)
    mp = sub.add_parser("mc", help="Monte Carlo detection/false-alarm campaign")
    mp.add_argument("--runs", type=int, default=150)
    mp.add_argument("--seed", type=int, default=0)
    mp.add_argument("--out", default="campaigns/monte_carlo.json")
    mp.set_defaults(fn=_mc)
    sub.add_parser("info", help="package info").set_defaults(fn=_info)
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
