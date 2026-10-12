"""Capability negotiation: what this vehicle can support, before it flies.

A vehicle is plugged in, a profile is selected, and the honest question is
*which diagnostic relations can this airframe actually feed?* Answering it
after the fact -- by watching relations sit at zero and guessing why -- is
what the systems paper measures going wrong. This answers it up front, from
the frozen relation graph and the adapter's own channel report.

THE DISTINCTION THIS MODULE EXISTS TO PRESERVE
-----------------------------------------------
"I have not heard from this sensor yet" and "this airframe does not have this
sensor" produce identical channel states and mean opposite things. The
adapter alone cannot tell them apart: `MissingReason.NOT_RECEIVED` covers
both. Only the PROFILE knows which channels the vehicle is supposed to
provide, so capability is a function of BOTH, and a channel the profile does
not declare is `NOT_CONFIGURED` rather than broken.

That distinction is the whole reason a diagnostic layer may not report health
by default. A relation that is dark because the airframe lacks an ESC
telemetry bus is a permanent structural fact; a relation dark because a cable
fell out is a fault. Collapsing them is how "absence of evidence" becomes
"evidence of health".

NOTHING HERE CHANGES A DIAGNOSTIC DECISION
------------------------------------------
This module reads the frozen relation graph and reports. It does not gate,
score, weight or rank. `csia/trust_graph/graph.py:EDGES` is the source of
truth for which relations exist and which nodes they span; if that list
changes, this follows it rather than carrying its own copy.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from ..trust_graph.graph import EDGES
from .adapters.base import PlatformAdapter


class Capability(enum.Enum):
    """What is known about a channel or relation, with absence spelled out.

    Deliberately NOT a two-state available/unavailable. Four of these six mean
    "no data", and a consumer that treats them alike will draw the wrong
    conclusion from at least two of them.
    """

    AVAILABLE = "AVAILABLE"
    #: declared by the profile, arriving, and admissible as evidence.

    UNAVAILABLE = "UNAVAILABLE"
    #: declared by the profile and NOT arriving. This is the one that may be
    #: a fault. Everything below is a configuration fact, not a fault.

    NOT_CONFIGURED = "NOT_CONFIGURED"
    #: the profile does not declare it. The airframe is not expected to have
    #: it and its absence says nothing about health.

    INAPPLICABLE = "INAPPLICABLE"
    #: the profile declares it structurally impossible on this airframe --
    #: e.g. a second IMU on a single-IMU board. Distinct from NOT_CONFIGURED,
    #: which merely means "not wired up here".

    STALE = "STALE"
    #: arrived once and has since aged out. Distinct from UNAVAILABLE because
    #: it proves the path worked at least once.

    UNKNOWN = "UNKNOWN"
    #: not yet determined -- typically the start-up window, before enough
    #: time has passed for UNAVAILABLE to mean anything. Never report a
    #: relation INACTIVE on the strength of an UNKNOWN endpoint.


#: Which canonical channels each trust-graph node needs before it can feed a
#: relation. Mirrors `PlatformAdapter.CORE_MAP`, and a test asserts the two
#: agree -- if the core map gains a sensor and this does not, capability
#: negotiation would silently report a relation available that the core
#: cannot actually compute.
NODE_CHANNELS = {
    "imu0": ("imu0.accel", "imu0.gyro"),
    "imu1": ("imu1.accel", "imu1.gyro"),
    "mag": ("mag.field_ut",),
    "baro": ("baro.altitude",),
    "gps": ("gnss.position", "gnss.velocity"),
    "battery": ("battery.voltage", "battery.current"),
    "motor_esc": ("esc.rpm", "esc.current"),
    "vibration": ("vibration.rms",),
}


#: (display name, endpoints) -> the identifier the RUNTIME actually uses.
#:
#: THIS IS NOT A NEW IDENTIFIER SCHEME. The stable IDs already existed:
#: csia/prediction/comparator.py computes `velocity_gps_doppler_0` for the
#: imu0-gps edge and `velocity_gps_doppler_1` for imu1-gps, and those are the
#: strings that appear in `gps_gates` in every Mechanism-A trial artifact.
#: csia/trust_graph/graph.py's EDGES list -- which drives the diagram -- gives
#: BOTH edges the same human-friendly display name, and the capability layer
#: inherited that ambiguity from it.
#:
#: So a name may legitimately repeat; an edge ID may not. Reporting the
#: runtime ID means a capability report and a trial artifact now use the same
#: string for the same edge, which they did not before.
EDGE_ID = {
    ("velocity_gps_doppler", ("imu0", "gps")): "velocity_gps_doppler_0",
    ("velocity_gps_doppler", ("imu1", "gps")): "velocity_gps_doppler_1",
}


def edge_id(relation: str, endpoints: tuple) -> str:
    """The runtime identifier for an edge. Falls back to the relation name.

    Every relation except the doppler pair has exactly one edge, so its name
    IS its identifier and no mapping entry is needed.
    """
    return EDGE_ID.get((relation, tuple(endpoints)), relation)


@dataclass
class RelationCapability:
    """One relation, and why it can or cannot be fed."""

    relation: str
    endpoints: tuple
    capability: Capability
    blocking_nodes: tuple = ()
    blocking_channels: tuple = ()
    note: str = ""

    @property
    def edge_id(self) -> str:
        """Stable identifier. Distinct even when `relation` repeats."""
        return edge_id(self.relation, self.endpoints)


@dataclass
class CapabilityReport:
    """The answer to 'can I plug CSIA into this vehicle?'"""

    platform: str
    profile_id: Optional[str]
    channels: dict = field(default_factory=dict)
    nodes: dict = field(default_factory=dict)
    relations: list = field(default_factory=list)

    def _labels(self, *caps) -> list:
        """Summaries are keyed on the EDGE ID, never on the display name.

        `velocity_gps_doppler` names two edges. On a single-IMU airframe one is
        INAPPLICABLE and the other merely UNKNOWN, and a summary keyed on the
        display name put the same string in two mutually exclusive buckets --
        which reads as a contradiction even though the underlying data was
        right. The runtime already distinguishes them; this now uses those
        identifiers.
        """
        return [r.edge_id for r in self.relations if r.capability in caps]

    @property
    def active_relations(self) -> list:
        return self._labels(Capability.AVAILABLE)

    @property
    def inactive_relations(self) -> list:
        return self._labels(Capability.UNAVAILABLE, Capability.STALE)

    @property
    def structurally_absent_relations(self) -> list:
        """Relations this airframe was never going to feed. NOT a fault."""
        return self._labels(Capability.NOT_CONFIGURED, Capability.INAPPLICABLE)

    @property
    def unknown_relations(self) -> list:
        return self._labels(Capability.UNKNOWN)

    @property
    def compatible(self) -> bool:
        """CSIA-compatible means: at least one relation can be fed.

        Deliberately a low bar, and deliberately not a quality judgement. A
        vehicle with one live relation is compatible and severely limited, and
        `to_dict()` reports both so the caller cannot see one without the
        other.
        """
        return bool(self.active_relations)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "profile_id": self.profile_id,
            "compatible": self.compatible,
            "channels": {k: v.value for k, v in self.channels.items()},
            "nodes": {k: v.value for k, v in self.nodes.items()},
            "relations": [
                {
                    "edge_id": r.edge_id,
                    "relation": r.relation,
                    "endpoints": list(r.endpoints),
                    "capability": r.capability.value,
                    "blocking_nodes": list(r.blocking_nodes),
                    "blocking_channels": list(r.blocking_channels),
                    "note": r.note,
                }
                for r in self.relations
            ],
            "summary": {
                "active": sorted(set(self.active_relations)),
                "inactive": sorted(set(self.inactive_relations)),
                "structurally_absent": sorted(
                    set(self.structurally_absent_relations)),
                "unknown": sorted(set(self.unknown_relations)),
            },
        }


def channel_capability(adapter: PlatformAdapter, channel: str,
                       declared: Optional[set], now: Optional[float] = None,
                       inapplicable: Optional[set] = None) -> Capability:
    """One channel's capability, from the adapter state AND the profile.

    `declared` is the set of channels the profile says this vehicle provides.
    Pass None when no profile is loaded -- then every channel the adapter's
    contract knows about is treated as declared, which is the old behaviour
    and is weaker: without a profile, NOT_CONFIGURED cannot be distinguished
    from UNAVAILABLE.
    """
    inapplicable = inapplicable or set()
    if channel in inapplicable:
        return Capability.INAPPLICABLE
    if declared is not None and channel not in declared:
        return Capability.NOT_CONFIGURED

    now = now if now is not None else adapter._clock()
    cv = adapter._channel_value(channel, now)
    if cv.usable:
        return Capability.AVAILABLE
    if cv.missing is not None and cv.missing.value == "STALE":
        return Capability.STALE
    if cv.missing is not None and cv.missing.value == "NOT_RECEIVED":
        # Nothing has arrived. Whether that is a fault or a start-up window
        # is not decidable from here, and saying UNAVAILABLE would assert
        # more than is known.
        return Capability.UNKNOWN
    return Capability.UNAVAILABLE


def negotiate(adapter: PlatformAdapter, profile=None,
              now: Optional[float] = None) -> CapabilityReport:
    """Produce the full capability report for an adapter and a profile."""
    declared = None
    inapplicable = set()
    profile_id = None
    if profile is not None:
        declared = set(profile.declared_channels)
        inapplicable = set(profile.inapplicable_channels)
        profile_id = profile.profile_id

    now = now if now is not None else adapter._clock()
    report = CapabilityReport(platform=adapter.platform, profile_id=profile_id)

    all_channels = set(adapter.contract.channels)
    if declared is not None:
        all_channels |= declared
    for channel in sorted(all_channels):
        report.channels[channel] = channel_capability(
            adapter, channel, declared, now, inapplicable)

    for node, channels in NODE_CHANNELS.items():
        caps = [report.channels.get(c, Capability.NOT_CONFIGURED)
                for c in channels]
        if all(c is Capability.AVAILABLE for c in caps):
            report.nodes[node] = Capability.AVAILABLE
        elif any(c is Capability.INAPPLICABLE for c in caps):
            report.nodes[node] = Capability.INAPPLICABLE
        elif any(c is Capability.NOT_CONFIGURED for c in caps):
            report.nodes[node] = Capability.NOT_CONFIGURED
        elif any(c is Capability.UNKNOWN for c in caps):
            report.nodes[node] = Capability.UNKNOWN
        elif any(c is Capability.STALE for c in caps):
            report.nodes[node] = Capability.STALE
        else:
            report.nodes[node] = Capability.UNAVAILABLE

    seen = set()
    for a, b, relation, _desc in EDGES:
        # velocity_gps_doppler appears twice, once per IMU. Both instances are
        # reported; the key is the (relation, endpoints) pair, not the name.
        key = (relation, a, b)
        if key in seen:
            continue
        seen.add(key)
        ca, cb = report.nodes.get(a, Capability.NOT_CONFIGURED), \
            report.nodes.get(b, Capability.NOT_CONFIGURED)
        blocking_nodes = tuple(n for n, c in ((a, ca), (b, cb))
                               if c is not Capability.AVAILABLE)
        blocking_channels = tuple(
            ch for n in blocking_nodes for ch in NODE_CHANNELS.get(n, ())
            if report.channels.get(ch) is not Capability.AVAILABLE)

        if not blocking_nodes:
            cap, note = Capability.AVAILABLE, ""
        elif any(c is Capability.INAPPLICABLE for c in (ca, cb)):
            cap = Capability.INAPPLICABLE
            note = "an endpoint is structurally absent on this airframe"
        elif any(c is Capability.NOT_CONFIGURED for c in (ca, cb)):
            cap = Capability.NOT_CONFIGURED
            note = "an endpoint is not declared by the profile"
        elif any(c is Capability.UNKNOWN for c in (ca, cb)):
            cap = Capability.UNKNOWN
            note = "an endpoint has not reported yet; too early to call it dark"
        elif any(c is Capability.STALE for c in (ca, cb)):
            cap = Capability.STALE
            note = "an endpoint reported once and has since aged out"
        else:
            cap = Capability.UNAVAILABLE
            note = "an endpoint is declared and not arriving"

        report.relations.append(RelationCapability(
            relation=relation, endpoints=(a, b), capability=cap,
            blocking_nodes=blocking_nodes,
            blocking_channels=tuple(sorted(set(blocking_channels))),
            note=note))

    return report
