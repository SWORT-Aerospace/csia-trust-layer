"""Ingest-path equivalence and an automatic search for semantic divergence.

Items 25, 26, 27. Two questions, one small search.

  EQUIVALENCE   Two ingest paths are semantically equivalent iff the same
                canonical input trace yields the same downstream (A, D,
                provenance, core slot). Divergence means the same vehicle
                condition means different things depending on which decoder
                the deployment happened to use.

  COLLAPSE      Two DISTINCT raw traces that yield the SAME downstream state
                are a semantic-collapse witness. The shortest such pair is the
                cheapest possible demonstration that the vocabulary is too
                small.

The search drives the REAL `ArduPilotAdapter`, the REAL `OnlineTrustLayer` and
the REAL `DiagArm` over a GNSS-only stream. Nothing is modelled: a divergence
found here is a divergence in the implementation.

Alphabet:  V = a 3D fix,  I = a message reporting no fix,  N = no message.
"""

from __future__ import annotations

import csv
import importlib.util
import itertools
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
HZ = 5.0
WARMUP_S = 6.0            # clear of the core's tau > 3 gate
MAX_LEN = 6
ALPHABET = "VIN"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
A = _load("_dual_arms", os.path.join(_HERE, "dual_arms.py"))

BASE = {"mavpackettype": "GPS_RAW_INT", "lat": 473977418, "lon": 85455938,
        "alt": 55000, "eph": 121, "epv": 200, "vel": 0, "cog": 0,
        "fix_type": 6, "satellites_visible": 12, "h_acc": 300,
        "v_acc": 400, "vel_acc": 100, "hdg_acc": 0, "alt_ellipsoid": 55000,
        "yaw": 0}
INVALID = {"fix_type": 1, "satellites_visible": 0, "h_acc": 0, "eph": 65535}


def stream(word, hz=HZ, warmup_s=WARMUP_S):
    """warm-up of valid fixes, then one message per symbol (N emits none)."""
    period = 1.0 / hz
    msgs, t = [], 0.0
    while t < warmup_s:
        m = dict(BASE)
        m["_t_recv"] = round(t, 6)
        m["time_usec"] = int(round(t * 1e6))
        msgs.append(m)
        t += period
    for sym in word:
        if sym != "N":
            m = dict(BASE)
            if sym == "I":
                m.update(INVALID)
            m["_t_recv"] = round(t, 6)
            m["time_usec"] = int(round(t * 1e6))
            msgs.append(m)
        t += period
    # a trailing quiet stretch so the last symbol's consequences are observed
    return msgs, t + 1.0


def semantic_trace(word, arm, tick_hz=25.0):
    """Downstream semantic state per tick, from the real implementation."""
    from csia.runtime.online import OnlineTrustLayer
    msgs, t_end = stream(word)
    now = {"t": 0.0}
    adapter = H.make_adapter(A.policy_for(arm), lambda: now["t"])
    layer = OnlineTrustLayer(tick_hz=tick_hz, field_mode=True)
    diag = A.DiagArm(arm)
    diag.bind_clock(lambda: layer.next_tick)
    layer.diag = diag

    out, next_tick, dt = [], 0.0, 1.0 / tick_hz
    idx = 0

    def record(states):
        for st in states:
            d = next((r for r in reversed(diag.rows)
                      if abs(r.get("t", -1) - st.t) < 1e-9), None) or {}
            out.append((
                round(st.t, 3),
                1 if st.fresh.get("gps") else 0,
                int(layer.slots["gps"].valid),
                round(float(d.get("d_status") or 0.0), 3),
                round(float(d.get("d_hacc") or 0.0), 3),
                (None if d.get("c_status") is None
                 else round(float(d["c_status"]), 3)),
                (None if d.get("c_hacc") is None
                 else round(float(d["c_hacc"]), 3)),
            ))

    def drain(until):
        nonlocal next_tick, idx
        while next_tick <= until:
            now["t"] = next_tick
            smp = adapter.sample(t_mono=next_tick)
            for sensor, ts, chans in adapter.to_core_samples(smp):
                record(layer.ingest(sensor, ts, chans) or [])
            next_tick += dt

    for m in msgs:
        t = float(m["_t_recv"])
        now["t"] = t
        adapter.ingest(m)
        diag.sidecar.observe(m, t)
        drain(t)
        idx += 1
    now["t"] = t_end
    drain(t_end)
    # The tick loop above only emits a state when a core sample is handed
    # over, so the ticks AFTER the last message never materialise -- and that
    # is exactly where a lost fix becomes visible. Flush them.
    record(layer.flush(t_end) or [])
    # only the post-warmup portion carries the word's meaning
    return tuple(r for r in out if r[0] >= WARMUP_S)


