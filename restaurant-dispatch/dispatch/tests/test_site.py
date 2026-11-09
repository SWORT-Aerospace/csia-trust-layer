"""Public site, demo isolation, sign-in rules, device pairing, setup wizard."""

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from dispatch import config_ops
from dispatch.models import AuditEvent, Location, Restaurant, SetupSession, StaffMember, Task
from dispatch.seeding import cleanup_expired_demos, parse_staff_lines, parse_table_labels

from .helpers import later, sample


class PublicSiteTests(TestCase):
    def test_homepage_leads_with_copy_and_demo_action(self):
        response = self.client.get("/")
        self.assertContains(response, "Get food off the pass.")
        self.assertContains(response, "Assign food runs, coordinate courses, and close every handoff from one live floor.")
        self.assertContains(response, 'href="/demo/">Try the demo</a>')
        self.assertContains(response, "Staff sign in")
        for preset in ("Captain Release", "Pairing Coordination", "Coordinated Service"):
            self.assertContains(response, preset)
        for forbidden in ("Michelin", "star", "testimonial", "pricing", "$"):
            self.assertNotIn(forbidden.lower(), response.content.decode().lower().replace("start", ""), forbidden)

    @override_settings(DISPATCH_DEMO_ENABLED=False)
    def test_demo_can_be_switched_off(self):
        self.assertEqual(self.client.get("/demo/").status_code, 404)
        self.assertEqual(self.client.post("/demo/start/").status_code, 404)


class DemoSandboxTests(TestCase):
    def start(self, client, profile="regular"):
        response = client.post(reverse("web:demo_start"), {"profile": profile})
        self.assertRedirects(response, reverse("web:demo_floor"))
        return Location.objects.filter(restaurant__demo_owner__isnull=False).order_by("-id").first()

    def test_demo_creates_isolated_sandbox_with_working_personas(self):
        one, two = Client(), Client()
        loc_one = self.start(one)
        loc_two = self.start(two, "coordinated_service")
        self.assertNotEqual(loc_one.restaurant_id, loc_two.restaurant_id)
        floor = one.get(reverse("web:demo_floor"))
        self.assertContains(floor, "Juniper &amp; Pine")
        sam = StaffMember.objects.get(location=loc_one, display_name="Sam")
        self.assertEqual(one.get(reverse("web:screen", args=[sam.pk, "pass"])).status_code, 200)
        # Visitor two cannot reach visitor one's sandbox.
        self.assertEqual(two.get(reverse("web:screen", args=[sam.pk, "pass"])).status_code, 404)
        # Personas keep their own permissions inside the sandbox.
        self.assertEqual(one.get(reverse("web:manage_now", args=[sam.pk])).status_code, 403)

    def test_demo_preset_switch_and_cleanup(self):
        client = Client()
        loc = self.start(client, "captain_release")
        client.post(reverse("web:demo_preset"), {"profile": "pairing_coordination"})
        self.assertEqual(Location.objects.get(pk=loc.pk).profile_key, "pairing_coordination")
        Restaurant.objects.filter(pk=loc.restaurant_id).update(demo_expires_at=later(-60))
        self.assertEqual(cleanup_expired_demos(), 1)
        self.assertFalse(Location.objects.filter(pk=loc.pk).exists())


class SignInTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular", prefix="s-")
        user = self.s["Kim"].user
        user.set_password("a-long-local-password")
        user.save()

    @override_settings(DISPATCH_ALLOW_DEMO_LOGINS=False)
    def test_seeded_demo_accounts_refused_when_demo_logins_off(self):
        response = self.client.post(reverse("web:signin"), {"username": "s-kim", "password": "a-long-local-password"})
        self.assertContains(response, "Demo accounts are switched off")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DISPATCH_ALLOW_DEMO_LOGINS=True)
    def test_password_sign_in_goes_to_staff_screen(self):
        response = self.client.post(reverse("web:signin"), {"username": "s-kim", "password": "a-long-local-password"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kim · Manager")

    def test_device_pairing_code_is_single_use(self):
        StaffMember.objects.filter(pk=self.s["Maria"].pk).update(user=None)
        self.s["Maria"].refresh_from_db()
        code, _ = config_ops.create_pairing_code(self.s["Kim"], self.s["Maria"].pk)
        response = self.client.post(reverse("web:pair"), {"code": code.lower()}, follow=True)
        self.assertContains(response, "Maria · Runner")
        other = Client()
        self.assertContains(other.post(reverse("web:pair"), {"code": code}), "Codes are single-use")
        with self.assertRaises(config_ops.Forbidden):
            config_ops.create_pairing_code(self.s["Maria"], self.s["Dev"].pk)


class SetupWizardTests(TestCase):
    def test_full_wizard_creates_a_working_location_and_records_timing(self):
        c = Client()
        c.get(reverse("web:setup"))
        response = c.post(
            reverse("web:setup"),
            {
                "restaurant": "Test Kitchen",
                "location": "Downtown",
                "your_name": "Morgan",
                "username": "morgan",
                "password": "a-very-long-pass-phrase",
                "password2": "a-very-long-pass-phrase",
            },
        )
        setup = SetupSession.objects.get()
        step = lambda name: reverse("web:setup_step", args=[setup.pk, name])  # noqa: E731
        self.assertRedirects(response, step("edition"))
        self.assertRedirects(c.post(step("edition"), {"profile": "regular"}), step("tables"))
        c.post(step("tables"), {"op": "add", "labels": "Main: 1-6\nPatio: P1-P3"})
        self.assertRedirects(c.post(step("tables"), {"op": "continue"}), step("staff"))
        c.post(step("staff"), {"op": "people", "people": "Maria: runner\nLee: busser\nSam: expo\nAna: host"})
        location = setup.location
        maria = StaffMember.objects.get(location=location, display_name="Maria")
        section = location.sections.get(name="Main")
        self.assertRedirects(c.post(step("staff"), {"op": "coverage", f"{section.pk}-primary_runner": maria.pk}), step("pair"))
        c.post(step("pair"), {"staff": maria.pk})
        self.assertRedirects(c.post(step("pair"), {"op": "continue"}), step("practice"))
        for op in ("seat", "send", "claim", "deliver", "depart", "reset_claim", "reset_done"):
            c.post(step("practice"), {"op": op})
        self.assertRedirects(c.post(step("practice"), {"op": "finish"}), step("done"))
        setup.refresh_from_db()
        self.assertIsNotNone(setup.finished_at)
        self.assertGreaterEqual(setup.duration_seconds, 0)
        self.assertEqual(set(setup.steps) >= {"location", "edition", "tables", "staff", "pair", "practice"}, True)
        self.assertTrue(AuditEvent.objects.filter(location=location, verb="setup.started").exists())
        self.assertTrue(AuditEvent.objects.filter(location=location, verb="setup.finished").exists())
        practice = Task.objects.filter(location=location, is_practice=True)
        self.assertEqual(sorted(practice.values_list("kind", "state")), [("reset", "completed"), ("run", "completed")])
        self.assertEqual(location.tables.get(label="1").state, "ready")
        self.assertContains(c.get(step("done")), "is ready")


class ParsingTests(TestCase):
    def test_table_label_parsing(self):
        self.assertEqual(
            parse_table_labels("Main: 1-3, 10\nPatio: P1-P2\nBar 1"),
            [("Main", ["1", "2", "3", "10", "Bar 1"]), ("Patio", ["P1", "P2"])],
        )

    def test_staff_line_parsing(self):
        self.assertEqual(
            parse_staff_lines("Maria: runner, busser\nRae: floor lead\nJordan - somm"),
            [("Maria", ["runner", "busser"]), ("Rae", ["lead"]), ("Jordan", ["sommelier"])],
        )


class SeedCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_seed_refuses_outside_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo")
