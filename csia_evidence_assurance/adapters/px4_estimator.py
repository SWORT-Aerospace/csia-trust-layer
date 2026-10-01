"""PX4 EKF2's own status as evidence, and as the configuration epoch.

**No estimator integrity logic is implemented here.** The adapter reads what
EKF2 already publishes (PX4 547e2ca, `src/modules/ekf2/EKF2.cpp`
`PublishStatus`, lines 1943-2017, read at V4) and says what each field means:

| field | used for |
|---|---|
| `pos_test_ratio`, `vel_test_ratio`, `hgt_test_ratio`, `hdg_test_ratio` | the four claims. EKF2 publishes the square root of the low-pass filtered innovation test ratio, NaN when no aiding of that kind is fused (`ekf_helper.cpp` lines 412-558). Above 1.0 the filtered innovation is outside EKF2's own gate |
| `control_mode_flags` | which aiding sources are fused (the claim's lineage, and its aiding context epoch); tilt and yaw alignment (producer health) |
| `filter_fault_flags` | producer health: bits 0-15 (numerical fusion errors, bad delta-velocity bias) are faults of the estimator itself |
| `time_slip` | producer health: an increase means the EKF's inertial update fell behind system time |
| `reset_count_*` (uint8) | context epochs, unwrapped |
| `gyro_device_id`, `accel_device_id`, `baro_device_id`, `mag_device_id` | the lineage roots, and the IMU context epoch |
| `estimator_selector_status.instance_changed_count` | the lane epoch, when the selector runs |
| `timestamp_sample` / `timestamp` | content time (EKF2's delayed fusion horizon) / produced time |

Not used: `health_flags` and `timeout_flags` (legacy LPE fields that EKF2
does not set: no assignment in `EKF2.cpp`), and the GPS check flags (a GNSS
quality statement this adapter has no claim for).

WHAT A CLAIM SAYS, AND DOES NOT
-------------------------------
`INNOVATION_<POS|VEL|HGT|HDG>` on COMPUTE/state_estimator:
- **NOMINAL:** EKF2's filtered test ratio for that aiding kind is at or below
  its gate;
- **VIOLATED:** it is above the gate;
- **NOT_APPLICABLE:** no aiding of that kind is fused, so there is no
  innovation to test.

A failed innovation test says the estimator and an aiding sensor disagree.
It does not say which is wrong: the IMU prediction, the aiding sensor, or
the model. The record is therefore `attributable=False`.

PRODUCER HEALTH
---------------
| condition | health |
|---|---|
| tilt or yaw not yet aligned (`control_mode_flags` bits 0, 1) | UNAVAILABLE |
| any of `filter_fault_flags` bits 0-15 | FAULTED |
| `time_slip` increased since this lane's previous output | DEGRADED |
| otherwise | VALID |

CONFIGURATION EPOCHS (2.1.1's R-3, reused)
-------------------------------------------
The adapter publishes five kinds of epoch, all monotonic counters (R-3: a
counter, never an id, so a switch back does not re-admit old evidence):

| key | advances when | a dependency of the claims? |
|---|---|---|
| `ekf2.selector.instance_changed_count` | the selector switches lane | **yes** |
| `ekf2.imu.change_count` | the primary lane's gyro or accel device id changes | no: context only |
| `ekf2.aiding.<pos|vel|hgt|hdg>` | the set of fused sources for that claim changes (for example magnetic heading to 3-axis magnetometer fusion) | no: context only |
| `ekf2.reset.<counter>` | the matching uint8 reset counter increments (unwrapped) | no: context only |

**Why only the lane is a dependency.** A dependency protects evidence only
if the configuration can change before the evidence is replaced.
- The lane counter can: the selector publishes the switch at once
  (`EKF2Selector.cpp` lines 110-140), and the new lane's status follows. Every
  held output of the old lane is then stale for that interval.
- The other counters cannot: they arrive in the same `estimator_status`
  message as the claims they would guard, so evidence and context always
  agree. As dependencies they would protect nothing.

They are still published as context. The timeline shows them as
configuration changes, and a producer whose output depends on the
estimator's state can declare them.

**The lane epoch.**
- When the selector does not run (`SENS_IMU_MODE` != 0: `EKF2.cpp` lines
  2995-3060 start it only in multi mode), the lane cannot change and the
  epoch is 0 by construction.
- When the selector should run but its topic is not logged, the key is left
  out of the stamp. The evidence is refused (MISSING_EPOCH), with a coverage
  notice.

So a lane switch makes every held output of the old lane stale, the new
lane's outputs are admitted, and evidence that does not depend on the
estimator is untouched.

Only outputs of the lane that is primary when they are published are
emitted; another lane's outputs are not the vehicle's estimate.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState

from ..envelope import EvidenceEnvelope
from ..health import ProducerHealth
from ..lineage import Lineage

PRODUCER_ID = "px4:ekf2.estimator_status"
CONTRACT_VERSION = "px4-ekf2-status-1"
#: The PX4 build this contract was written against (`ver_sw`, first 7).
PX4_VERSION = "547e2ca"
DOMAIN, COMPONENT = "COMPUTE", "state_estimator"
LANE_KEY = "ekf2.selector.instance_changed_count"
IMU_KEY = "ekf2.imu.change_count"
GATE = 1.0
#: `filter_fault_flags` bits that are faults of the estimator's own computation.
FAULT_MASK = 0xFFFF
TILT_ALIGN, YAW_ALIGN = 0, 1

#: claim -> (status field, aiding kind, {control_mode bit: lineage root}, reset fields)
CLAIMS = {
    "INNOVATION_POS": ("pos_test_ratio", "pos",
                       {2: "sensor:gnss", 12: "sensor:vision", 38: "sensor:aux_global_position"},
                       ("reset_count_pos_ne",)),
    "INNOVATION_VEL": ("vel_test_ratio", "vel",
                       {44: "sensor:gnss", 24: "sensor:vision", 3: "sensor:optical_flow"},
                       ("reset_count_vel_ne", "reset_count_vel_d")),
    "INNOVATION_HGT": ("hgt_test_ratio", "hgt",
                       {9: "sensor:baro.{baro}", 11: "sensor:gnss", 10: "sensor:range",
                        14: "sensor:vision"},
                       ("reset_count_pod_d",)),
    "INNOVATION_HDG": ("hdg_test_ratio", "hdg",
                       {4: "sensor:mag.{mag}", 5: "sensor:mag.{mag}", 22: "sensor:gnss",
                        13: "sensor:vision"},
                       ("reset_count_quat",)),
}
#: `control_mode_flags` bit names (EstimatorStatus.msg, PX4 547e2ca), for transition text.
FUSION_NAMES = {2: "GNSS position", 3: "optical flow", 4: "magnetic heading",
                5: "3-axis magnetometer", 9: "barometer height", 10: "range-finder height",
                11: "GNSS height", 12: "vision position", 13: "vision yaw", 14: "vision height",
                22: "GNSS yaw", 24: "vision velocity", 38: "auxiliary global position",
                44: "GNSS velocity"}
RESET_NAMES = {"reset_count_pos_ne": "horizontal position", "reset_count_vel_ne": "horizontal velocity",
               "reset_count_vel_d": "vertical velocity", "reset_count_pod_d": "vertical position",
               "reset_count_quat": "attitude (quaternion)"}
STATUS_FIELDS = sorted({"timestamp", "timestamp_sample", "control_mode_flags",
                        "filter_fault_flags", "time_slip", "gyro_device_id",
                        "accel_device_id", "baro_device_id", "mag_device_id"}
                       | {c[0] for c in CLAIMS.values()}
                       | {r for c in CLAIMS.values() for r in c[3]})


def relation(claim: str) -> str:
    return f"estimator.innovation.{CLAIMS[claim][1]}"


def claim_keys(claim: str) -> tuple:
    """The configuration epochs a claim depends on (see the module docstring)."""
    return (LANE_KEY,)


def context_keys(claim: str) -> tuple:
    """Every epoch the adapter publishes about a claim's configuration."""
    _f, kind, _bits, resets = CLAIMS[claim]
    return (LANE_KEY, IMU_KEY, f"ekf2.aiding.{kind}") + tuple(f"ekf2.reset.{r}" for r in resets)


