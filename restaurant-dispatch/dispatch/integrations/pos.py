"""POS adapter interface (shadow mode only in this release).

The first release runs on manual Expo and table events. A POS adapter turns a
vendor payload into normalized ``POSEvent`` objects; ``ingest`` records them
with what dispatch *would* have done, and changes nothing on the floor.

An adapter graduates out of shadow mode only after the actual site proves that
its event means what dispatch needs (for example, that "course fired" means the
full course is physically at the pass). Toast is the first candidate for a real
read-only adapter, then Square. Neither is connected here, and no vendor
access is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from ..models import IntegrationEvent, Table
from ..states import TableState


@dataclass(frozen=True)
class POSEvent:
    kind: str  # "item_ready" | "course_fired" | "check_closed" | "order_opened"
    table_label: str
    external_ref: str = ""


class POSAdapter(Protocol):
    provider: str

    def parse(self, payload: dict) -> Iterable[POSEvent]: ...


class FakePOSAdapter:
    """Test adapter. Accepts {"events": [{"kind": ..., "table": ..., "ref": ...}]}."""

    provider = "fake"

    def parse(self, payload: dict) -> Iterable[POSEvent]:
        for raw in payload.get("events", []):
            yield POSEvent(kind=str(raw["kind"]), table_label=str(raw["table"]), external_ref=str(raw.get("ref", "")))


PLANNED_ADAPTERS = [
    {
        "key": "toast",
        "name": "Toast",
        "status": "Planned — first read-only candidate",
        "detail": "Not connected. Will start in shadow mode once vendor access is approved.",
    },
    {
        "key": "square",
        "name": "Square",
        "status": "Planned — after Toast",
        "detail": "Not connected. No credentials are requested by this release.",
    },
]


def interpret(location, event: POSEvent) -> str:
    """What dispatch would do with this event if the adapter were trusted."""
    table = Table.objects.filter(location=location, label=event.table_label).first()
    where = f"table {event.table_label}" if table else f"unknown table “{event.table_label}”"
    if event.kind == "check_closed":
        state = f" (currently {table.get_state_display().lower()})" if table else ""
        return f"No change to {where}{state}: payment never marks a table vacant."
    if event.kind == "item_ready":
        if location.profile.holds_at_pass:
            return f"Would stage a course for {where} — only after the site proves the event means the full course is at the pass."
        return f"Would create a run offer for {where}."
    if event.kind == "course_fired":
        return f"No action: “fired” means the kitchen started {where}'s course, not that it is at the pass."
    if event.kind == "order_opened" and table and table.state != TableState.OCCUPIED:
        return f"No action: seating stays with the host for {where}."
    return f"No action for {event.kind} at {where}."


def ingest(location, adapter: POSAdapter, payload: dict) -> list[IntegrationEvent]:
    """Record events in shadow mode. Never creates tasks or changes tables."""
    recorded = []
    for event in adapter.parse(payload):
        recorded.append(
            IntegrationEvent.objects.create(
                location=location,
                provider=adapter.provider,
                mode="shadow",
                kind=event.kind[:30],
                external_ref=event.external_ref[:80],
                table_label=event.table_label[:20],
                would_do=interpret(location, event)[:200],
                applied=False,
            )
        )
    return recorded
