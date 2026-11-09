"""Server-side enforcement over HTTP: CSRF, tenant scope, roles, idempotency."""

import uuid

from django.test import Client, TestCase
from django.urls import reverse

from dispatch import engine
from dispatch.models import Table, Task

from .helpers import sample, table

FETCH = {"HTTP_X_DISPATCH_FETCH": "1"}


def act(sid, action):
    return reverse("web:act", args=[sid, action])


class HttpEnforcementTests(TestCase):
    def setUp(self):
        self.loc_a, self.a = sample("regular", prefix="a-")
        self.loc_b, self.b = sample("pairing_coordination", prefix="b-")
        self.client = Client()

    def login(self, member):
        self.client.force_login(member.user)
        return member.pk

    def test_actions_require_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.a["Sam"].user)
        response = strict.post(act(self.a["Sam"].pk, "food_ready"), {"table": table(self.loc_a, "4").pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(location=self.loc_a, kind="run").exists())

    def test_anonymous_users_are_sent_to_sign_in(self):
        response = self.client.get(reverse("web:screen", args=[self.a["Maria"].pk, "runs"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("web:signin"), response["Location"])

    def test_staff_cannot_open_another_users_or_locations_screens(self):
        self.login(self.a["Maria"])
        for member in (self.b["Mateo"], self.a["Dev"]):
            self.assertEqual(self.client.get(reverse("web:staff_home", args=[member.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse("web:live", args=[member.pk, "runs"])).status_code, 404)

    def test_staff_cannot_act_on_another_locations_tasks(self):
        course = engine.stage_course(self.b["Noor"], table(self.loc_b, "3").pk).task
        engine.confirm_pairing(self.b["Jordan"], course.pk)
        engine.release_course(self.b["Elise"], course.pk, self.b["Mateo"].pk)
        sid = self.login(self.a["Maria"])
        response = self.client.post(act(sid, "claim"), {"task": course.pk}, **FETCH)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Task.objects.get(pk=course.pk).state, "offered")
        # Location B's tables are equally out of reach.
        sid = self.login(self.a["Ana"])
        response = self.client.post(act(sid, "depart"), {"table": table(self.loc_b, "1").pk}, **FETCH)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(table(self.loc_b, "1").state, "occupied")

    def test_runner_cannot_perform_captain_or_manager_actions(self):
        course = engine.stage_course(self.b["Noor"], table(self.loc_b, "3").pk).task
        sid = self.login(self.b["Mateo"])
        for action in ("release_course", "hold", "no_pairing", "team_ready", "pairing_ready"):
            response = self.client.post(act(sid, action), {"task": course.pk}, **FETCH)
            self.assertIn(response.status_code, (403, 404), action)
        self.assertEqual(Task.objects.get(pk=course.pk).state, "staged")
        self.assertEqual(self.client.get(reverse("web:screen", args=[sid, "captain"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("web:manage_now", args=[sid])).status_code, 403)
        before = Table.objects.filter(location=self.loc_b).count()
        response = self.client.post(reverse("web:manage_floor", args=[sid]), {"op": "add_tables", "labels": "Z1-Z9"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Table.objects.filter(location=self.loc_b).count(), before)

    def test_server_cannot_change_configuration_or_assign(self):
        sid = self.login(self.a["Theo"])
        self.assertEqual(self.client.post(reverse("web:manage_rules", args=[sid]), {"profile": "captain_release"}).status_code, 403)
        run = engine.food_ready(self.a["Sam"], table(self.loc_a, "4").pk).task
        response = self.client.post(act(sid, "assign"), {"task": run.pk, "staff": self.a["Dev"].pk}, **FETCH)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["ok"], False)

    def test_full_regular_flow_over_http(self):
        sid = self.login(self.a["Sam"])
        token = str(uuid.uuid4())
        payload = {"table": table(self.loc_a, "4").pk, "items": 3, "client_token": token}
        first = self.client.post(act(sid, "food_ready"), payload, **FETCH)
        second = self.client.post(act(sid, "food_ready"), payload, **FETCH)  # double tap
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["created"])
        self.assertFalse(second.json()["created"])
        run = Task.objects.get(location=self.loc_a, kind="run")
        maria = self.login(self.a["Maria"])
        live = self.client.get(reverse("web:live", args=[maria, "runs"]))
        self.assertContains(live, "Table 4 · 3 plates")
        self.assertContains(live, "Offered to you")
        self.assertEqual(self.client.post(act(maria, "claim"), {"task": run.pk}, **FETCH).status_code, 200)
        dev = self.login(self.a["Dev"])
        lost = self.client.post(act(dev, "claim"), {"task": run.pk}, **FETCH)
        self.assertEqual(lost.status_code, 409)
        self.assertIn("Maria", lost.json()["message"])
        maria = self.login(self.a["Maria"])
        self.assertEqual(self.client.post(act(maria, "complete"), {"task": run.pk}, **FETCH).status_code, 200)
        self.assertEqual(Task.objects.get(pk=run.pk).state, "completed")

    def test_staged_course_absent_from_runner_screen_until_released(self):
        course = engine.stage_course(self.b["Noor"], table(self.loc_b, "3").pk).task
        sid = self.login(self.b["Mateo"])
        self.assertNotContains(self.client.get(reverse("web:live", args=[sid, "runs"])), course.title)
        engine.confirm_pairing(self.b["Jordan"], course.pk)
        engine.release_course(self.b["Elise"], course.pk, self.b["Mateo"].pk)
        self.assertContains(self.client.get(reverse("web:live", args=[sid, "runs"])), course.title)

    def test_non_js_form_post_redirects_with_message(self):
        sid = self.login(self.a["Ana"])
        response = self.client.post(act(sid, "seat"), {"table": table(self.loc_a, "7").pk, "party": 2, "next": "https://evil.example/"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/app/"))  # open redirect refused

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertIn("geolocation=()", response["Permissions-Policy"])
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
