"""P8: execute the preregistered repeated Mechanism A campaign.

PREREGISTERED IN
    research/physical_validation/prereg/MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md
committed before the first trial of this campaign.

WHAT THIS DOES AND DOES NOT DECIDE
-----------------------------------
It runs trials and records them. It computes NO metric, applies NO
classification and draws NO conclusion -- the preregistration fixed those, and
a runner that also decided them could quietly move one. Every trial becomes an
immutable manifest; the report is produced separately from the manifests.

THE ONE JUDGEMENT MADE HERE, STATED PLAINLY
--------------------------------------------
Tick latency is RECORDED and is NOT a validity criterion for this campaign.

The R13 budget (2 ms/tick) is a real requirement and the shadow runner checks
it. But these trials share a container with the rest of this session's work,
so the host is contended in a way a deployment's would not be: a probe run
produced `median 946.7 us | p99 1294.4 | max 10932.7 us` and 2 of 751 ticks
over budget, with the host-noise control showing 966 us median for CONSTANT
work -- i.e. most of the variance is the host, not the stack.

Adjudicating those trials TIMING_INSUFFICIENT would discard evidence about
gate weights because of a measurement artefact in an unrelated quantity. The
preregistration anticipated exactly this: TIMING_INSUFFICIENT is last in
precedence because "a trial can be timing-insufficient for a latency claim and
still perfectly valid evidence for a categorical one".

So: `timing_budget` is deliberately NOT placed in the trial record, which
leaves the timing predicate undecidable rather than false -- it appears in
every manifest's `undecidable` list. The latency numbers are still recorded in
full under `latency_recorded_not_adjudicated`.

**NO LATENCY OR TIMING CLAIM MAY BE MADE FROM THIS CAMPAIGN.** That is not a
limitation discovered afterwards; it is a consequence of where it ran.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from tools.csia_experiment import manifest as M            # noqa: E402
from tools.csia_experiment import orchestrator as O        # noqa: E402

PREREG = ("research/physical_validation/prereg/"
          "MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md")
DRIVER = os.path.join(ROOT, "tools", "deploy", "shadow_sitl_check.py")

#: The build the preregistration pins (section 2.1), reproduced from source.
PINNED_AP_COMMIT = "01a504b472259602e13df4cf07df7c0cdbb35993"

#: Per platform: the env var that points at the simulator checkout, the
#: manifest backend label, the field the trial record names the build in, the
#: commit its preregistration pins, and that preregistration.
#:
#: NOT a convenience table. Before it existed, `build_record` wrote
#: `"backend": "ardupilot_sitl"` and an `ardupilot_commit` unconditionally, so
#: a PX4 campaign would have produced 40 manifests each asserting it ran an
#: ArduPilot build it never touched -- and the adjudicator's
#: WRONG_AUTOPILOT_VERSION check would have compared a PX4 run against an
#: ArduPilot commit and passed.
PLATFORMS = {
    "ardupilot": {
        "root_env": "CSIA_AP_ROOT",
        "backend": "ardupilot_sitl",
        "commit_field": "ardupilot_commit",
        "pinned_commit": PINNED_AP_COMMIT,
        "prereg": PREREG,
        "honours_speedup": True,
    },
    "px4": {
        "root_env": "CSIA_PX4_ROOT",
        "backend": "px4_sitl",
        "commit_field": "px4_commit",
        "pinned_commit": "547e2caa9883bc1609325f02b4914b4e2482fe62",
        "prereg": ("research/physical_validation/prereg/"
                   "MECHANISM_A_PX4_REPEATED_PREREG.md"),
        # PX4 SIH is lockstep and IGNORES a requested speedup (rigs.py
        # HONOURS_SPEEDUP). The PX4 preregistration section 2 declares this
        # before the campaign as a schedule fact.
        "honours_speedup": False,
    },
}


def run_flight(platform, arm, out_path, seconds, speedup, inject_at,
               sim_root, timeout=900, trust_trace_path=None) -> dict:
    """One SITL flight. FAULT injects; CONTROL is identical and does not.

    `trust_trace_path` is the ONLY difference between Campaign A1 and A2. It
    changes no diagnostic path: the tracer reads state the frozen engine has
    already computed and writes it to a separate file.
    """
    cmd = [sys.executable, DRIVER, "--platform", platform, "--fly",
           "--speedup", str(speedup), "--seconds", str(seconds),
           "--out", out_path]
    if trust_trace_path:
        cmd += ["--trust-trace", trust_trace_path]
    if arm == "FAULT":
        cmd += ["--inject", "gps_fix_loss", "--inject-at", str(inject_at)]

    env = dict(os.environ, **{PLATFORMS[platform]["root_env"]: sim_root})
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=timeout)
    elapsed = round(time.time() - started, 1)

    payload = None
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError:
            payload = None
    trace_rows = 0
    if trust_trace_path and os.path.exists(trust_trace_path):
        with open(trust_trace_path, encoding="utf-8") as fh:
            trace_rows = sum(1 for _ in fh)
    return {"returncode": proc.returncode, "seconds": elapsed,
            "payload": payload, "trust_trace_path": trust_trace_path,
            "trust_trace_rows": trace_rows,
            "stderr_tail": (proc.stderr or "").strip().splitlines()[-3:]}


def build_record(arm, flight, commit, platform="ardupilot") -> dict:
    """Turn a flight into a trial record the validity predicates can read."""
    spec = PLATFORMS[platform]
    payload = flight["payload"] or {}
    injection = payload.get("injection") or {}
    confirmed = injection.get("confirmed")

    # RULE A. The CONTROL arm must NOT show an injection. If the driver
    # reports one on a control flight, the instrument moved on an arm where
    # nothing was applied and no arm may be read.
    if arm == "CONTROL":
        # THE DRIVER ALWAYS WRITES AN `injection` BLOCK. On a control flight
        # it is a role marker -- {"kind": null, "role": "CONTROL: fix
        # preserved"} -- not an injection. A first version tested
        # `not bool(injection)` and adjudicated the control INSTRUMENT_DEAD on
        # the validation pair, which would have declared the whole campaign
        # unreadable because a dict was non-empty. What actually distinguishes
        # the arms is whether a PARAMETER WAS WRITTEN.
        wrote_param = bool(injection.get("kind")) or "param" in injection
        null_controls = [{
            "name": "no_parameter_written",
            "quiet": not wrote_param,
            "measured": 1.0 if wrote_param else 0.0,
            "tolerance": 0.0,
            "basis": "a control flight must write no injection parameter; "
                     "`kind` is null and no `param` key is present when none "
                     "was written",
            "observed_injection_block": injection,
        }]
    else:
        null_controls = [{
            "name": "injection_readback",
            "quiet": True,
            "measured": 0.0,
            "tolerance": 0.0,
            "basis": "not a null control for the fault arm; the fault arm's "
                     "integrity is the confirmed readback, checked as the "
                     "evidence chain below",
        }]

    # THE DRIVER'S EXIT CODE IS THE R13 TIMING VERDICT, NOT A FAULT SIGNAL.
    # shadow_sitl_check.py:1136-1139 returns 0 for PASS, 2 for INDETERMINATE
    # and 1 otherwise -- purely the tick-latency budget.
    #
    # A first version of this function read `returncode != 0` as a rig fault.
    # The validation run adjudicated BOTH trials of a 1+1 pair HARDWARE_FAULT
    # on a contended host, which is exactly the misreading the module
    # docstring exists to prevent -- discarding categorical evidence about
    # gate weights because an unrelated latency budget was missed. Caught on
    # a 1+1 pair rather than after 40.
    r13_verdict = str(payload.get("R13", "")) if payload else "UNKNOWN"
    produced_usable_flight = bool(
        payload and (payload.get("stats") or {}).get("ticks"))

    # The evidence chain. COMMAND ISSUED != FAULT INJECTED: the chain breaks
    # at the first stage the driver could not evidence with a number.
    first_break = None
    if not produced_usable_flight:
        first_break = "COMMAND_ISSUED"
    elif arm == "FAULT":
        if not injection:
            first_break = "COMMAND_ISSUED"
        elif confirmed is not True:
            first_break = "SIMULATOR_STATE_CHANGED"

    record = {
        "attempted": True,
        "arm": arm,
        "backend": spec["backend"],
        "evidence_tier": "E1",
        "admissible_as_evidence": True,
        spec["commit_field"]: commit,
        "platform": platform,
        "prereg": spec["prereg"],
        "prereg_deviations": [],
        "operator_abort": False,
        # A RIG FAULT IS THE RIG BREAKING, not a budget being missed. Only a
        # flight that produced no usable telemetry qualifies.
        "rig_faults": [] if produced_usable_flight else
                      [f"no usable flight: driver exited "
                       f"{flight['returncode']} (R13={r13_verdict}), "
                       f"payload={'present' if payload else 'absent'}, "
                       f"stderr={flight['stderr_tail']}"],
        "null_controls": null_controls,
        "first_break": first_break,
        "stages": {"driver_returncode": flight["returncode"]},
        # RECORDED, NOT ADJUDICATED. See the module docstring: timing_budget is
        # deliberately absent so the predicate stays undecidable rather than
        # failing a trial for host contention.
        "latency_recorded_not_adjudicated": payload.get("latency"),
        "r13_verdict_recorded_not_adjudicated": r13_verdict,
        "latency_note": ("Measured on a contended host shared with other work "
                         "in the same container. NO LATENCY OR TIMING CLAIM "
                         "MAY BE MADE FROM THIS CAMPAIGN."),
        "flight_seconds": flight["seconds"],
    }

    # The preregistered quantities (section 5), copied verbatim from the
    # driver's own output. Nothing is derived here.
    for key in ("injection", "stats", "phases", "command_authority",
                "live_transmit_probe", "rig_flight", "host_noise_control",
                "flight_id", "R13"):
        if key in payload:
            record[f"measured_{key}"] = payload[key]

    # Section 5.1: recorded if present, NOT_RECORDED if not. Never inferred.
    record["support_state"] = payload.get("support_state", "NOT_RECORDED")

    # A2: THE TRACE IS THE POINT OF THIS CAMPAIGN. A flight that produced no
    # trust trace has not captured the quantity the campaign exists for, so it
    # is INVALID_SCENARIO rather than a valid trial with a missing column --
    # which is precisely the shape of A1's defect (FL-014), and repeating it
    # silently would be worse than the original.
    if flight.get("trust_trace_path"):
        record["trust_trace_path"] = os.path.relpath(
            flight["trust_trace_path"], ROOT) \
            if flight["trust_trace_path"].startswith(ROOT) \
            else flight["trust_trace_path"]
        record["trust_trace_rows"] = flight.get("trust_trace_rows", 0)
        record["trust_trajectory"] = ("CAPTURED"
                                      if flight.get("trust_trace_rows", 0) > 1
                                      else "NOT_CAPTURED")
        if record["trust_trajectory"] != "CAPTURED" and not first_break:
            record["first_break"] = "CSIA_RECEIVED_CHANGE"
            record["first_break_reason"] = (
                "no trust trace was produced; the quantity this campaign "
                "exists to capture is absent")
    else:
        record["trust_trajectory"] = "NOT_CAPTURED"
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(
        ROOT, "campaigns", "physical_validation", "mechanism_a_repeat_ap"))
    ap.add_argument("--platform", default="ardupilot")
    ap.add_argument("--n", type=int, default=20,
                    help="per arm; the preregistration fixes this at 20")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--speedup", type=int, default=5)
    ap.add_argument("--inject-at", type=float, default=12.0)
    ap.add_argument("--sim-root", "--ap-root", dest="sim_root", default=None,
                    help="the simulator checkout. Defaults to the platform's "
                         "own env var (CSIA_AP_ROOT / CSIA_PX4_ROOT) and to "
                         "NOTHING otherwise -- see main()")
    ap.add_argument("--raw-dir", default="/tmp/p8/raw")
    ap.add_argument("--campaign-id", default=None,
                    help="overrides the derived id; A2 uses MECHA2-ARDUPILOT")
    ap.add_argument("--trust-trace-dir", default=None,
                    help="enable trust tracing, one file per flight. Required "
                         "for CAMPAIGN A2")
    args = ap.parse_args(argv)

    if args.platform not in PLATFORMS:
        raise SystemExit(f"unknown platform {args.platform!r}; "
                         f"known: {sorted(PLATFORMS)}")
    spec = PLATFORMS[args.platform]
    sim_root = args.sim_root or os.environ.get(spec["root_env"])
    if not sim_root:
        raise SystemExit(
            f"--sim-root or ${spec['root_env']} must point at the "
            f"{args.platform} checkout. It is NOT defaulted: a wrong default "
            f"produces a campaign against a build nobody chose.")

    # PX4 SIH ignores a requested speedup. Recording the REQUESTED value as if
    # it were the one that ran is how a rate-dependent check ends up gated on
    # a number that was never true (rigs.py, HONOURS_SPEEDUP).
    speedup = args.speedup if spec["honours_speedup"] else 1
    if speedup != args.speedup:
        print(f"NOTE: {args.platform} ignores --speedup {args.speedup}; "
              f"running at {speedup}x. Both are recorded per trial.")

    os.makedirs(args.raw_dir, exist_ok=True)
    campaign = args.campaign_id or f"MECHA-{args.platform.upper()}"
    if args.trust_trace_dir:
        os.makedirs(args.trust_trace_dir, exist_ok=True)
    total = args.n * 2
    O.plan_campaign(args.dir, campaign, "gps_fix_loss", total,
                    prereg_path=spec["prereg"])

    # Arms interleaved, FAULT first. Interleaving matters: running all 20
    # faults then all 20 controls confounds arm with anything that drifts
    # over the campaign -- host load, disk, thermal.
    order = []
    for i in range(args.n):
        order.append(("FAULT", 2 * i + 1))
        order.append(("CONTROL", 2 * i + 2))

    for arm, index in order:
        trial_id = f"{campaign}-{index:03d}"
        target = os.path.join(args.dir, f"{trial_id}.json")
        if os.path.exists(target):
            print(f"{trial_id} already recorded, skipping")
            continue
        raw = os.path.join(args.raw_dir, f"{trial_id}_{arm}.json")
        trace = (os.path.join(args.trust_trace_dir,
                              f"{trial_id}_{arm}.trace.jsonl")
                 if args.trust_trace_dir else None)
        flight = run_flight(args.platform, arm, raw, args.seconds,
                            speedup, args.inject_at, sim_root,
                            trust_trace_path=trace)
        record = build_record(arm, flight, spec["pinned_commit"],
                              platform=args.platform)
        record["requested_speedup"] = args.speedup
        record["effective_speedup"] = speedup
        path = O.run_trial(args.dir, trial_id, spec["backend"],
                           record_override=record)
        body = M.load(path)
        print(f"{trial_id} {arm:8s} {body['adjudication']['state']:18s} "
              f"{flight['seconds']:6.1f}s "
              f"ticks={(flight['payload'] or {}).get('stats', {}).get('ticks')} "
              f"trace_rows={flight.get('trust_trace_rows', 0)}")

    summary = O.report(args.dir)
    out = os.path.join(args.dir, "_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({k: summary[k] for k in
                      ("planned", "attempted", "valid", "invalid",
                       "not_attempted", "by_state")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
