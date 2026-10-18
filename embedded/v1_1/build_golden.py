"""Phase 4.5 §§20–27: freeze the golden corpus.

Runs only when the Phase 4.5 gates have passed — §20 makes that a
precondition, so this script checks the gate artifacts and refuses otherwise
rather than freezing traces for an architecture still in motion.

Eleven cases. Three tiers, and the tiers do not share a comparison rule:

  TIER A   discrete state, per tick. EXACT. Any difference fails a port.
  TIER B   numeric state, per tick. Compared against the tolerance frozen in
           NUMERIC_EQUIVALENCE_SPEC.md, which was derived BEFORE any C.
  TIER C   ids and content hashes. NOT compared -- they hash the
           implementation, not the behaviour.

    python embedded/v1_1/build_golden.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")
GOLD = os.path.join(_HERE, "golden")
for p in (ROOT, os.path.join(ENG, "phase4"), os.path.join(ENG, "ablation"),
          os.path.join(ENG, "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.aircraft.adapters import get_adapter                     # noqa: E402
from csia.runtime.failsafe import FailsafeConfig, FailsafeLevel    # noqa: E402
from csia.v1_1.eligibility import (EligibilityPolicy,              # noqa: E402
                                   Requirements)
from csia.v1_1.ledger import (AssuranceLedger, LedgerContext,      # noqa: E402
                              snapshot_from, suppression)
from csia.v1_1.sequential import CUSUM_H, CUSUM_K, CusumBank       # noqa: E402
from csia.v1_1.trust_mode import TrustMode                         # noqa: E402
from run_p4b import _observation, _relation_gates, _series         # noqa: E402
from run_p4c import ENDPOINTS, _config_hash                        # noqa: E402
from run_phase3b import MECHANISMS, _hashes                        # noqa: E402
import support as S                                                # noqa: E402

MECHS = [m for m, s in MECHANISMS.items() if s["status"] == "APPLICABLE"]
SENTINELS = ("BATTERY_SENTINEL", "MAG_SENTINEL")
PLATFORM = "ardupilot-derived deterministic simulator"

#: §24, frozen in NUMERIC_EQUIVALENCE_SPEC.md before any C exists.
TOLERANCE = {"trust": 1e-4, "alpha_beta_rel": 1e-4, "smoothed": 1e-3,
             "score": 1e-3, "posterior": 1e-3, "cusum_S": 0.5}

#: Tier B is a trajectory and does not compress; stored every Nth tick with
#: the full-series hash beside it.
TIER_B_STRIDE = 10

#: §26. Trust thresholds a numeric error could carry across, and the node
#: each applies to. Inherited from the FROZEN FailsafeConfig, never restated.
_CFG = FailsafeConfig()
TRUST_BOUNDARIES = (
    ("nav_caution", _CFG.nav_caution, ("gps",)),
    ("heading_caution", _CFG.heading_caution, ("mag",)),
    ("struct_critical", _CFG.struct_critical, ("vibration",)),
    ("power_critical", _CFG.power_critical, ("battery",)),
    ("att_caution", _CFG.att_caution, ("imu0", "imu1")),
    ("att_emergency", _CFG.att_emergency, ("imu0", "imu1")),
)


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _sha_file(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canon(row) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def _write_jsonl(path, rows) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(_canon(r) + "\n")
    return _sha_file(path)


def _series_sha(rows) -> str:
    """Hash of the COMPLETE per-tick series, whatever is stored on disk."""
    h = hashlib.sha256()
    for r in rows:
        h.update(_canon(r).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _rle(rows) -> list:
    """Lossless run-length encoding of a piecewise-constant series.

    Tier A is discrete state: it changes at transitions and is otherwise
    constant, so storing every tick would store the same record hundreds of
    times. Only change-points are written, each carrying the tick index it
    starts at and how many ticks it covers, so the full per-tick series
    reconstructs EXACTLY. A test rebuilds it and compares against the
    full-series hash rather than taking this on trust.
    """
    out = []
    for i, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k != "t"}
        if out and _canon(out[-1]["v"]) == _canon(body):
            out[-1]["n"] += 1
            continue
        out.append({"k": i, "t": row["t"], "n": 1, "v": body})
    return out


def _unrle(encoded, times) -> list:
    """Inverse of `_rle`, used by the reconstruction test."""
    rows = []
    for run in encoded:
        for j in range(run["n"]):
            rows.append({"t": times[run["k"] + j], **run["v"]})
    return rows


# --------------------------------------------------------------- §20 gates
def _preconditions() -> dict:
    checks = {}

    trust_doc = os.path.join(ENG, "TRUST_MODE_FINAL_DECISION.md")
    checks["A_trust_mode_review"] = (
        os.path.exists(trust_doc)
        and "TRUST_MODE_REVIEW:  PASS" in open(trust_doc,
                                               encoding="utf-8").read())

    dep = os.path.join(ROOT, "validation", "v1_1", "deployment")
    stale = os.path.join(dep, "STALENESS_REGRESSION_SUMMARY.json")
    if os.path.exists(stale):
        d = json.load(open(stale, encoding="utf-8"))
        checks["B_staleness"] = bool(d["gate_B_nominal_rate_pass"]
                                     and d["gate_B_jitter_pass"]
                                     and d["gate_C_hard_dropout_pass"])
    else:
        checks["B_staleness"] = False

    reg = os.path.join(dep, "PHASE4_REGRESSION_AFTER_TIMEOUT.json")
    checks["B_phase4_unaffected"] = (
        os.path.exists(reg)
        and json.load(open(reg, encoding="utf-8"))["verdict"]
        == "NO_BEHAVIOURAL_CHANGE")

    cons = os.path.join(ENG, "API_CONSUMER_RESULTS.json")
    if os.path.exists(cons):
        d = json.load(open(cons, encoding="utf-8"))
        checks["C_consumer"] = bool(d["gate_E_consumer_pass"]
                                    and d["gate_F_firewall_pass"])
    else:
        checks["C_consumer"] = False

    checks["numeric_spec_written_before_c"] = (
        os.path.exists(os.path.join(_HERE, "NUMERIC_EQUIVALENCE_SPEC.md"))
        and not [f for _d, _s, fs in os.walk(_HERE) for f in fs
                 if f.endswith((".c", ".h", ".cpp", ".hpp"))])
    return checks


# ------------------------------------------------------------- the cases
def _mechanism_case(mech):
    """Tier A, Tier B and decision margins for one scenario mechanism."""
    td, names, hist, levels, alarms, sup, by_k = _series(mech)
    dec, _s = S.support_series(td, stride=1)
    pol = EligibilityPolicy(Requirements.load())
    ledger = AssuranceLedger(LedgerContext(
        platform=PLATFORM, software_sha="TIER_C_NOT_COMPARED",
        configuration_hash="TIER_C_NOT_COMPARED",
        input_trace_hash=_hashes(td)["raw_trace_sha256"],
        trust_mode=TrustMode.FLAT_V1_1.value))
    bank = CusumBank()

    tier_a, tier_b, margins, events = [], [], [], []
    for k in range(len(td.t)):
        srow = by_k.get(k)
        if srow is None:
            continue
        t = round(float(td.t[k]), 4)
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        trust = {n: float(hist.trust[k, i]) for i, n in enumerate(names)}
        gates = _relation_gates(td, k)
        phys = {n: (float(lam[k]),
                    float(np.asarray(g).flat[min(k, np.asarray(g).size - 1)]))
                for n, (lam, g) in td.physics.items()}
        bank.step(phys, fresh)
        obs = _observation(td, names, hist, levels, alarms, srow, k)
        verdicts = pol.update(obs)
        act, supp, why = suppression(gates, ENDPOINTS, fresh)
        lvl = FailsafeLevel(int(levels[k])).name
        evs = ledger.observe(snapshot_from(
            t=t, levels_name=lvl, support_row=srow, trust=trust, fresh=fresh,
            relation_gates=gates, endpoints=ENDPOINTS,
            sequential_state={"k": CUSUM_K, "h": CUSUM_H,
                              "alarming": sorted(bank.alarming)},
            verdicts=verdicts))
        for ev in evs:
            events.append({"seq": ev.sequence, "t": t,
                           "type": ev.event_type, "subject": ev.subject,
                           "from": ev.previous_state, "to": ev.new_state,
                           "codes": list(ev.reason_codes)})

        # ---- TIER A: discrete, exact ---------------------------------
        tier_a.append({
            "t": t,
            "assurance": lvl,
            "fn": {n: v.state for n, v in sorted(verdicts.items())},
            "codes": {n: sorted(v.reason_codes)
                      for n, v in sorted(verdicts.items())},
            "leader": srow.leader,
            "identifiable": bool(srow.leader_identifiable),
            "ambiguity": srow.ambiguity,
            "support": srow.support_state,
            "nonident": sorted(srow.non_identifiable_against),
            "alarming": sorted(bank.alarming),
            "fresh": {n: fresh[n] for n in sorted(fresh)},
            "missing": {},          # scenario path runs no ingest layer
            "active_rel": sorted(act),
            "supp_rel": sorted(supp),
            "supp_why": dict(sorted(why.items())),
        })

        # ---- TIER B: numeric, compared against the frozen tolerance ---
        tier_b.append({
            "t": t,
            "trust": {n: round(trust[n], 9) for n in sorted(trust)},
            "S": {n: round(v, 9) for n, v in sorted(bank.S.items())},
            "posterior": round(float(srow.posterior), 9),
            "smoothed": [round(float(x), 9) for x in dec.smoothed[k]],
            "score": [round(float(x), 9) for x in dec.score[k]],
        })

        # ---- §26: decision margins ------------------------------------
        row = {"t": t, "near_boundary": False, "reasons": []}
        for name, limit, nodes in TRUST_BOUNDARIES:
            value = max(trust[n] for n in nodes)
            d = abs(value - limit)
            row[f"d_{name}"] = round(d, 9)
            if d <= TOLERANCE["trust"]:
                row["near_boundary"] = True
                row["reasons"].append(f"trust/{name}")
        d_h = min((abs(v - CUSUM_H) for v in bank.S.values()), default=None)
        row["d_cusum_h"] = None if d_h is None else round(d_h, 9)
        if d_h is not None and d_h <= TOLERANCE["cusum_S"]:
            row["near_boundary"] = True
            row["reasons"].append("cusum/h")
        margin = float(dec.score_margin(k))
        row["d_score_margin"] = round(margin, 9)
        if margin <= TOLERANCE["score"]:
            row["near_boundary"] = True
            row["reasons"].append("diagnosis/ranking")
        row["reasons"] = "|".join(row["reasons"])
        margins.append(row)

    return tier_a, tier_b, margins, events, _hashes(td)


def _sentinel_case(name):
    """Tier A for an INGEST-layer case. There is no trust tick here.

    §21 keeps these in the corpus because they exercise R1-R5 rather than the
    trust update, and a port that skipped them would ship the ingest rules
    untested. Their Tier A is the channel outcome, and they have no Tier B --
    stated rather than padded with an empty numeric file.
    """
    adapter = get_adapter("ardupilot")
    rows = []
    if name == "BATTERY_SENTINEL":
        adapter.ingest(_msg("BATTERY_STATUS", time_boot_ms=1000,
                            voltages=[3821, 3817, 3833, 3809] + [65535] * 6,
                            current_battery=500, battery_remaining=76))
        s0 = adapter.sample(t_mono=1.0)
        rows.append(_channel_row(s0, "battery.current", "after_real_reading"))
        adapter.ingest(_msg("BATTERY_STATUS", time_boot_ms=1020,
                            voltages=[3821, 3817, 3833, 3809] + [65535] * 6,
                            current_battery=-1, battery_remaining=76))
        s1 = adapter.sample(t_mono=1.02)
        rows.append(_channel_row(s1, "battery.current", "after_sentinel"))
    else:
        adapter.ingest(_msg("SCALED_IMU", time_boot_ms=1000,
                            xacc=137, yacc=-241, zacc=-993,
                            xgyro=53, ygyro=-27, zgyro=11,
                            xmag=421, ymag=-133, zmag=377))
        s0 = adapter.sample(t_mono=1.0)
        rows.append(_channel_row(s0, "mag.field_ut", "after_real_reading"))
        adapter.ingest(_msg("SCALED_IMU", time_boot_ms=1020,
                            xacc=137, yacc=-241, zacc=-993,
                            xgyro=53, ygyro=-27, zgyro=11,
                            xmag=0, ymag=0, zmag=0))
        s1 = adapter.sample(t_mono=1.02)
        rows.append(_channel_row(s1, "mag.field_ut", "after_sentinel"))
    return rows


class _msg:
    def __init__(self, type_, **fields):
        self._type = type_
        for k, v in fields.items():
            setattr(self, k, v)

    def get_type(self):
        return self._type


def _channel_row(sample, channel, stage) -> dict:
    cv = sample.get(channel)
    return {"stage": stage, "channel": channel,
            "present": cv is not None and cv.usable,
            "quality": None if cv is None else cv.quality.value,
            "missing": None if cv is None or cv.missing is None
            else cv.missing.value}


def main() -> int:
    checks = _preconditions()
    if not all(checks.values()):
        print("STOP: Phase 4.5 preconditions not met (section 20).")
        for k, v in sorted(checks.items()):
            print(f"  {k:34s} {'PASS' if v else 'FAIL'}")
        print("Golden traces are NOT frozen for an architecture still in "
              "motion.")
        return 1

    os.makedirs(GOLD, exist_ok=True)
    cases, near_total, tick_total = [], 0, 0
    all_margins = []

    for mech in MECHS:
        tier_a, tier_b, margins, events, hashes = _mechanism_case(mech)
        a_path = os.path.join(GOLD, f"{mech}.tierA.jsonl")
        b_path = os.path.join(GOLD, f"{mech}.tierB.jsonl")
        e_path = os.path.join(GOLD, f"{mech}.ledger.jsonl")
        encoded = _rle(tier_a)
        a_file_sha = _write_jsonl(a_path, encoded)
        a_sha = _series_sha(tier_a)
        # Tier B is a continuous trajectory, so it does not run-length
        # encode. It is stored at a fixed stride with the FULL-series hash
        # beside it: the stride localises a divergence to a 10-tick window
        # and the hash settles whether the full series matches.
        sampled = tier_b[::TIER_B_STRIDE]
        b_file_sha = _write_jsonl(b_path, sampled)
        b_sha = _series_sha(tier_b)
        e_sha = _write_jsonl(e_path, events)
        near = sum(1 for m in margins if m["near_boundary"])
        near_total += near
        tick_total += len(tier_a)
        for m in margins:
            all_margins.append({"case": mech, **m})
        cases.append({
            "case_id": mech, "kind": "SCENARIO",
            "ticks": len(tier_a), "ledger_events": len(events),
            "input_hashes": hashes,
            "tierA_file": os.path.basename(a_path),
            "tierA_encoding": "run-length, lossless",
            "tierA_runs": len(encoded),
            "tierA_file_sha256": a_file_sha,
            "tierA_series_sha256": a_sha,
            "tierB_file": os.path.basename(b_path),
            "tierB_encoding": f"stride {TIER_B_STRIDE}",
            "tierB_rows_stored": len(sampled),
            "tierB_file_sha256": b_file_sha,
            "tierB_series_sha256": b_sha,
            "ledger_file": os.path.basename(e_path), "ledger_sha256": e_sha,
            "near_boundary_ticks": near,
        })
        print(f"  {mech:20s} {len(tier_a):5d} ticks  "
              f"{len(events):3d} events  near-boundary {near}")

    for name in SENTINELS:
        rows = _sentinel_case(name)
        a_path = os.path.join(GOLD, f"{name}.tierA.jsonl")
        a_sha = _write_jsonl(a_path, rows)
        cases.append({
            "case_id": name, "kind": "INGEST",
            "ticks": len(rows), "ledger_events": 0,
            "input_hashes": {"fixture": "adapter message pair, R1 supersession"},
            "tierA_file": os.path.basename(a_path),
            "tierA_encoding": "verbatim",
            "tierA_runs": len(rows),
            "tierA_file_sha256": a_sha, "tierA_series_sha256": a_sha,
            "tierB_file": None, "tierB_encoding": None,
            "tierB_rows_stored": 0,
            "tierB_file_sha256": None, "tierB_series_sha256": None,
            "ledger_file": None, "ledger_sha256": None,
            "near_boundary_ticks": 0,
            "note": "ingest-layer case: exercises R1-R5, has no trust tick "
                    "and therefore no Tier B",
        })
        print(f"  {name:20s} {len(rows):5d} rows   (ingest, no Tier B)")

    # ---- §26 audit -------------------------------------------------------
    import csv as _csv
    audit = os.path.join(_HERE, "DECISION_MARGIN_AUDIT.csv")
    fields = ["case", "t", "near_boundary", "reasons", "d_cusum_h",
              "d_score_margin"] + [f"d_{n}" for n, _v, _x in TRUST_BOUNDARIES]
    with open(audit, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in all_margins:
            if row["near_boundary"]:
                w.writerow(row)

    # ---- §22 frozen inputs + §27 manifest --------------------------------
    frozen_inputs = {}
    for rel in ("engineering/v1_1/FUNCTION_REQUIREMENTS.yaml",
                "engineering/v1_1/REASON_CODES.yaml",
                "engineering/v1_1/csia_output_v1_1.schema.json",
                "csia/v1_1/trust_mode.py", "csia/v1_1/sequential.py",
                "csia/v1_1/eligibility.py", "csia/v1_1/ledger.py",
                "csia/v1_1/advisory.py", "csia/v1_1/staleness.py",
                "csia/scenarios.py", "csia/diagnosis/bayes.py",
                "csia/trust_engine/engine.py", "csia/runtime/failsafe.py"):
        frozen_inputs[rel] = _sha_file(os.path.join(ROOT, rel))

    manifest = {
        "artifact": "GOLDEN_CORPUS_MANIFEST",
        "generation_command": "python embedded/v1_1/build_golden.py",
        "source_sha": _git("rev-parse", "HEAD"),
        "frozen_v1_tag": "csia-v1.0-research-final",
        "config_hash": _config_hash(),
        "trust_mode": TrustMode.FLAT_V1_1.value,
        "sequential": {"k": CUSUM_K, "h": CUSUM_H},
        "output_schema_version": "1.1.0",
        "preconditions": checks,
        "frozen_input_hashes": frozen_inputs,
        "tier_a": "EXACT -- any difference on any tick fails a port",
        "tier_b": "compared against NUMERIC_EQUIVALENCE_SPEC.md",
        "tier_b_tolerance": TOLERANCE,
        "tier_c": "event ids and content hashes -- NOT compared",
        "cases": cases,
        "case_count": len(cases),
        "total_ticks": tick_total,
        "near_boundary_ticks": near_total,
        "near_boundary_fraction": (round(near_total / tick_total, 6)
                                   if tick_total else 0.0),
        "decision_margin_audit": "DECISION_MARGIN_AUDIT.csv",
    }
    man_path = os.path.join(GOLD, "MANIFEST.json")
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    corpus_sha = _sha_text("".join(
        sorted(c["tierA_series_sha256"] + (c["tierB_series_sha256"] or "")
               for c in cases)))
    with open(os.path.join(GOLD, "CORPUS_SHA256"), "w",
              encoding="utf-8") as fh:
        fh.write(corpus_sha + "\n")

    print(f"\ncases={len(cases)} ticks={tick_total} "
          f"near-boundary={near_total} "
          f"({manifest['near_boundary_fraction']:.4%})")
    print("corpus sha256:", corpus_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
