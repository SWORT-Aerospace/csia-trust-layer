"""Regular Service: expo -> runner -> delivered, backup coverage and escalation."""

import uuid

from django.test import TestCase

from dispatch import engine
from dispatch.models import AuditEvent, Task
from dispatch.states import OfferStage, TaskState

from .helpers import fresh, later, sample, table


class RegularRunTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular")
        self.t4 = table(self.loc, "4")  # Main room: Maria first, Dev backup

    def fire(self, **kwargs):
        return engine.food_ready(self.s["Sam"], self.t4.pk, 2, **kwargs).task

    def test_run_goes_from_expo_to_runner_to_delivered(self):
        run = self.fire()
        self.assertEqual(run.state, TaskState.OFFERED)
        self.assertEqual(run.offered_to, self.s["Maria"])
        self.assertEqual(run.offer_stage, OfferStage.PRIMARY)
        self.assertIsNotNone(run.ready_at)
        self.assertIsNotNone(run.offered_at)

        engine.claim(self.s["Maria"], run.pk)
        run = fresh(run)
        self.assertEqual((run.state, run.owner), (TaskState.CLAIMED, self.s["Maria"]))
        self.assertIsNotNone(run.claimed_at)

        engine.complete(self.s["Maria"], run.pk)
        run = fresh(run)
        self.assertEqual(run.state, TaskState.COMPLETED)
        self.assertEqual(run.completed_by, self.s["Maria"])
        self.assertLessEqual(run.ready_at, run.offered_at)
        self.assertLessEqual(run.claimed_at, run.completed_at)

    def test_expired_offer_goes_to_backup_then_escalates_to_floor_lead(self):
        run = self.fire()
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + 1))
        run = fresh(run)
        self.assertEqual(run.state, TaskState.OFFERED)
        self.assertEqual(run.offered_to, self.s["Dev"])
        self.assertEqual(run.offer_stage, OfferStage.BACKUP)

        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + self.loc.backup_timeout_seconds + 2))
        run = fresh(run)
        self.assertEqual(run.state, TaskState.ESCALATED)
        self.assertEqual(run.escalated_to_role, "lead")
        self.assertIsNotNone(run.escalated_at)
        self.assertIsNone(run.offered_to)
        verbs = list(AuditEvent.objects.filter(task=run).order_by("at", "id").values_list("verb", flat=True))
        self.assertEqual(
            verbs, ["run.ready", "offer.sent", "offer.expired", "offer.sent", "offer.expired", "task.escalated"]
        )
        # The floor lead can hand it to a runner directly.
        engine.assign(self.s["Rae"], run.pk, self.s["Maria"].pk)
        run = fresh(run)
        self.assertEqual((run.state, run.owner, run.assigned_by), (TaskState.CLAIMED, self.s["Maria"], self.s["Rae"]))

    def test_only_the_offered_runner_can_claim_an_offer(self):
        run = self.fire()
        with self.assertRaises(engine.Conflict):
            engine.claim(self.s["Dev"], run.pk)
        with self.assertRaises(engine.Forbidden):
            engine.claim(self.s["Ana"], run.pk)  # host is not a runner

    def test_decline_moves_to_backup_immediately(self):
        run = self.fire()
        engine.decline(self.s["Maria"], run.pk)
        run = fresh(run)
        self.assertEqual((run.offered_to, run.offer_stage), (self.s["Dev"], OfferStage.BACKUP))
        engine.decline(self.s["Dev"], run.pk)
        self.assertEqual(fresh(run).state, TaskState.ESCALATED)

    def test_claimed_run_stays_with_its_owner(self):
        run = self.fire()
        engine.claim(self.s["Maria"], run.pk)
        engine.expire_due_offers(now=later(3600))
        self.assertEqual(fresh(run).owner, self.s["Maria"])
        with self.assertRaises(engine.Conflict):
            engine.claim(self.s["Dev"], run.pk)
        with self.assertRaises(engine.Forbidden):
            engine.complete(self.s["Dev"], run.pk)
        with self.assertRaises(engine.Forbidden):
            engine.release_claim(self.s["Dev"], run.pk)
        with self.assertRaises(engine.Forbidden):
            engine.assign(self.s["Dev"], run.pk, self.s["Dev"].pk)  # runners can't reassign
        # An authorized lead can reassign.
        engine.assign(self.s["Rae"], run.pk, self.s["Dev"].pk)
        self.assertEqual(fresh(run).owner, self.s["Dev"])

    def test_owner_giving_back_re_routes_to_someone_else(self):
        run = self.fire()
        engine.claim(self.s["Maria"], run.pk)
        engine.release_claim(self.s["Maria"], run.pk)
        run = fresh(run)
        self.assertEqual(run.state, TaskState.OFFERED)
        self.assertEqual(run.offered_to, self.s["Dev"])

    def test_escalated_run_can_be_grabbed_by_any_runner_or_taken_by_lead(self):
        run = self.fire()
        engine.decline(self.s["Maria"], run.pk)
        engine.decline(self.s["Dev"], run.pk)
        engine.claim(self.s["Maria"], run.pk)
        self.assertEqual(fresh(run).owner, self.s["Maria"])

    def test_going_off_shift_reroutes_pending_offers(self):
        run = self.fire()
        engine.set_on_shift(self.s["Kim"], self.s["Maria"].pk, False)
        run = fresh(run)
        self.assertEqual(run.offered_to, self.s["Dev"])
        run2 = engine.food_ready(self.s["Sam"], self.t4.pk, 1).task
        self.assertNotEqual(run2.offered_to, self.s["Maria"])
        with self.assertRaises(engine.Forbidden):
            engine.set_on_shift(self.s["Dev"], self.s["Maria"].pk, True)  # only managers change others

    def test_replaying_a_creation_request_does_not_duplicate(self):
        token = str(uuid.uuid4())
        first = engine.food_ready(self.s["Sam"], self.t4.pk, 2, client_token=token)
        again = engine.food_ready(self.s["Sam"], self.t4.pk, 2, client_token=token)
        self.assertTrue(first.created)
        self.assertFalse(again.created)
        self.assertEqual(first.task.pk, again.task.pk)
        self.assertEqual(Task.objects.filter(location=self.loc, kind="run").count(), 1)

    def test_food_ready_requires_expo_and_a_seated_table(self):
        with self.assertRaises(engine.Forbidden):
            engine.food_ready(self.s["Maria"], self.t4.pk)
        with self.assertRaises(engine.Conflict):
            engine.food_ready(self.s["Sam"], table(self.loc, "7").pk)  # not seated
        with self.assertRaises(engine.Invalid):
            engine.stage_course(self.s["Sam"], self.t4.pk)  # Regular Service doesn't stage

    def test_no_runner_on_shift_escalates_straight_to_lead(self):
        for name in ("Maria", "Dev"):
            engine.set_on_shift(self.s["Kim"], self.s[name].pk, False)
        run = self.fire()
        self.assertEqual(run.state, TaskState.ESCALATED)
