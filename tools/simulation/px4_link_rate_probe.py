"""Why two committed artifacts disagree about the same PX4 channel by 10x.

THE CONFLICT. Two measurements in this repository, both committed, both
correct, disagree about `baro.altitude` on PX4 by an order of magnitude:

    research/v1_1/results/qualification_px4.json   9.825 Hz
    research/v1_1/results/shadow_flights/*.jsonl   1.00  Hz

`docs/simulation/CHANNEL_SEMANTICS.yaml` declares 10 Hz. `MAX_AGE_MARGIN`
turns that declaration into `max_age = 5.0 / 10 = 0.50 s`, and a channel that
actually arrives every 1.00 s is therefore STALE on roughly half of all ticks.
That is the measured cause of PX4 baro starvation: the baro node was fresh on
82 of 1001 ticks (8.2 %) and `altitude_baro` carried weight on 8.1 %, against
99.9 % on ArduPilot.

WHY THIS TOOL EXISTS RATHER THAN A ONE-LINE CONTRACT EDIT. The first response
to the conflict was to "correct" the declaration from 10 Hz to 1 Hz. That edit
was wrong and was reverted. Neither number is a property of the platform:

    the rate is a property of the LINK, set by whoever last transmitted
    SET_MESSAGE_INTERVAL on it

Two things differ between the two tools at once, so neither artifact alone can
identify the cause:

    (a) INSTANCE  qualification binds 14550 (Normal); CSIA binds 14540
                  (Onboard, the companion port)
    (b) REQUESTS  qualification calls `rigs.connect()`, which sends
                  MAV_CMD_SET_MESSAGE_INTERVAL for msg 29 at 10 Hz; CSIA's
                  link is a bare passive bind that requests nothing, because
                  shadow mode may not transmit

This probe holds one variable at a time. Every arm binds BOTH links inside the
SAME simulator run, so the instance comparison is made under identical
conditions rather than across two boots.

    passive          neither link requests anything
    request          14550 gets connect()'s requests; 14540 still requests none
    request_onboard  14540 requests for itself; 14550 requests none

Arm 3 is the one that decides whether the starvation is INHERENT or FIXABLE:
CSIA cannot transmit, but if a transmit on CSIA's own link raises the rate,
then the fix is for the rig to drive that link -- the same role the tee already
plays for ArduPilot -- rather than for the contract to be edited.

THE CLAIM THIS FALSIFIES. `tools/deploy/shadow_sitl_check.py` justifies PX4
running WITHOUT a tee: "It runs several mavlink instances, each streaming a
full set unprompted... Interposing a tee there would model a constraint the
platform does not have." That was measured by counting message TYPES over 4 s
per link. A 1 Hz message is present in a 4 s window, so a type count cannot
distinguish 1 Hz from 10 Hz. The claim is true of message PRESENCE and false
of message RATE, and it is rate that decides staleness.

Launches the simulator; reads no committed artifact and writes none of them.

    python tools/simulation/px4_link_rate_probe.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

SECONDS = 40.0
SETTLE_S = 3.0

# The three channels in dispute, plus three that are NOT, as a within-run
# control: if an arm changed every rate, the arm would be measuring the boot
# rather than the requests.
WATCH = {
    "SCALED_PRESSURE": "baro.altitude, baro.temp_c",
    "BATTERY_STATUS": "battery.voltage, battery.current",
    "VIBRATION": "vibration.rms",
    "ATTITUDE": "control (not requested by any arm)",
    "GLOBAL_POSITION_INT": "control (requested by connect(), msg 33)",
    "GPS_RAW_INT": "control (requested by connect(), msg 24)",
}
# msgid -> hz, matching what rigs.connect() asks for on the channels in dispute
ONBOARD_REQUESTS = ((29, 10), (147, 10), (241, 10))
ARMS = ("passive", "request", "request_onboard")


def _count(links, seconds):
    """Drain several bound links for `seconds` of wall time, tallying types."""
    tally = {name: {} for name in links}
    t_end = time.time() + seconds
    while time.time() < t_end:
        for name, m in links.items():
            while True:
                msg = m.recv_match(blocking=False)
                if msg is None:
                    break
                t = msg.get_type()
                tally[name][t] = tally[name].get(t, 0) + 1
        time.sleep(0.002)
    return tally


def run_arm(arm, workdir):
    from pymavlink import mavutil

    from csia.simulation.rigs import connect, launch_px4

    proc, normal_str = launch_px4(workdir, speedup=1)
    try:
        links = {}
        if arm == "request":
            # connect() dials the Normal link AND sends its interval requests.
            links["14550"] = connect(normal_str, "px4")
        else:
            m = mavutil.mavlink_connection("udpin:127.0.0.1:14550")
            if not m.wait_heartbeat(timeout=90):
                raise SystemExit("no heartbeat on 14550")
            links["14550"] = m

        onboard = mavutil.mavlink_connection("udpin:127.0.0.1:14540")
        if not onboard.wait_heartbeat(timeout=90):
            raise SystemExit("no heartbeat on 14540")
        links["14540"] = onboard

        if arm == "request_onboard":
            # A udpin socket has a peer as soon as it has RECEIVED, so it can
            # transmit back into the instance that is streaming to it.
            for mid, hz in ONBOARD_REQUESTS:
                onboard.mav.command_long_send(
                    onboard.target_system, onboard.target_component,
                    511, 0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)

        time.sleep(SETTLE_S)
        for m in links.values():                      # discard the settle window
            while m.recv_match(blocking=False) is not None:
                pass
        t0 = time.time()
        tally = _count(links, SECONDS)
        return time.time() - t0, tally
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "PX4_LINK_RATE_PROBE.json"))
    ap.add_argument("--workdir", default=os.path.join(
        ROOT, "research", "v1_1", "results", ".px4_link_probe"))
    ap.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args()

    arms = [a for a in args.arms.split(",") if a.strip()]
    measured = {}
    for arm in arms:
        print(f"=== arm={arm}: launching PX4 SIH, {SECONDS:.0f} s per link")
        dur, tally = run_arm(arm, os.path.join(args.workdir, arm))
        measured[arm] = {
            "seconds": round(dur, 3),
            "links": {
                link: {t: {"count": c, "hz": round(c / dur, 3)}
                       for t, c in sorted(counts.items()) if t in WATCH}
                for link, counts in tally.items()
            },
        }
        for link in sorted(tally):
            row = measured[arm]["links"][link]
            for t in sorted(row):
                print(f"    {link}  {t:22s} {row[t]['count']:6d} "
                      f"{row[t]['hz']:7.3f} Hz")

    # WITHOUT THIS THE GUARD IS BLIND. tests/test_px4_link_rate.py checks the
    # contract against this artifact, not against a live simulator, so a PX4
    # upgrade that changed the default stream rates would leave the test
    # passing against a stale measurement. Recording the build that produced
    # these numbers lets the test refuse to testify about a different one.
    from csia.simulation.rigs import simulator_provenance
    out = {
        "simulator_provenance": simulator_provenance("px4"),
        "airframe": {"PX4_SYS_AUTOSTART": "10040",
                     "PX4_SIM_MODEL": "sihsim_quadx"},
        "what_this_resolves": "qualification_px4.json and the shadow flight "
                              "logs disagree by 10x about the same PX4 "
                              "channel; both are correct",
        "finding": "the stream rate is a property of the LINK, set by whoever "
                   "last transmitted SET_MESSAGE_INTERVAL on it, not a "
                   "property of the platform or of the mavlink instance",
        "csia_link": "udpin:127.0.0.1:14540 -- passive, never transmits, so "
                     "nothing ever raises its rates",
        "consequence": "CHANNEL_SEMANTICS.yaml declares one rate per "
                       "(channel, platform) and MAX_AGE_MARGIN derives "
                       "max_age from it, so a declaration measured on a "
                       "REQUESTING link starves a channel on a PASSIVE one",
        "seconds_per_arm": SECONDS,
        "settle_discarded_s": SETTLE_S,
        "channels_in_dispute": WATCH,
        "onboard_requests": [{"msgid": m, "hz": h} for m, h in
                             ONBOARD_REQUESTS],
        "arms": measured,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
