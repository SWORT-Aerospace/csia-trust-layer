#!/usr/bin/env python3
"""Phase 8: configuration-epoch adversarial variants. NON-CONFIRMATORY.
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/epoch_adversarial.py

Each variant perturbs the frozen E1 stream (`transition_study.stream`, the
shadow study's design, unchanged) in one way an integration could get
wrong, and runs 2.1.1 (all revisions) over it with the implemented epoch
rule. Every record carries a TRUE configuration identity, set by the variant
independently of what the record is stamped with. A record is VALID at a
tick iff its true identity equals the true identity in force then.

Per variant:
  stale_admitted       record-ticks admitted although INVALID
  valid_withheld       record-ticks not admitted although VALID
  stale_position_ticks / missed_position_ticks / attribution grades
                       from the E1 truth (`transition_study.grade`)

Variants:
  BASE                    E1 as designed (one switch at tick 25)
  RAPID_SWITCHING         switches at 25, 26, 27, 28
  SWITCH_BACK             lane 0 -> 1 at 25 -> 0 at 30, counter stamps
  SWITCH_BACK_LANE_ID     the same, stamped with the lane id (the rejected
                          design: shown to price it)
  EARLY_NEW_EPOCH         a lane-1 record arrives at tick 24, before the
                          context has seen the transition
  LATE_OLD_EPOCH          a lane-0 stability record arrives late, at 26-28
  DUPLICATE_OLD           the latched lane-0 record arrives twice, 25-33
  MISSING_TRANSITION      the context never sees the switch; lane-1 records
                          carry epoch 1
  MISSING_TRANSITION_SILENT  the context never sees the switch and no record
                          reveals it (only the latched record is stamped)
  MALFORMED_EPOCH         the latched record's stamp is malformed
  RESTART_COUNTER_ONLY    the estimator restarts at 28 and its counter
                          resets to 0; stamps are the counter alone
  RESTART_COMPOSITE       the same restart; stamps are (boot, counter)
  ROLLOVER_UINT8          an 8-bit counter at 255 wraps to 0 at the switch
  UNRELATED_TRANSITION    the gyro device id changes at tick 40; only the
                          IMU's records depend on it

Writes EPOCH_ADVERSARIAL_RESULTS.json.
"""
from __future__ import annotations

import sys
from dataclasses import replace

import revision_common as RC

import semantic_probe as P  # noqa: E402
import transition_study as T  # noqa: E402

from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import Corrections, EpochContext, SemanticCore21  # noqa: E402

OUT = RC.HERE / "EPOCH_ADVERSARIAL_RESULTS.json"
KEY = "ekf2.selector.instance_changed_count"
GYRO = "sensor_selection.gyro_device_id"
DEADLINE = "COMPUTE/state_estimator:compute.deadline_met"
STABILITY = "COMPUTE/state_estimator:compute.stability"
IMU = "SENSOR/source.imu0"


def _rid(r):
    return f"{r.domain}/{r.component}:{r.relation}"


def _stamp(r, value, key=KEY):
    prov = dict(r.provenance or {})
    ce = dict(prov.get("config_epoch") or {}) if isinstance(prov.get("config_epoch"), dict) else {}
    ce[key] = value
    prov["config_epoch"] = ce
    return replace(r, provenance=prov)