def v1_plugin_trace(word, tick_hz=25.0):
    """The SAME word through the committed v1 live-MAVLink decoder."""
    import types

    from csia.runtime.online import OnlineTrustLayer
    from csia.runtime.plugins import map_mavlink

    msgs, t_end = stream(word)
    layer = OnlineTrustLayer(tick_hz=tick_hz, field_mode=True)
    ctx, out, next_tick, dt = {}, [], 0.0, 1.0 / tick_hz

    def drain(until):
        nonlocal next_tick
        while next_tick <= until:
            next_tick += dt

    for m in msgs:
        obj = types.SimpleNamespace(**m)
        obj.get_type = lambda k=m["mavpackettype"]: k
        for sensor, _t, chans in map_mavlink(obj, ctx):
            # the v1 path stamps from the SOURCE clock; the receive time is
            # what makes the two paths comparable, so it is substituted here
            # and nothing else about the decode is touched
            for st in (layer.ingest(sensor, float(m["_t_recv"]), chans) or []):
                out.append((round(st.t, 3),
                            1 if st.fresh.get("gps") else 0,
                            int(layer.slots["gps"].valid),
                            0.0, 0.0, None, None))
    for st in (layer.flush(t_end) or []):
        out.append((round(st.t, 3), 1 if st.fresh.get("gps") else 0,
                    int(layer.slots["gps"].valid), 0.0, 0.0, None, None))
    return tuple(r for r in out if r[0] >= WARMUP_S)


def _semantic_projection(trace):
    """What a path MEANS about the source, with tick alignment removed.

    The two ingest paths stamp a sample differently -- the v1.1 adapter with
    the tick it handed over on, the v1 decoder with the message's own receive
    time -- so a tick-by-tick comparison reports a timestamping difference as
    a semantic one. These three facts are what the paths are being compared
    on, and none of them depends on the stamp.
    """
    if not trace:
        return {"ever_slot_invalid": None, "a_closed_ticks": None,
                "a_ever_closed": None}
    return {
        "ever_slot_invalid": any(r[2] == 0 for r in trace),
        "a_closed_ticks": sum(1 for r in trace if r[1] == 0),
        "a_ever_closed": any(r[1] == 0 for r in trace),
    }


