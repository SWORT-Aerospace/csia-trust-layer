"""`csia-monitor` — a real consumer of the v1.1 output schema. Phase 4.5 §§13–18.

Gate C exists because a schema that only its own producer has ever read is not
an integration, it is a serialisation format with a validator attached. This
module is a second component: it takes `csia_output_v1_1` payloads and nothing
else, and it has no access to the trust engine, the diagnosis, the eligibility
policy or the ledger.

    python -m csia.v1_1.monitor payloads.jsonl

WHAT IT IS NOT
--------------
**Not another source of truth.** It imports no producer. It recomputes
nothing. If a field is absent from the payload the monitor cannot show it, and
that is the point — the exercise is to find out whether the schema carries
enough for an external integration to be useful, and the only honest way to
find out is to forbid the shortcut.

THE ONE DESIGN RULE THAT MATTERS — §15
--------------------------------------
On the GNSS fix-loss payload the trust in `gps` is 0.987 and the leader is
`nominal` at posterior 0.992. A consumer that led with either number would
report a healthy GPS while every GNSS function was ineligible.

So the **primary status is computed from function eligibility and support, and
never from the posterior**. The posterior is not suppressed — it is
informative — but `format_leader` will not render it without its support
qualifier attached, and a test asserts that no rendering path can produce a
bare posterior.

STRICT PARSING — §16
--------------------
Every rejection is a raised `PayloadRejected`. There is no permissive path, no
"best effort" degradation and no default for a missing field: a monitor that
guessed at a malformed assurance payload would be worse than one that stopped.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import output_api as API
from . import reason_codes as RC
from . import sequential as SEQ
from .firewall import OutputFirewall
from .trust_mode import TrustMode

#: Schema majors this consumer understands. §16: an unknown version is
#: refused, never coerced.
SUPPORTED_MAJOR_MINOR = ("1.1",)

#: §14. Everything the consumer is required to be able to surface.
REQUIRED_VIEW = ("timestamp", "assurance", "function_eligibility",
                 "leader", "posterior", "support_state", "ambiguity",
                 "active_evidence_count", "discriminating_evidence_count",
                 "sequential_alarms", "recommendations", "ledger_event")


class PayloadRejected(ValueError):
    """A payload this consumer will not interpret. Never downgraded."""


@dataclass
class MonitorView:
    """One tick, as an external integration sees it."""

    timestamp: float
    assurance: str
    function_eligibility: dict          # {name: state}
    function_reasons: dict              # {name: [codes]}
    leader: str
    posterior: float
    support_state: str
    ambiguity: str
    active_evidence_count: int
    discriminating_evidence_count: int
    sequential_alarms: tuple
    recommendations: tuple
    trust: dict
    ledger_event: dict | None = None

    # -- §15: the primary status, and where it may NOT come from ---------
    @property
    def primary_status(self) -> str:
        """Derived from ELIGIBILITY and SUPPORT. The posterior is not an
        input to this property, and a test asserts that by construction."""
        states = list(self.function_eligibility.values())
        if not states:
            return "NO_FUNCTIONS_REPORTED"
        worst = max(states, key=lambda s: RC.SEVERITY_RANK[s])
        gone = sum(1 for s in states if s == RC.INELIGIBLE)
        degraded = sum(1 for s in states if s == RC.DEGRADED)
        if worst == RC.ELIGIBLE:
            return "ALL FUNCTIONS AVAILABLE"
        if worst == RC.UNKNOWN:
            return "ELIGIBILITY UNDETERMINED — MANUAL REVIEW"
        head = (f"{gone} OF {len(states)} FUNCTIONS UNAVAILABLE" if gone
                else f"{degraded} OF {len(states)} FUNCTIONS DEGRADED")
        return f"{head} — support {self.support_state}"

    @property
    def unavailable(self) -> tuple:
        return tuple(sorted(n for n, s in self.function_eligibility.items()
                            if s == RC.INELIGIBLE))

    def format_leader(self) -> str:
        """The posterior, NEVER on its own.

        §15. `nominal p=0.9925` invites "99% confident it is fine". The
        support state and the discriminating-evidence count are what make it
        readable, so they are not optional here and cannot be formatted away.
        """
        return (f"{self.leader} p={self.posterior:.4f} "
                f"[{self.support_state}, "
                f"{self.discriminating_evidence_count} discriminating, "
                f"{self.ambiguity}]")

    def render(self) -> str:
        lines = [
            f"t={self.timestamp:8.2f}  {self.primary_status}",
            f"  assurance          {self.assurance}",
            f"  diagnosis          {self.format_leader()}",
            f"  evidence           {self.active_evidence_count} active, "
            f"{self.discriminating_evidence_count} discriminating",
            f"  sequential alarms  "
            f"{', '.join(self.sequential_alarms) or 'none'}",
        ]
        for name in sorted(self.function_eligibility):
            state = self.function_eligibility[name]
            why = ", ".join(self.function_reasons.get(name, ()))
            lines.append(f"  {name:22s} {state:11s} {why}")
        if self.recommendations:
            lines.append("  advisory           "
                         + ", ".join(self.recommendations))
        if self.ledger_event:
            ev = self.ledger_event
            lines.append(f"  ledger             {ev['event_type']} "
                         f"{ev.get('subject', '')} "
                         f"{ev.get('previous_state', '')}->"
                         f"{ev.get('new_state', '')}")
        return "\n".join(lines)

    def to_row(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "primary_status": self.primary_status,
            "assurance": self.assurance,
            "leader": self.leader, "posterior": self.posterior,
            "support_state": self.support_state, "ambiguity": self.ambiguity,
            "active_evidence_count": self.active_evidence_count,
            "discriminating_evidence_count":
                self.discriminating_evidence_count,
            "sequential_alarms": list(self.sequential_alarms),
            "recommendations": list(self.recommendations),
            "function_eligibility": dict(self.function_eligibility),
            "unavailable": list(self.unavailable),
            "ledger_event": (self.ledger_event or {}).get("event_type"),
        }


# ---------------------------------------------------------------- parsing
def _require(payload, path):
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise PayloadRejected(
                f"missing required field: {'.'.join(path)}")
        node = node[key]
    return node


def parse(payload: dict) -> MonitorView:
    """Strict. Every failure raises; nothing is defaulted or guessed."""
    if not isinstance(payload, dict):
        raise PayloadRejected(f"payload is {type(payload).__name__}, not an "
                              f"object")

    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise PayloadRejected("schema_version missing or not a string")
    if ".".join(version.split(".")[:2]) not in SUPPORTED_MAJOR_MINOR:
        raise PayloadRejected(
            f"unsupported schema_version {version!r}; this consumer "
            f"understands {SUPPORTED_MAJOR_MINOR}. Refusing rather than "
            f"reinterpreting fields whose meaning may have changed.")

    try:
        API.validate(payload)
    except Exception as exc:                       # jsonschema.ValidationError
        raise PayloadRejected(f"schema validation failed: {exc}") from exc

    mode = _require(payload, ("trust", "mode"))
    if mode not in {m.value for m in TrustMode}:
        raise PayloadRejected(f"unknown trust mode {mode!r}")

    seq = _require(payload, ("sequential",))
    if seq.get("k") != SEQ.CUSUM_K or seq.get("h") != SEQ.CUSUM_H:
        raise PayloadRejected(
            f"sequential constants {seq.get('k')}/{seq.get('h')} do not match "
            f"the frozen detector {SEQ.CUSUM_K}/{SEQ.CUSUM_H}; this payload "
            f"was produced by a differently configured detector")

    diag = _require(payload, ("diagnosis",))
    elig, reasons = {}, {}
    for name, row in _require(payload, ("function_eligibility",)).items():
        state = row.get("state")
        if state not in RC.STATES:
            raise PayloadRejected(
                f"unknown function state {state!r} for {name}")
        elig[name] = state
        reasons[name] = tuple(row.get("reason_codes", ()))

    for code_list in reasons.values():
        for code in code_list:
            if code not in RC.eligibility_codes():
                raise PayloadRejected(f"unknown reason code {code!r}")

    return MonitorView(
        timestamp=float(_require(payload, ("timestamp",))),
        assurance=_require(payload, ("assurance", "level")),
        function_eligibility=elig, function_reasons=reasons,
        leader=diag["leader"], posterior=float(diag["posterior"]),
        support_state=diag["support_state"], ambiguity=diag["ambiguity"],
        active_evidence_count=int(diag["active_evidence_count"]),
        discriminating_evidence_count=int(
            diag["discriminating_evidence_count"]),
        sequential_alarms=tuple(seq.get("alarming", ())),
        recommendations=tuple(payload.get("recommendations", ())),
        trust=dict(_require(payload, ("trust", "nodes"))),
        ledger_event=payload.get("ledger_event"),
    )


# --------------------------------------------------------------- the monitor
@dataclass
class Monitor:
    """Read-only. Holds a firewall and no transport."""

    firewall: OutputFirewall = field(default_factory=OutputFirewall)
    accepted: int = 0
    rejected: list = field(default_factory=list)
    views: list = field(default_factory=list)

    def consume(self, payload: dict) -> MonitorView | None:
        """Accept one payload, or record why it was refused."""
        self.firewall.request("EMIT_OUTPUT")       # permitted: read + render
        try:
            view = parse(payload)
        except PayloadRejected as exc:
            self.rejected.append(str(exc))
            return None
        self.accepted += 1
        self.views.append(view)
        return view

    def consume_jsonl(self, path: str) -> int:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.rejected.append(f"malformed JSON: {exc}")
                        continue
                    self.consume(obj)
        return self.accepted

    def act(self, operation: str):
        """Every action a monitor might be asked to take goes through here.

        §18. There is no branch that bypasses the firewall, so a control
        operation is denied by the same path that permits a log write.
        """
        return self.firewall.request(operation)

    def evidence(self) -> dict:
        return {"accepted": self.accepted,
                "rejected": len(self.rejected),
                "rejections": list(self.rejected),
                "firewall": self.firewall.evidence()}


def main(argv=None) -> int:                        # pragma: no cover - CLI
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip().splitlines()[0])
        print("usage: python -m csia.v1_1.monitor <payloads.jsonl>")
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"no such file: {path}")
        return 2
    mon = Monitor()
    mon.consume_jsonl(path)
    for view in mon.views:
        print(view.render())
        print()
    ev = mon.evidence()
    print(f"accepted={ev['accepted']} rejected={ev['rejected']}")
    for why in ev["rejections"]:
        print("  REJECTED:", why)
    return 0 if ev["rejected"] == 0 else 1


if __name__ == "__main__":                         # pragma: no cover
    raise SystemExit(main())
