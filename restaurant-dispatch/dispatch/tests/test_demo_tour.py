"""Guided demo tour: real engine actions, the real timer, isolated sandboxes."""

from django.test import Client, TestCase
from django.urls import reverse

from dispatch import engine
from dispatch.models import Location, Table, Task
from dispatch.seeding import DEMO_BACKUP_SECONDS, DEMO_OFFER_SECONDS

from .helpers import later, sample


def start(client, profile="regular"):
    client.post(reverse("web:demo_start"), {"profile": profile})
    return Location.objects.filter(restaurant__demo_owner__isnull=False).order_by("-id").first()


def state(client):
    return client.get(reverse("web:tour_state")).json()


def do(client, key):
    return client.post(reverse("web:tour_do"), {"step": key})


class RegularTourTests(TestCase):
    def test_tour_runs_real_actions_and_waits_for_the_timer(self):
        c = Client()
        loc = start(c)
        self.assertEqual((loc.offer_timeout_seconds, loc.backup_timeout_seconds), (DEMO_OFFER_SECONDS, DEMO_BACKUP_SECONDS))
        self.assertEqual(state(c)["steps"][0]["key"], "fire")
        self.assertEqual(do(c, "backup_claim").status_code, 409)  # steps can't be skipped
        self.assertEqual(do(c, "fire").json()["ok"], True)
        run = Task.objects.get(location=loc, kind="run")
        self.assertEqual(run.offered_to.display_name, "Maria")
        current = state(c)["steps"][state(c)["current"]]
        self.assertEqual((current["key"], current["waiting"], current["action"]), ("expire", True, None))
        self.assertEqual(do(c, "expire").status_code, 409)  # only the timer worker moves it on
        upcoming = state(c)["steps"]
        self.assertTrue(upcoming[2]["title"].startswith("Dev claims"), upcoming[2]["title"])  # backup, not Maria
        self.assertNotIn("table the table", upcoming[-1]["title"])
        engine.expire_due_offers(now=later(DEMO_OFFER_SECONDS + 1))  # what the worker does
        s = state(c)
        self.assertEqual(s["steps"][s["current"]]["key"], "backup_claim")
        self.assertIn("Dev", s["steps"][s["current"]]["action"])
        for key in ("backup_claim", "deliver", "depart", "reset_claim", "reset_done"):
            response = do(c, key)
            self.assertEqual(response.status_code, 200, (key, response.content))
        self.assertEqual(Task.objects.get(pk=run.pk).state, "completed")
        reset = Task.objects.get(location=loc, kind="reset", state="completed")
        self.assertEqual(Table.objects.get(pk=reset.table_id).state, "ready")  # reset reached the host
        do(c, "host_sees")
        self.assertTrue(state(c)["complete"])

    def test_tour_is_scoped_to_the_visitors_own_sandbox(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse("web:tour_state")).status_code, 404)
        loc_real, s = sample("regular", prefix="tr-")
        staff = Client()
        staff.force_login(s["Kim"].user)
        self.assertEqual(staff.get(reverse("web:tour_state")).status_code, 404)  # no sandbox, no tour
        one, two = Client(), Client()
        loc_one, loc_two = start(one), start(two)
        do(one, "fire")
        self.assertTrue(Task.objects.filter(location=loc_one, kind="run").exists())
        self.assertFalse(Task.objects.filter(location=loc_two, kind="run").exists())
        self.assertFalse(Task.objects.filter(location=loc_real, kind="run").exists())
        self.assertEqual(state(two)["current"], 0)

    def test_tour_post_requires_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        start(Client())  # unrelated sandbox
        strict.get(reverse("web:demo"))
        response = strict.post(reverse("web:tour_do"), {"step": "fire"})
        self.assertEqual(response.status_code, 403)


class FineTourTests(TestCase):
    def test_pairing_preset_shows_the_servers_refusal_then_clears(self):
        c = Client()
        loc = start(c, "pairing_coordination")
        keys = [step["key"] for step in state(c)["steps"]]
        self.assertEqual(keys, ["stage", "try_release", "pairing", "release", "claim", "deliver"])
        do(c, "stage")
        course = Task.objects.get(location=loc, kind="course", course_number__isnull=False, table__label="3")
        self.assertEqual(course.state, "staged")
        refused = do(c, "try_release").json()
        self.assertEqual(refused["tone"], "refused")
        self.assertIn("Can't release yet", refused["message"])
        self.assertEqual(Task.objects.get(pk=course.pk).state, "staged")  # the refusal was real
        for key in ("pairing", "release", "claim", "deliver"):
            self.assertEqual(do(c, key).status_code, 200, key)
        course.refresh_from_db()
        self.assertEqual((course.state, course.pairing_resolved_by.display_name), ("completed", "Jordan"))
        final = state(c)
        self.assertTrue(final["complete"])
        self.assertIn("Held at the pass", final["steps"][-1]["note"])

    def test_coordinated_service_adds_team_readiness(self):
        c = Client()
        start(c, "coordinated_service")
        keys = [step["key"] for step in state(c)["steps"]]
        self.assertIn("team", keys)
        self.assertLess(keys.index("team"), keys.index("release"))