def _bit(flags, b) -> bool:
    return bool((int(flags) >> b) & 1)


@dataclass
class EstimatorLog:
    """What the adapter reads from one flight log. Times in microseconds.

    `status` is `{instance: {field: array}}` sorted by `timestamp`;
    `selector` is `{"timestamp", "primary_instance",
    "instance_changed_count"}` arrays, or None when not logged."""

    status: dict
    selector: dict | None
    params: dict
    ver_sw: str
    t0_us: int
    origin: dict = field(default_factory=dict)

    @classmethod
    def from_ulog(cls, path) -> "EstimatorLog":
        from pyulog import ULog
        path = Path(path)
        u = ULog(str(path), ["estimator_status", "estimator_selector_status"])
        status, selector = {}, None
        for d in u.data_list:
            if d.name == "estimator_status":
                status[d.multi_id] = {k: np.asarray(d.data[k]) for k in STATUS_FIELDS}
            elif d.name == "estimator_selector_status" and d.multi_id == 0:
                selector = {k: np.asarray(d.data[k]) for k in
                            ("timestamp", "primary_instance", "instance_changed_count")}
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        return cls(status, selector, dict(u.initial_parameters),
                   str(u.msg_info_dict.get("ver_sw", "")), int(u.start_timestamp),
                   {"file": path.name, "sha256": h})

    def to_npz(self, path) -> None:
        """A compressed extract of exactly what the adapter reads, so an
        analysis is reproducible without the raw ULog."""
        import json as _json
        arrays = {f"status__{i}__{k}": v for i, d in self.status.items() for k, v in d.items()}
        if self.selector is not None:
            arrays.update({f"selector__{k}": v for k, v in self.selector.items()})
        meta = {"params": {k: self.params[k] for k in sorted(self.params)
                           if k.startswith(("SENS_", "EKF2_", "SYS_"))},
                "ver_sw": self.ver_sw, "t0_us": self.t0_us, "origin": self.origin}
        np.savez_compressed(path, __meta__=np.array(_json.dumps(meta, sort_keys=True)), **arrays)

    @classmethod
    def from_npz(cls, path) -> "EstimatorLog":
        import json as _json
        z = np.load(path, allow_pickle=False)
        meta = _json.loads(str(z["__meta__"]))
        status, selector = {}, None
        for k in z.files:
            if k.startswith("status__"):
                _, inst, field_ = k.split("__", 2)
                status.setdefault(int(inst), {})[field_] = z[k]
            elif k.startswith("selector__"):
                selector = selector or {}
                selector[k.split("__", 1)[1]] = z[k]
        origin = dict(meta["origin"], extract=Path(path).name)
        return cls(status, selector, meta["params"], meta["ver_sw"], meta["t0_us"], origin)

    def multi_mode(self) -> bool:
        return int(self.params.get("SENS_IMU_MODE", 1)) == 0


