"""Table resets: Vacated -> Busser -> Ready to seat, and the visit guard."""

import uuid

from django.test import TestCase

from dispatch import engine
from dispatch.integrations import pos
from dispatch.models import AuditEvent, IntegrationEvent, Table, Task, Visit
from dispatch.states import TableState, TaskKind, TaskState, VisitState

from .helpers import fresh, sample, table


class ResetFlowTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular")
        self.t1 = table(self.loc, "1")

    def test_reset_moves_from_vacated_to_busser_to_ready_to_seat(self):
        old_visit = self.t1.current_visit
        reset = engine.mark_departed(self.s["Ana"], self.t1.pk).task
        t1 = fresh(self.t1)
        self.assertEqual(t1.state, TableState.NEEDS_RESET)
        self.assertEqual(fresh(old_visit).state, VisitState.DEPARTED)
        self.assertEqual((reset.kind, reset.state, reset.offered_to), (TaskKind.RESET, TaskState.OFFERED, self.s["Lee"]))

        engine.claim(self.s["Lee"], reset.pk)
        self.assertEqual(fresh(self.t1).state, TableState.RESETTING)

        engine.complete(self.s["Lee"], reset.pk)
        t1 = fresh(self.t1)
        self.assertEqual(t1.state, TableState.READY)
        self.assertIsNone(t1.current_visit)
        self.assertEqual(fresh(old_visit).state, VisitState.CLOSED)

        result = engine.seat_party(self.s["Ana"], self.t1.pk, 3)
        t1 = fresh(self.t1)
        self.assertEqual(t1.state, TableState.OCCUPIED)
        self.assertEqual(t1.current_visit, result.visit)
        self.assertNotEqual(result.visit.pk, old_visit.pk)

    def test_previous_visits_reset_cannot_release_a_newly_occupied_table(self):
        reset = engine.mark_departed(self.s["Ana"], self.t1.pk).task
        engine.claim(self.s["Lee"], reset.pk)
        # The floor lead seats a new party before Lee confirmed the reset.
        new_visit = engine.seat_override(self.s["Rae"], self.t1.pk, 2).visit
        self.assertEqual(fresh(reset).state, TaskState.CANCELLED)
        # Lee's late "done" arrives from the old visit.
        with self.assertRaises(engine.Conflict):
            engine.complete(self.s["Lee"], reset.pk)
        t1 = fresh(self.t1)
        self.assertEqual(t1.state, TableState.OCCUPIED)
        self.assertEqual(t1.current_visit, new_visit)

    def test_engine_guard_ignores_stale_visit_even_if_task_were_still_open(self):
        """Defense in depth: even if a reset for an old visit were still claimed,
        completing it must not touch a table that now belongs to a newer visit."""
        reset = engine.mark_departed(self.s["Ana"], self.t1.pk).task
        engine.claim(self.s["Lee"], reset.pk)
        newer = Visit.objects.create(location=self.loc, table=self.t1, party_size=4)
        Table.objects.filter(pk=self.t1.pk).update(state=TableState.OCCUPIED, current_visit=newer)
        result = engine.complete(self.s["Lee"], reset.pk)
        self.assertIn("stays seated", result.message)
        t1 = fresh(self.t1)
        self.assertEqual((t1.state, t1.current_visit), (TableState.OCCUPIED, newer))
        self.assertTrue(AuditEvent.objects.filter(task=reset, verb="reset.stale").exists())

    def test_payment_or_check_closure_never_marks_a_table_vacant(self):
        recorded = pos.ingest(self.loc, pos.FakePOSAdapter(), {"events": [{"kind": "check_closed", "table": "1"}]})
        self.assertEqual(fresh(self.t1).state, TableState.OCCUPIED)
        self.assertFalse(Task.objects.filter(table=self.t1, kind=TaskKind.RESET).exists())
        self.assertEqual(len(recorded), 1)
        self.assertFalse(recorded[0].applied)
        self.assertIn("payment never marks a table vacant", recorded[0].would_do)

    def test_shadow_mode_item_ready_creates_no_work(self):
        pos.ingest(self.loc, pos.FakePOSAdapter(), {"events": [{"kind": "item_ready", "table": "1", "ref": "x"}]})
        self.assertFalse(Task.objects.filter(table=self.t1, kind=TaskKind.RUN).exists())
        self.assertEqual(IntegrationEvent.objects.get().mode, "shadow")

    def test_repeated_departure_creates_one_reset(self):
        first = engine.mark_departed(self.s["Ana"], self.t1.pk, client_token=str(uuid.uuid4()))
        second = engine.mark_departed(self.s["Theo"], self.t1.pk, client_token=str(uuid.uuid4()))
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(Task.objects.filter(table=self.t1, kind=TaskKind.RESET).count(), 1)

    def test_replayed_seat_creates_one_visit(self):
        t7 = table(self.loc, "7")
        token = str(uuid.uuid4())
        engine.seat_party(self.s["Ana"], t7.pk, 2, client_token=token)
        again = engine.seat_party(self.s["Ana"], t7.pk, 2, client_token=token)
        self.assertFalse(again.created)
        self.assertEqual(Visit.objects.filter(table=t7).count(), 1)
        with self.assertRaises(engine.Conflict):
            engine.seat_party(self.s["Ana"], t7.pk, 2, client_token=str(uuid.uuid4()))  # already seated

    def test_role_rules_for_tables(self):
        with self.assertRaises(engine.Forbidden):
            engine.mark_departed(self.s["Lee"], self.t1.pk)  # busser can't declare a party gone
        with self.assertRaises(engine.Forbidden):
            engine.seat_party(self.s["Theo"], table(self.loc, "7").pk)  # server can't seat
        with self.assertRaises(engine.Forbidden):
            engine.seat_override(self.s["Ana"], table(self.loc, "3").pk)  # host can't override a reset
        engine.mark_departed(self.s["Theo"], self.t1.pk)  # server can confirm departure

    def test_reset_offer_escalates_like_runs(self):
        reset = engine.mark_departed(self.s["Ana"], self.t1.pk).task
        engine.decline(self.s["Lee"], reset.pk)
        self.assertEqual(fresh(reset).offered_to, self.s["Jo"])
        engine.decline(self.s["Jo"], reset.pk)
        self.assertEqual(fresh(reset).state, TaskState.ESCALATED)
