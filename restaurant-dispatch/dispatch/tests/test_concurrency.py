"""Races on real, separate database connections (file-backed test DB)."""

import threading
import uuid

from django.db import connection, connections
from django.test import TransactionTestCase

from dispatch import engine
from dispatch.models import Task
from dispatch.states import TaskState

from .helpers import fresh, later, sample, table


def race(*callables):
    """Run callables at the same instant in separate threads/connections."""
    barrier = threading.Barrier(len(callables))
    results = [None] * len(callables)

    def runner(i, fn):
        try:
            barrier.wait()
            results[i] = ("ok", fn())
        except engine.DispatchError as error:
            results[i] = ("conflict", error)
        except Exception as error:  # surface unexpected failures to the test
            results[i] = ("error", error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=runner, args=(i, fn)) for i, fn in enumerate(callables)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor == "sqlite" and ":memory:" in str(connection.settings_dict["NAME"]):
            self.skipTest("needs a file-backed SQLite test DB")
        self.loc, self.s = sample("regular", prefix="r-")
        self.t4 = table(self.loc, "4")

    def escalated_run(self):
        run = engine.food_ready(self.s["Sam"], self.t4.pk).task
        engine.decline(self.s["Maria"], run.pk)
        engine.decline(self.s["Dev"], run.pk)
        self.assertEqual(fresh(run).state, TaskState.ESCALATED)
        return run

    def test_two_simultaneous_claims_yield_exactly_one_owner(self):
        for _ in range(5):
            run = self.escalated_run()
            maria, dev = self.s["Maria"], self.s["Dev"]
            results = race(lambda: engine.claim(maria, run.pk), lambda: engine.claim(dev, run.pk))
            outcomes = sorted(r[0] for r in results)
            self.assertEqual(outcomes, ["conflict", "ok"], results)
            run = fresh(run)
            winner = maria if results[0][0] == "ok" else dev
            self.assertEqual((run.state, run.owner), (TaskState.CLAIMED, winner))
            loser_message = next(r[1].message for r in results if r[0] == "conflict")
            self.assertIn(winner.display_name, loser_message)
            engine.complete(winner, run.pk)

    def test_claim_racing_the_expiry_timer_never_produces_two_owners(self):
        for _ in range(5):
            run = engine.food_ready(self.s["Sam"], self.t4.pk).task
            maria = self.s["Maria"]
            results = race(lambda: engine.claim(maria, run.pk), lambda: engine.expire_due_offers(now=later(120)))
            run = fresh(run)
            if results[0][0] == "ok":
                self.assertEqual((run.state, run.owner), (TaskState.CLAIMED, maria))
                engine.complete(maria, run.pk)
            else:
                self.assertEqual(results[0][0], "conflict")
                self.assertNotEqual(run.offered_to, maria)
                self.assertIsNone(run.owner)
                Task.objects.filter(pk=run.pk).update(state=TaskState.CANCELLED)

    def test_replayed_creation_racing_itself_creates_one_task(self):
        token = str(uuid.uuid4())
        sam = self.s["Sam"]
        results = race(*(lambda: engine.food_ready(sam, self.t4.pk, 1, client_token=token) for _ in range(3)))
        self.assertTrue(all(r[0] == "ok" for r in results), results)
        self.assertEqual(len({r[1].task.pk for r in results}), 1)
        self.assertEqual(Task.objects.filter(client_token=token).count(), 1)

    def test_simultaneous_departure_taps_create_one_reset(self):
        t1 = table(self.loc, "1")
        ana, theo = self.s["Ana"], self.s["Theo"]
        results = race(lambda: engine.mark_departed(ana, t1.pk), lambda: engine.mark_departed(theo, t1.pk))
        self.assertNotIn("error", [r[0] for r in results], results)
        self.assertEqual(Task.objects.filter(table=t1, kind="reset").exclude(state="cancelled").count(), 1)