def variant(base, name):
    """-> [(t, records, context, truth)], truth = {id(record): valid}."""
    out = []
    for t, lane, recs, meta in base:
        if name in ("RAPID_SWITCHING",):
            count = 0 if t < 25 else min(t - 24, 4)
        elif name.startswith("SWITCH_BACK"):
            count = 0 if t < 25 else (1 if t < 30 else 2)
        else:
            count = lane
        lane_id = {0: 0, 1: 1, 2: 0}.get(count, count) if name.startswith("SWITCH_BACK") else count
        rows, truth = [], {}
        ctx = {KEY: count}
        events = {KEY: f"instance_changed_count -> {count}"} if count else {}
        for r in recs:
            k = _rid(r)
            content, epoch, _valid = meta.get(k, (t, None, True))
            true_id = None
            if epoch is not None:
                # what lane/epoch generated the content, in this variant
                if k == DEADLINE:
                    true_id = 0 if content < 25 else count
                else:
                    true_id = count
            stamp = true_id
            if name == "SWITCH_BACK_LANE_ID" and true_id is not None:
                stamp = {0: 0, 1: 1, 2: 0}.get(true_id, true_id)
            if name == "MALFORMED_EPOCH" and k == DEADLINE:
                stamp = "lane0"
            if name == "ROLLOVER_UINT8" and true_id is not None:
                stamp = (255 + true_id) % 256
            if name.startswith("RESTART"):
                boot = 1 if t >= 28 else 0
                if true_id is not None:
                    gen_boot = 0 if (k == DEADLINE and content < 28) else boot
                    true_id = (gen_boot, 0 if gen_boot else true_id)
                    stamp = true_id if name == "RESTART_COMPOSITE" else true_id[1]
            if name == "MISSING_TRANSITION_SILENT" and k != DEADLINE:
                stamp = None
            if stamp is not None:
                r = _stamp(r, list(stamp) if isinstance(stamp, tuple) else stamp)
            if name == "UNRELATED_TRANSITION" and r.component == "source.imu0":
                r = _stamp(r, 1 if t < 40 else 2, GYRO)
            current = count
            if name.startswith("RESTART"):
                current = (1 if t >= 28 else 0, 0 if t >= 28 else count)
            truth[id(r)] = (true_id is None) or (true_id == current)
            rows.append(r)
        if name == "EARLY_NEW_EPOCH" and t == 24:
            s = [r for r in rows if _rid(r) == STABILITY][0]
            early = _stamp(replace(s, source="ekf2_lane1_early",
                                   observation_state=OS.NOMINAL, reason_codes=()), 1)
            rows.append(early)
            truth[id(early)] = False
        if name == "LATE_OLD_EPOCH" and 26 <= t <= 28:
            s = [r for r in rows if _rid(r) == STABILITY][0]
            late = _stamp(replace(s, source="ekf2_lane0_late",
                                  observation_state=OS.DEGRADED,
                                  reason_codes=("COMPUTE_QUEUE_BACKLOG",)), 0)
            rows.append(late)
            truth[id(late)] = False
        if name == "DUPLICATE_OLD" and 25 <= t <= 33:
            d = [r for r in rows if _rid(r) == DEADLINE][0]
            dup = replace(d, source="ekf2_lane0_replay")
            rows.append(dup)
            truth[id(dup)] = truth[id(d)]
        if name in ("MISSING_TRANSITION", "MISSING_TRANSITION_SILENT"):
            ctx, events = {KEY: 0}, {}
        if name == "SWITCH_BACK_LANE_ID":
            ctx = {KEY: lane_id}
        if name == "ROLLOVER_UINT8":
            ctx = {KEY: (255 + count) % 256}
        if name.startswith("RESTART"):
            cur = (1 if t >= 28 else 0, 0 if t >= 28 else count)
            ctx = {KEY: list(cur) if name == "RESTART_COMPOSITE" else cur[1]}
            if t >= 28:
                events = {KEY: "estimator restarted at tick 28"}
        if name == "UNRELATED_TRANSITION":
            ctx[GYRO] = 1 if t < 40 else 2
            if t >= 40:
                events = dict(events, **{GYRO: "gyro device id changed at tick 40"})
        out.append((t, tuple(rows), EpochContext(ctx, events), truth))
    return out


NAMES = ("BASE", "RAPID_SWITCHING", "SWITCH_BACK", "SWITCH_BACK_LANE_ID",
         "EARLY_NEW_EPOCH", "LATE_OLD_EPOCH", "DUPLICATE_OLD", "MISSING_TRANSITION",
         "MISSING_TRANSITION_SILENT", "MALFORMED_EPOCH", "RESTART_COUNTER_ONLY",
         "RESTART_COMPOSITE", "ROLLOVER_UINT8", "UNRELATED_TRANSITION")


def main():
    design = T.load_design()
    base = T.stream(design)
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    core = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True)
    pre = SemanticCore21.from_engine(engine, trace=True)
    out = {"harness": "semantic_core_2_1_revision_epoch_adversarial",
           "design_sha256": T.FROZEN_SHA256,
           "label": "NON-CONFIRMATORY; perturbations of the frozen E1 stream",
           "variants": {}}
    for name in NAMES:
        row = {"stale_admitted": 0, "valid_withheld": 0, "stale_position_ticks": 0,
               "missed_position_ticks": 0, "attribution": {}, "reasons": {},
               "pre_2_1_0_stale_position_ticks": 0, "examples": []}
        for t, recs, ctx, truth in variant(base, name):
            tr = core.reason(recs, ctx)
            bad = {}
            for e in tr.admission["inadmissible"]:
                bad.setdefault((e["record"], e["source"]), []).append(e)
                row["reasons"][e["reason"]] = row["reasons"].get(e["reason"], 0) + 1
            for r in recs:
                withheld = bool(bad.get((_rid(r), r.source)))
                valid = truth[id(r)]
                row["stale_admitted"] += int(not valid and not withheld)
                row["valid_withheld"] += int(valid and withheld)
            ag, pos, should = T.grade(design, t, tr)
            row["attribution"][ag] = row["attribution"].get(ag, 0) + 1
            row["stale_position_ticks"] += int(bool(pos) and not should)
            row["missed_position_ticks"] += int(should and not pos)
            _a, ppos, _s = T.grade(design, t, pre.reason(recs))
            row["pre_2_1_0_stale_position_ticks"] += int(bool(ppos) and not should)
            if bad and len(row["examples"]) < 3:
                row["examples"].append({"t": t, "inadmissible": [
                    {k: e[k] for k in ("record", "source", "key", "evidence_epoch",
                                       "current_epoch", "reason", "action",
                                       "transition_event")}
                    for v in bad.values() for e in v]})
        out["variants"][name] = row
        print(name, {k: row[k] for k in ("stale_admitted", "valid_withheld",
                                         "stale_position_ticks", "missed_position_ticks",
                                         "attribution", "reasons",
                                         "pre_2_1_0_stale_position_ticks")})
    RC.write_json(OUT, out)


if __name__ == "__main__":
    sys.exit(main())
