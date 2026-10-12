"""Configuration-epoch admission (revision R-3, CONFIG_EPOCH). New in 2.1.1.

The smallest piece of evidence admissibility: **evidence generated under one
configuration is not admitted once the configuration it depends on has
changed.** Nothing else about admissibility (age, freshness, producer
contracts, provenance graphs) is here.

WHAT A RECORD DECLARES
----------------------
A producer whose output depends on a configuration stamps the record:

    provenance["config_epoch"] = {"<epoch key>": <epoch value>, ...}

- The key names the configuration, for example
  `ekf2.selector.instance_changed_count`.
- The value is the epoch in force when the content was generated: a
  non-negative int, or a tuple of them for a composite epoch such as
  (producer boot count, instance_changed_count).
- A record with no `config_epoch` depends on no configuration and is never
  touched here. A sensor's own health record, for instance, describes the
  sensor and not the estimator lane that reads it.

WHAT THE CONTEXT DECLARES
-------------------------
`EpochContext.current` maps each key to the epoch in force now. An optional
`events` map names the transition that set it, for the trace. On PX4 the
natural sources are:
- `estimator_selector_status.instance_changed_count` (uint32, incremented in
  `EKF2Selector::SelectInstance`) for the estimator lane;
- `sensor_selection.accel_device_id` / `gyro_device_id` for the IMU in use;
- the estimator's `*_reset_counter` fields for state resets.

Those are read by an integration adapter. The rule does not re-derive the
estimator's logic and does not decide when a lane switch should happen.

THE RULE
--------
A record is admissible iff every key it names is in the context with an
EQUAL epoch. Equality, not order, decides: order is used only to name the
reason. So a lane switch back to an earlier lane does not re-admit old
evidence, as long as the key is a monotonic counter and not the lane id.

| condition | reason |
|---|---|
| record epoch < current | STALE_CONFIGURATION_EPOCH |
| record epoch > current | EPOCH_AHEAD_OF_CONTEXT, and every record of that key is held back this tick (CONTEXT_BEHIND_PRODUCER): the context evidently missed a transition, so its "current" cannot be trusted |
| key not in the context | UNKNOWN_EPOCH_KEY |
| unparseable stamp, or a context value that is not an epoch | MALFORMED_EPOCH / MALFORMED_CONTEXT_EPOCH |
| composite epochs of different length | EPOCH_FORM_MISMATCH |

WHAT HAPPENS TO AN INADMISSIBLE RECORD
--------------------------------------
- **If an admissible record answers the same (relation, component)**, the
  inadmissible one is dropped: it is superseded, and keeping it would only
  make C6 read neither.
- **Otherwise it becomes UNAVAILABLE ("could not look").** Its identity and
  declared structure are kept (domain, component, relation, source,
  applicability, affected functions, dependencies, attributable,
  provenance). Its content is cleared: reason codes, measured value,
  residual, timestamps, sequential state and detail. Detectors that read
  reason codes cannot see the old content, and C2 treats the record as
  unknown.

Every inadmissible record is listed in the tick's admission report with its
producer, the evidence epoch, the current epoch, the transition event and
the reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from csia.v2.evidence import ObservationState

CONFIG_EPOCH = "config_epoch"
INADMISSIBLE_CODE = "EVIDENCE_CONFIG_EPOCH_INADMISSIBLE"

STALE_CONFIGURATION_EPOCH = "STALE_CONFIGURATION_EPOCH"
EPOCH_AHEAD_OF_CONTEXT = "EPOCH_AHEAD_OF_CONTEXT"
CONTEXT_BEHIND_PRODUCER = "CONTEXT_BEHIND_PRODUCER"
UNKNOWN_EPOCH_KEY = "UNKNOWN_EPOCH_KEY"
MALFORMED_EPOCH = "MALFORMED_EPOCH"
MALFORMED_CONTEXT_EPOCH = "MALFORMED_CONTEXT_EPOCH"
EPOCH_FORM_MISMATCH = "EPOCH_FORM_MISMATCH"

DROPPED_SUPERSEDED = "DROPPED_SUPERSEDED_BY_ADMISSIBLE_RECORD"
MADE_UNAVAILABLE = "MADE_UNAVAILABLE"


def epoch_value(v):
    """A non-negative int, or a non-empty sequence of them, as a tuple.
    None for anything else (bool is not an int here)."""
    if type(v) is int and v >= 0:
        return (v,)
    if isinstance(v, (list, tuple)) and v and all(
            type(x) is int and x >= 0 for x in v):
        return tuple(v)
    return None


@dataclass(frozen=True)
class EpochContext:
    """The configuration epochs in force for one tick."""

    current: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)

    @classmethod
    def of(cls, epochs) -> "EpochContext":
        if epochs is None:
            return cls()
        if isinstance(epochs, cls):
            return epochs
        return cls(dict(epochs))


def _rid(r) -> str:
    return f"{r.domain}/{r.component}:{r.relation}"


def _stamp(r):
    """-> (has_stamp, {key: epoch tuple} or None if malformed)."""
    prov = r.provenance if isinstance(r.provenance, dict) else {}
    if CONFIG_EPOCH not in prov:
        return False, None
    raw = prov[CONFIG_EPOCH]
    if not isinstance(raw, dict) or not raw:
        return True, None
    out = {}
    for k, v in raw.items():
        ev = epoch_value(v)
        if not isinstance(k, str) or not k or ev is None:
            return True, None
        out[k] = ev
    return True, out


def _blank(r, entry):
    return replace(r, observation_state=ObservationState.UNAVAILABLE,
                   reason_codes=(INADMISSIBLE_CODE,), measured_value=None,
                   residual=None, sequential_state=None,
                   timestamp_validity=None, timestamp_arrival=None,
                   timestamp_processed=None,
                   detail={"config_epoch_inadmissible": entry["reason"]})


def admit(records, context: EpochContext) -> tuple:
    """-> (admitted records, report). Records with no epoch stamp pass
    unchanged and in order."""
    records = tuple(records)
    current, context_errors = {}, {}
    for k, v in context.current.items():
        ev = epoch_value(v)
        if ev is None:
            context_errors[k] = MALFORMED_CONTEXT_EPOCH
        else:
            current[k] = ev
    stamps = [_stamp(r) for r in records]
    ahead = set()
    for has, st in stamps:
        for k, ev in (st or {}).items():
            cur = current.get(k)
            if cur is not None and len(cur) == len(ev) and ev > cur:
                ahead.add(k)
    decisions = []
    for r, (has, st) in zip(records, stamps):
        if not has:
            decisions.append(None)
            continue
        if st is None:
            decisions.append({"key": None, "evidence_epoch": None,
                              "current_epoch": None, "reason": MALFORMED_EPOCH})
            continue
        bad = None
        for k in sorted(st):
            ev, cur = st[k], current.get(k)
            if k in context_errors:
                bad = (k, ev, None, context_errors[k])
            elif cur is None:
                bad = (k, ev, None, UNKNOWN_EPOCH_KEY)
            elif len(cur) != len(ev):
                bad = (k, ev, cur, EPOCH_FORM_MISMATCH)
            elif ev > cur:
                bad = (k, ev, cur, EPOCH_AHEAD_OF_CONTEXT)
            elif ev < cur:
                bad = (k, ev, cur, STALE_CONFIGURATION_EPOCH)
            elif k in ahead:
                bad = (k, ev, cur, CONTEXT_BEHIND_PRODUCER)
            if bad:
                break
        if bad is None:
            decisions.append(None)
        else:
            k, ev, cur, why = bad
            decisions.append({"key": k, "evidence_epoch": list(ev),
                              "current_epoch": None if cur is None else list(cur),
                              "reason": why})
    answered = {(r.relation, r.component)
                for r, d in zip(records, decisions) if d is None}
    out, inadmissible = [], []
    stamped = 0
    for r, (has, _st), d in zip(records, stamps, decisions):
        stamped += int(has)
        if d is None:
            out.append(r)
            continue
        entry = {"record": _rid(r), "source": r.source, **d,
                 "transition_event": context.events.get(d["key"]),
                 "action": (DROPPED_SUPERSEDED
                            if (r.relation, r.component) in answered
                            else MADE_UNAVAILABLE)}
        inadmissible.append(entry)
        if entry["action"] == MADE_UNAVAILABLE:
            out.append(_blank(r, entry))
    report = {"context_epochs": {k: list(v) for k, v in sorted(current.items())},
              "context_errors": dict(sorted(context_errors.items())),
              "transition_events": dict(sorted(context.events.items())),
              "keys_with_context_behind": sorted(ahead),
              "records_with_epoch": stamped,
              "inadmissible": inadmissible}
    return tuple(out), report
