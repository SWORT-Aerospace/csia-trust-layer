"""Make a lost sensor mean something to the capability layer.

THE GAP THIS CLOSES
-------------------
`csia_supervision.dataloss` raises a `DataLossCondition` when a monitored
sensor stops delivering. `csia_mission.capability` decides which capabilities
the surviving evidence supports. Nothing connected them: a cut baro line
raised a CAUTION and `altitude_hold` went on reporting SUPPORTED, because the
evidence it rests on was still whatever the firewall last said.

`csia_mission/xr1_contracts.py` already says where the join belongs:

    "These are CANONICAL EVIDENCE IDS, not CSIA internal names. The mapping
     from a CSIA relation to one of these belongs in an adapter, so that the
     frozen core's vocabulary and the mission layer's vocabulary can each
     change without forcing the other."

This is that adapter. It is not part of either layer and neither imports it.

THE ONE RULE: IT CAN ONLY DEMOTE
--------------------------------
A lost sensor is proof that the evidence riding on it is not currently
supportable. A PRESENT sensor is not proof of anything -- support is the
firewall's verdict to give, and delivering bytes is not a verdict. So this
bridge emits an override only for evidence it is DEMOTING, and says nothing
at all about the rest.

That is the mirror of the supervision overlay's own rule. The overlay can
raise a failsafe level and never lower it; the bridge can withdraw support
and never grant it. Both directions fail safe.

WHAT IS NOT MAPPED, AND WHY THAT IS WRITTEN DOWN
-------------------------------------------------
Two monitored sensors have no canonical evidence id at all, and two evidence
ids that look like they should follow from a sensor deliberately do not:

  * `motor_esc`, `vibration` -- the XR-1 contract set names no evidence for
    propulsion or structural telemetry. They are listed in `UNMAPPED` rather
    than attached to the nearest plausible id.
  * `attitude.supported` is NOT demoted when one IMU is lost. Attitude comes
    from the autopilot's estimator, which has two inertial sources; asserting
    that losing one destroys attitude would be inventing a dependency the
    evidence does not establish. It IS demoted when BOTH are lost, which is
    the case where no inertial source remains -- and that rule is labelled
    DERIVED, not DIRECT, so the difference is visible in the output.

An unmapped sensor is reported, not silently dropped. A bridge that quietly
covered six of eight sensors would read exactly like one that covered all
eight.
"""

from __future__ import annotations

from typing import Mapping

from csia_mission.capability import EvidenceStatus

#: This adapter's own name in `EvidenceStatus.source`. A downstream reader
#: must be able to tell an override from a firewall verdict, because they
#: are not the same kind of claim.
SOURCE = "CSIA_DATA_LOSS_SUPERVISOR"

DIRECT = "DIRECT_CHANNEL"
DERIVED = "DERIVED_FROM_TOTAL_LOSS"

#: sensor -> evidence ids that CANNOT hold while that sensor is not
#: delivering. Every entry here is a channel the evidence is read from, so
#: the loss is decisive rather than suggestive.
SENSOR_EVIDENCE: dict = {
    "imu0": ("imu.primary.supported",),
    "imu1": ("imu.reference.supported",),
    "baro": ("baro.altitude.supported",),
    "gps": ("gnss.position.supported", "gnss.velocity.supported"),
    "mag": ("mag.field.supported",),
    "battery": ("power.telemetry.supported",),
}

#: Monitored sensors the XR-1 contract set names no evidence for. Listed so
#: the gap is visible in the report rather than inferred from an absence.
UNMAPPED = frozenset({"motor_esc", "vibration"})

#: Evidence that only falls when EVERY listed sensor is lost. Kept separate
#: from SENSOR_EVIDENCE because "one of two inertial sources is gone" and
#: "there is no inertial source" are different claims.
REQUIRES_ALL_LOST: dict = {
    "attitude.supported": frozenset({"imu0", "imu1"}),
}


def _lost_sensors(conditions: Mapping) -> set:
    """The sensors named by the supervisor's currently dwelled-in conditions.

    Accepts the supervisor's `conditions` mapping directly; a caller with a
    bare set of sensor names may pass that instead.
    """
    if not conditions:
        return set()
    out = set()
    for key, cond in (conditions.items() if hasattr(conditions, "items")
                      else ((c, c) for c in conditions)):
        sensor = getattr(cond, "sensor", None)
        out.add(sensor if sensor is not None else key)
    return out


def evidence_overrides(conditions: Mapping, now: float = 0.0) -> dict:
    """Evidence this loss withdraws support from. DEMOTIONS ONLY.

    Returns `{evidence_id: EvidenceStatus(supported=False)}`. Evidence not
    mentioned is left entirely alone -- absence here means "this bridge has
    nothing to say", never "this is fine".
    """
    lost = _lost_sensors(conditions)
    out: dict = {}

    for sensor in sorted(lost):
        for eid in SENSOR_EVIDENCE.get(sensor, ()):
            out[eid] = EvidenceStatus(
                evidence_id=eid, supported=False, source=SOURCE,
                witness=(f"{DIRECT}:{sensor}",))

    for eid, needed in sorted(REQUIRES_ALL_LOST.items()):
        if needed and needed <= lost:
            out[eid] = EvidenceStatus(
                evidence_id=eid, supported=False, source=SOURCE,
                witness=tuple(f"{DERIVED}:{s}" for s in sorted(needed)))
    return out


def apply(evidence: Mapping[str, EvidenceStatus], conditions,
          now: float = 0.0) -> dict:
    """Merge the overrides over a firewall's evidence map, demote-only.

    An override never promotes: if the incoming status is already
    NOT_SUPPORTED or UNKNOWN it is left as it is, because replacing UNKNOWN
    with a definite NOT_SUPPORTED would be manufacturing certainty, and
    UNKNOWN is the state this system is built never to resolve by guessing.
    """
    merged = dict(evidence or {})
    for eid, override in evidence_overrides(conditions, now).items():
        current = merged.get(eid)
        if current is not None and current.supported is None:
            # UNKNOWN STAYS UNKNOWN. It is not upgraded to a firm negative
            # just because a sensor went quiet.
            continue
        merged[eid] = override
    return merged


def report(evidence: Mapping[str, EvidenceStatus], conditions,
           now: float = 0.0) -> dict:
    """What the bridge did, in a form fit for the flight log."""
    lost = _lost_sensors(conditions)
    overrides = evidence_overrides(conditions, now)
    return {
        "schema": "csia.supervision.capability_bridge/1",
        "sensors_lost": sorted(lost),
        "evidence_withdrawn": sorted(overrides),
        "sensors_lost_with_no_evidence_mapping": sorted(lost & UNMAPPED),
        "source": SOURCE,
        "demote_only": (
            "this bridge withdraws support and never grants it. Evidence it "
            "does not name was not endorsed -- it was simply not the "
            "bridge's to speak about."),
        "unknown_is_not_resolved": (
            "evidence already UNKNOWN is left UNKNOWN. A quiet sensor is not "
            "grounds to convert an unresolved state into a definite one."),
    }