def words(max_len=MAX_LEN):
    for n in range(1, max_len + 1):
        for w in itertools.product(ALPHABET, repeat=n):
            yield "".join(w)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # ---- item 25/26: ingest-path equivalence -----------------------------
    print("INGEST-PATH EQUIVALENCE (v1.1 adapter S0 vs committed v1 "
          "plugins.map_mavlink)")
    path_rows, first_div = [], None
    for w in words(4):
        pa = _semantic_projection(semantic_trace(w, "S0"))
        pb = _semantic_projection(v1_plugin_trace(w))
        same = pa == pb
        if not same and first_div is None:
            first_div = w
        path_rows.append({
            "word": w, "length": len(w),
            "v1_1_adapter_path": "S0_DROP_INVALID",
            "v1_plugins_path": "PROPAGATE_INVALID_ZERO",
            "semantics_identical": same,
            # `ever_slot_invalid` is the SEMANTIC comparison: does this path
            # ever tell the core the sensor is invalid? `a_closed_ticks` also
            # moves with the stamping convention (the v1.1 adapter stamps a
            # sample with the tick it handed it over on, the v1 decoder with
            # the message's own receive time), so a difference there is not by
            # itself evidence of a semantic difference.
            "semantic_divergence": (pa["ever_slot_invalid"]
                                    != pb["ever_slot_invalid"]),
            "tick_count_divergence": (pa["a_closed_ticks"]
                                      != pb["a_closed_ticks"]),
            "v1_1_ever_slot_invalid": pa["ever_slot_invalid"],
            "v1_ever_slot_invalid": pb["ever_slot_invalid"],
            "v1_1_a_closed_ticks": pa["a_closed_ticks"],
            "v1_a_closed_ticks": pb["a_closed_ticks"],
        })
    n_div = sum(1 for r in path_rows if r["semantic_divergence"])
    n_tick = sum(1 for r in path_rows if r["tick_count_divergence"])
    sem_words = [r["word"] for r in path_rows if r["semantic_divergence"]]
    shortest_sem = min(sem_words, key=len) if sem_words else None
    print(f"  {len(path_rows)} words up to length 4")
    print(f"  SEMANTIC divergence (does the path ever mark the slot "
          f"invalid?): {n_div} words; shortest {shortest_sem!r}")
    print(f"  tick-count divergence (includes the stamping convention, not "
          f"attributable on its own): {n_tick} words")

    with open(os.path.join(OUT, "INGEST_PATH_SEMANTIC_EQUIVALENCE.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w_ = csv.DictWriter(fh, fieldnames=list(path_rows[0].keys()))
        w_.writeheader()
        w_.writerows(path_rows)

    # ---- item 27: shortest semantic-collapse witness ---------------------
    print("\nSEMANTIC-COLLAPSE SEARCH (distinct raw words, identical "
          "downstream state)")
    findings = {}
    for arm in ("S0", "S1", "S2c2"):
        seen, collapse = {}, None
        for w in words(MAX_LEN):
            sig = semantic_trace(w, arm)
            key = tuple((r[1], r[2], r[3], r[4], r[5], r[6]) for r in sig)
            if key in seen and seen[key] != w and collapse is None:
                collapse = (seen[key], w)
                break
            seen.setdefault(key, w)
        findings[arm] = {
            "shortest_collapsing_pair": collapse,
            "words_examined": len(seen),
            "collapse_found": collapse is not None,
        }
        print(f"  {arm:<5} shortest collapsing pair: {collapse}")

    # the specific pair the whole study is about: I vs N
    targeted = {}
    for arm in A.ARMS:
        ti = semantic_trace("IIII", arm)
        tn = semantic_trace("NNNN", arm)
        ki = tuple((r[1], r[2], r[3], r[4], r[5], r[6]) for r in ti)
        kn = tuple((r[1], r[2], r[3], r[4], r[5], r[6]) for r in tn)
        targeted[arm] = {
            "receiver_invalid_word": "IIII",
            "no_message_word": "NNNN",
            "downstream_identical": ki == kn,
            "n_ticks_compared": min(len(ki), len(kn)),
        }
    print("\n  'receiver says no fix' vs 'no message at all', by arm:")
    for arm, v in targeted.items():
        print(f"    {arm:<5} downstream identical: "
              f"{v['downstream_identical']}")

    with open(os.path.join(OUT, "COUNTEREXAMPLE_SEARCH_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "COUNTEREXAMPLE_SEARCH_RESULTS",
            "alphabet": {"V": "GPS_RAW_INT with fix_type >= 3",
                         "I": "GPS_RAW_INT with fix_type < 3",
                         "N": "no message delivered"},
            "max_word_length": MAX_LEN,
            "gnss_hz": HZ, "warmup_s": WARMUP_S,
            "method": "the real ArduPilotAdapter, OnlineTrustLayer and "
                      "DiagArm are driven over a GNSS-only stream; nothing "
                      "is modelled",
            "ingest_path_semantic_divergences": n_div,
            "ingest_path_tick_count_divergences": n_tick,
            "shortest_semantically_divergent_word": shortest_sem,
            "divergence_note": "the v1.1 adapter never marks the GPS slot "
                               "invalid; csia/runtime/plugins.py does, for the "
                               "same raw condition and into the same frozen "
                               "core. A tick-count difference alone is not "
                               "evidence of a semantic one: the two paths also "
                               "stamp samples differently.",
            "collapse_by_arm": findings,
            "targeted_invalid_versus_absent": targeted,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
