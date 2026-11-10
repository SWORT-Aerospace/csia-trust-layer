"""POS adapter boundary: shadow mode records, dedupes and identity-checks
events, and never touches live service."""

import json
from pathlib import Path

from django.test import TestCase

from dispatch import engine
from dispatch.integrations import pos
from dispatch.models import AuditEvent, IntegrationEvent, Location, Table, Task

from .helpers import sample, table

FIXTURE = Path(__file__).parent / "fixtures" / "pos_shadow_ready_events.json"


class ShadowReadyEventTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("captain_release", prefix="pos-")
        Location.objects.filter(pk=self.loc.pk).update(pos_ref="venue-42")
        self.loc.refresh_from_db()
        self.payload = json.loads(FIXTURE.read_text())

    def snapshot(self):
        return (
            list(Task.objects.order_by("pk").values_list("pk", "state", "version")),
            list(Table.objects.order_by("pk").values_list("pk", "state", "version", "current_visit_id")),
            AuditEvent.objects.count(),
        )

    def test_fixture_is_deduplicated_and_identity_checked_without_side_effects(self):
        before = self.snapshot()
        recorded = pos.ingest(self.loc, pos.FakePOSAdapter(), self.payload)
        self.assertEqual(self.snapshot(), before)  # no tasks, tables or staff-visible events changed
        by_id = {e.external_event_id: e for e in recorded}
        self.assertEqual(len(recorded), 6)  # evt-1001 arrived twice, recorded once
        self.assertEqual(by_id["evt-1001"].identity_check, "match")
        self.assertIn("Would stage a course for table 3", by_id["evt-1001"].would_do)
        self.assertEqual(by_id["evt-1002"].identity_check, "wrong_location")
        self.assertEqual(by_id["evt-1003"].identity_check, "unknown_table")
        self.assertEqual(by_id["evt-1004"].identity_check, "course_mismatch")
        self.assertEqual(by_id["evt-1005"].identity_check, "course_already_on_pass")  # seeded staged course 3
        self.assertIn("payment never marks a table vacant", by_id["evt-1006"].would_do)
        self.assertTrue(all(e.mode == "shadow" and not e.applied for e in recorded))
        # A vendor retry of the whole batch records nothing new.
        self.assertEqual(pos.ingest(self.loc, pos.FakePOSAdapter(), self.payload), [])
        self.assertEqual(IntegrationEvent.objects.filter(location=self.loc).count(), 6)

    def test_unmapped_location_never_matches(self):
        Location.objects.filter(pk=self.loc.pk).update(pos_ref="")
        self.loc.refresh_from_db()
        recorded = pos.ingest(self.loc, pos.FakePOSAdapter(), {"events": [self.payload["events"][0]]})
        self.assertEqual(recorded[0].identity_check, "location_not_mapped")
        self.assertTrue(recorded[0].would_do.startswith("Would ignore"))

    def test_closed_check_never_frees_a_table_even_after_departure_flow_exists(self):
        t3 = table(self.loc, "3")
        pos.ingest(self.loc, pos.FakePOSAdapter(), {"events": [self.payload["events"][-1]]})
        self.assertEqual(table(self.loc, "3").state, "occupied")
        engine.mark_departed(self.s["Ana"], t3.pk)  # only a person confirming departure does
        self.assertEqual(table(self.loc, "3").state, "needs_reset")
