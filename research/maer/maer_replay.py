"""Replay one captured scenario through one arm, deterministically.

The recording is fed to a fresh `ArduPilotAdapter` whose CLOCK IS THE RECORDED
RECEIVE TIME, not wall clock. Staleness therefore replays exactly as it
happened, and two replays of the same recording produce identical output. That
is what makes the A1-vs-A1G comparison paired rather than merely similar: both
arms consume the same bytes and the same time base.

The only per-arm object is `ArmWrapper`, installed on `layer.diag`. The frozen
core is untouched; with arm A0 the wrapper delegates to a stock `DiagnosisCore`
built from the stock hypothesis map, which `tests/test_maer_arms.py` checks
reproduces production output exactly.

  python research/maer/maer_replay.py --capture <tag> --arm A1
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
_HERE = os.path.dirname(os.path.abspath(__file__))

RAW_DIR = os.path.join(ROOT, "research", "maer", "results", "scored", "raw")
TICK_HZ = 25.0


def _load_mod(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ARMS_MOD = _load_mod("_maer_arms", "maer_arms.py")


def load_capture(tag):
    path = os.path.join(RAW_DIR, f"{tag}.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def lam_from_consistency(c):
    """Invert the frozen core's map to recover the pre-transform lam.

    B4 is defined on the standardised PRE-TRANSFORM residual, not on the
    consistency. TrustState exposes only the consistency, and the map
    c = exp(-0.5 max(0, lam-1)) inverts exactly for c < 1 (and pins lam <= 1
    where c == 1, which is the healthy floor B4's standardisation expects).
    """
    import math
    c = min(max(float(c), 1e-12), 1.0)
    return 1.0 if c >= 1.0 else 1.0 - 2.0 * math.log(c)


def replay(capture, arm, cusum_stats=None):
    """Drive the frozen core from the recording, with one arm attached.

    `cusum_stats` is (mu0, sigma0) derived from the CLEAN arm only, exactly as
    B4 requires. Passing None for a CUSUM arm is a programming error rather
    than a default, because an unstandardised CUSUM is not the frozen detector.
    """
    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    from csia.runtime.online import OnlineTrustLayer

    msgs = capture["messages"]
    meta = capture["meta"]

    now = {"t": 0.0}
    adapter = ArduPilotAdapter(clock=lambda: now["t"])
    layer = OnlineTrustLayer(tick_hz=TICK_HZ, field_mode=True)
    wrapper = ARMS_MOD.ArmWrapper(arm)
    layer.diag = wrapper                       # research-only wrapper
    cusum = None
    if arm in ("A2", "A3"):
        if not cusum_stats:
            raise ValueError(
                "CUSUM arms need clean-derived (mu0, sigma0); running without "
                "them would not be the frozen B4 detector")
        cusum = ARMS_MOD.Cusum()
        mu0, sigma0 = cusum_stats

    ticks, next_tick, dt = [], 0.0, 1.0 / TICK_HZ
    last_gps = None

    for m in msgs:
        t = float(m["_t_recv"])
        now["t"] = t
        adapter.ingest(m)
        if m.get("mavpackettype") == "GPS_RAW_INT":
            last_gps = m
            wrapper.sidecar.observe(m)
        while next_tick <= t:
            now["t"] = next_tick
            smp = adapter.sample(t_mono=next_tick)
            states = []
            # The adapter's OWN hand-off, including its freshness gate. Not
            # reimplemented here: a second copy of that logic would be a
            # second thing to keep in step with the frozen core.
            for sensor, ts, chans in adapter.to_core_samples(smp):
                states.extend(layer.ingest(sensor, ts, chans) or [])
            for st in states:
                row = dict(wrapper.rows[-1]) if wrapper.rows else {}
                row.update({
                    "t": round(float(st.t), 6),
                    "trust_gps": float(st.trust.get("gps", float("nan"))),
                    # recorded on every arm so B4's in-control statistics can
                    # be taken from A0 on the CLEAN condition
                    "watch_lam": lam_from_consistency(
                        st.edges.get("altitude_baro", (1.0, 0.0))[0]),
                })
                if cusum is not None:
                    z = (row["watch_lam"] - mu0) / sigma0
                    row["cusum_S"] = cusum.update(z, float(st.t))
                    row["cusum_alarm_t"] = cusum.alarm_t
                ticks.append(row)
            next_tick += dt

    return {
        "arm": arm,
        "arm_config": ARMS_MOD.arm_config(arm),
        "arm_config_sha256": ARMS_MOD.arm_config_hash(arm),
        "capture_tag": meta["tag"],
        "condition": meta["condition"],
        "onset_s": meta.get("t_inject_rel_s"),
        "input_sha256": meta["input_sha256"],
        "scenario_signature": meta["scenario_signature"],
        "n_ticks": len(ticks),
        "ticks": ticks,
    }


def clean_cusum_stats(clean_tags):
    """(mu0, sigma0) for B4, from the CLEAN condition only.

    B4's rule is that in-control statistics come from the clean nominal arm and
    never from a fault outcome. Here that means: replay the M0 captures through
    A0 -- an arm with no receiver-health relation at all -- and take the mean
    and standard deviation of the watched lam.
    """
    import statistics
    vals = []
    for tag in clean_tags:
        for r in replay(load_capture(tag), "A0")["ticks"]:
            v = r.get("watch_lam")
            if v is not None:
                vals.append(float(v))
    if len(vals) < 2:
        raise ValueError("not enough clean ticks to standardise B4")
    mu0 = statistics.fmean(vals)
    sigma0 = statistics.pstdev(vals)
    if sigma0 <= 0.0:
        raise ValueError(
            "clean watched lam has zero variance; B4 cannot be standardised "
            "on it, and inventing a scale would not be the frozen detector")
    return (mu0, sigma0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture", required=True)
    ap.add_argument("--arm", required=True, choices=ARMS_MOD.ARMS)
    args = ap.parse_args()
    cap = load_capture(args.capture)
    out = replay(cap, args.arm)
    print(f"  {args.capture} {args.arm}: {out['n_ticks']} ticks, "
          f"input_sha={out['input_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