class EstimatorProducer:
    """Replays an `EstimatorLog` as the PX4 estimator producer.

    `step(t)` (seconds from log start) returns the envelopes of the primary
    lane's latest output published at or before t, if it is new since the
    previous step; `context(t)` returns the configuration epochs in force
    at t, and the transitions since the previous call."""

    def __init__(self, log: EstimatorLog):
        self.log = log
        self.version = (log.ver_sw or "")[:7]
        self.notices = []
        self._lane_mode = "STRUCTURAL_0"
        if log.multi_mode():
            self._lane_mode = "SELECTOR" if log.selector is not None else "NOT_LOGGED"
        if self._lane_mode == "NOT_LOGGED":
            self.notices.append({
                "producer_id": PRODUCER_ID, "source": "COMPUTE/state_estimator",
                "available": False,
                "why": "SENS_IMU_MODE=0 (EKF2 selector runs) but estimator_selector_status is "
                       "not logged: the lane epoch cannot be determined, so estimator evidence "
                       "is refused (MISSING_EPOCH)"})
        self._stream = self._primary_stream()
        self._last = None
        self._ctx_prev: dict = {}

    # ------------------------------------------------------------- stream
    def _lane_at(self, ts_us):
        """(primary instance, instance_changed_count) at publication time."""
        if self._lane_mode == "STRUCTURAL_0":
            return min(self.log.status), 0
        if self._lane_mode == "NOT_LOGGED":
            return min(self.log.status), None
        s = self.log.selector
        i = int(np.searchsorted(s["timestamp"], ts_us, side="right")) - 1
        if i < 0:
            return None, None
        return int(s["primary_instance"][i]), int(s["instance_changed_count"][i])

    def _primary_stream(self) -> list:
        """Every output of the lane that was primary when it was published,
        in publication order, with its epochs and health."""
        rows = []
        for inst, d in self.log.status.items():
            for j in range(len(d["timestamp"])):
                rows.append((int(d["timestamp"][j]), inst, j))
        rows.sort()
        out, prev_dev, imu_n = [], None, 0
        aid_prev, aid_n = {}, {k: 0 for k in ("pos", "vel", "hgt", "hdg")}
        reset_prev, reset_n = {}, {}
        slip_prev = {}
        for ts, inst, j in rows:
            lane, count = self._lane_at(ts)
            if lane != inst:
                continue
            d = self.log.status[inst]
            row = {k: d[k][j] for k in STATUS_FIELDS}
            dev = (int(row["gyro_device_id"]), int(row["accel_device_id"]))
            if prev_dev is not None and dev != prev_dev:
                imu_n += 1
            prev_dev = dev
            flags = int(row["control_mode_flags"])
            for claim, (_f, kind, bits, resets) in CLAIMS.items():
                aid = tuple(b for b in sorted(bits) if _bit(flags, b))
                if kind in aid_prev and aid != aid_prev[kind]:
                    aid_n[kind] += 1
                aid_prev[kind] = aid
                for r in resets:
                    v = int(row[r])
                    if (inst, r) in reset_prev:
                        reset_n[r] = reset_n.get(r, 0) + (v - reset_prev[(inst, r)]) % 256
                    else:
                        reset_n.setdefault(r, 0)
                    reset_prev[(inst, r)] = v
            epochs = {IMU_KEY: imu_n}
            if count is not None:
                epochs[LANE_KEY] = count
            epochs.update({f"ekf2.aiding.{k}": n for k, n in aid_n.items()})
            epochs.update({f"ekf2.reset.{r}": n for r, n in reset_n.items()})
            slip = float(row["time_slip"])
            health, why = ProducerHealth.VALID, ""
            if not (_bit(flags, TILT_ALIGN) and _bit(flags, YAW_ALIGN)):
                health, why = ProducerHealth.UNAVAILABLE, "FILTER_NOT_ALIGNED"
            elif int(row["filter_fault_flags"]) & FAULT_MASK:
                health = ProducerHealth.FAULTED
                why = f"FILTER_FAULT_FLAGS:0x{int(row['filter_fault_flags']) & FAULT_MASK:04x}"
            elif inst in slip_prev and slip > slip_prev[inst] + 1e-9:
                health, why = ProducerHealth.DEGRADED, "TIME_SLIP_INCREASED"
            slip_prev[inst] = slip
            out.append({"ts": ts, "inst": inst, "row": row, "epochs": epochs,
                        "aiding": dict(aid_prev), "health": health, "health_why": why})
        return out

    def _sec(self, us) -> float:
        return (int(us) - self.log.t0_us) * 1e-6

    def _index_at(self, t) -> int:
        us = self.log.t0_us + int(round(t * 1e6))
        lo, hi = 0, len(self._stream)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._stream[mid]["ts"] <= us:
                lo = mid + 1
            else:
                hi = mid
        return lo - 1

    # ------------------------------------------------------------- outputs
    def envelopes_of(self, item) -> list:
        row, flags = item["row"], int(item["row"]["control_mode_flags"])
        base = {f"sensor:gyro.{int(row['gyro_device_id'])}",
                f"sensor:accel.{int(row['accel_device_id'])}", "model:ekf2"}
        out = []
        for claim, (fld, kind, bits, _resets) in sorted(CLAIMS.items()):
            ratio = float(row[fld])
            roots = set(base)
            for b, root in bits.items():
                if _bit(flags, b):
                    roots.add(root.format(baro=int(row["baro_device_id"]),
                                          mag=int(row["mag_device_id"])))
            if not math.isfinite(ratio):
                st, app, codes = (ObservationState.NOT_APPLICABLE, Applicability.NOT_APPLICABLE,
                                  (f"NO_{kind.upper()}_AIDING_FUSED",))
            elif ratio <= GATE:
                st, app, codes = ObservationState.NOMINAL, Applicability.APPLICABLE, ()
            else:
                st, app, codes = (ObservationState.VIOLATED, Applicability.APPLICABLE,
                                  ("INNOVATION_TEST_RATIO_OVER_GATE",))
            rec = EvidenceRecord(
                domain=DOMAIN, component=COMPONENT, relation=relation(claim),
                source=PRODUCER_ID, observation_state=st, applicability=app,
                reason_codes=codes,
                measured_value=ratio if math.isfinite(ratio) else None,
                expected_value=GATE,
                expected_relation="EKF2's filtered innovation test ratio at or below its gate",
                attributable=False, detail={"instance": item["inst"]})
            stamp = {k: item["epochs"][k] for k in claim_keys(claim) if k in item["epochs"]}
            out.append(EvidenceEnvelope(
                producer_id=PRODUCER_ID, producer_version=self.version,
                contract_version=CONTRACT_VERSION, claim=claim, record=rec,
                lineage=Lineage.of(*roots),
                content_time=self._sec(row["timestamp_sample"]),
                producer_health=item["health"], produced_time=self._sec(row["timestamp"]),
                config_epoch=stamp,
                detail={"health_why": item["health_why"]} if item["health_why"] else {}))
        return out

    def step(self, t) -> list:
        i = self._index_at(t)
        if i < 0 or i == self._last:
            return []
        self._last = i
        return self.envelopes_of(self._stream[i])

    def context(self, t) -> tuple:
        """-> ({key: epoch} in force at t, {key: transition description})."""
        i = self._index_at(t)
        cur = dict(self._stream[i]["epochs"]) if i >= 0 else {}
        if self._lane_mode == "SELECTOR":
            _lane, count = self._lane_at(self.log.t0_us + int(round(t * 1e6)))
            if count is not None:
                cur[LANE_KEY] = count
        aiding = self._stream[i]["aiding"] if i >= 0 else {}
        events = {k: self._describe(k, self._ctx_prev[k], v, aiding)
                  for k, v in sorted(cur.items())
                  if k in self._ctx_prev and self._ctx_prev[k] != v}
        self._ctx_prev = dict(cur)
        self._aiding_prev = aiding
        return cur, events

    def _describe(self, key, old, new, aiding) -> str:
        """A transition in PX4's own terms."""
        if key.startswith("ekf2.aiding."):
            kind = key.rsplit(".", 1)[1]
            names = lambda bits: (", ".join(FUSION_NAMES.get(b, f"bit {b}") for b in bits)  # noqa: E731
                                  or "none")
            before = getattr(self, "_aiding_prev", {}).get(kind, ())
            return (f"{kind} aiding fused: {names(before)} -> {names(aiding.get(kind, ()))} "
                    f"(control_mode_flags)")
        if key.startswith("ekf2.reset."):
            f = key.rsplit(".", 1)[1]
            n = new - old if isinstance(new, int) and isinstance(old, int) else "?"
            return f"EKF2 {RESET_NAMES.get(f, f)} reset ({f} +{n}, unwrapped total {new})"
        if key == IMU_KEY:
            return f"primary IMU device changed (change {new})"
        if key == LANE_KEY:
            return f"EKF2 selector changed primary lane (instance_changed_count {old} -> {new})"
        return f"{key} {old} -> {new}"

    def coverage_notices(self) -> list:
        return list(self.notices)
