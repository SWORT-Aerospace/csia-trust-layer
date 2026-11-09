"""Fine Dining: holds at the pass, captain release, and the three presets."""

from django.test import TestCase

from dispatch import config_ops, engine, selectors
from dispatch.states import OfferStage, PairingStatus, TaskState

from .helpers import fresh, later, sample, table


class CaptainReleaseTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("captain_release", prefix="f-")
        self.t3 = table(self.loc, "3")

    def stage(self):
        return engine.stage_course(self.s["Noor"], self.t3.pk).task

    def test_staged_course_is_invisible_to_runners_until_release(self):
        course = self.stage()
        self.assertEqual(course.state, TaskState.STAGED)
        self.assertEqual(course.course_number, 1)
        board = selectors.runner_board(self.s["Mateo"])
        self.assertNotIn(course, [*board["offers"], *board["mine"], *board["open_pool"]])
        with self.assertRaises(engine.NotFound):
            engine.claim(self.s["Mateo"], course.pk)

    def test_captain_holds_and_releases_to_one_runner(self):
        course = self.stage()
        with self.assertRaises(engine.Forbidden):
            engine.release_course(self.s["Mateo"], course.pk)
        engine.release_course(self.s["Elise"], course.pk, self.s["Priya"].pk)
        course = fresh(course)
        self.assertEqual((course.state, course.offered_to, course.offer_stage), (TaskState.OFFERED, self.s["Priya"], OfferStage.ASSIGNED))
        self.assertEqual(course.released_by, self.s["Elise"])
        engine.claim(self.s["Priya"], course.pk)
        engine.complete(self.s["Priya"], course.pk)
        self.assertEqual(fresh(course).state, TaskState.COMPLETED)

    def test_missed_offer_returns_to_captain_who_can_hold_or_reoffer(self):
        course = self.stage()
        engine.release_course(self.s["Elise"], course.pk)
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + 1))
        course = fresh(course)
        self.assertEqual((course.state, course.escalated_to_role), (TaskState.ESCALATED, "captain"))
        with self.assertRaises(engine.Conflict):
            engine.claim(self.s["Priya"], course.pk)  # runners don't grab returned courses
        engine.hold_course(self.s["Elise"], course.pk)
        self.assertEqual(fresh(course).state, TaskState.STAGED)
        engine.release_course(self.s["Elise"], course.pk, self.s["Priya"].pk)
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + 1))
        engine.offer_to(self.s["Elise"], course.pk, self.s["Mateo"].pk)
        self.assertEqual(fresh(course).offered_to, self.s["Mateo"])

    def test_claimed_course_cannot_be_put_back_on_hold(self):
        course = self.stage()
        engine.release_course(self.s["Elise"], course.pk, self.s["Mateo"].pk)
        engine.claim(self.s["Mateo"], course.pk)
        with self.assertRaises(engine.Conflict):
            engine.hold_course(self.s["Elise"], course.pk)

    def test_food_ready_is_not_available_in_fine_dining(self):
        with self.assertRaises(engine.Invalid):
            engine.food_ready(self.s["Noor"], self.t3.pk)


class PairingCoordinationTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("pairing_coordination", prefix="p-")
        self.t3 = table(self.loc, "3")

    def test_early_release_rejected_until_pairing_resolved_by_sommelier(self):
        course = engine.stage_course(self.s["Noor"], self.t3.pk).task
        self.assertEqual(course.pairing_status, PairingStatus.PENDING)
        with self.assertRaises(engine.Conflict) as ctx:
            engine.release_course(self.s["Elise"], course.pk)
        self.assertEqual(ctx.exception.code, "not_ready")
        self.assertEqual(fresh(course).state, TaskState.STAGED)
        with self.assertRaises(engine.Forbidden):
            engine.confirm_pairing(self.s["Elise"], course.pk)  # captain isn't the sommelier
        engine.confirm_pairing(self.s["Jordan"], course.pk)
        course = fresh(course)
        self.assertEqual((course.pairing_status, course.pairing_resolved_by), (PairingStatus.READY, self.s["Jordan"]))
        self.assertIsNotNone(course.pairing_resolved_at)
        engine.release_course(self.s["Elise"], course.pk)
        self.assertEqual(fresh(course).state, TaskState.OFFERED)

    def test_captain_can_mark_course_as_needing_no_pairing(self):
        course = engine.stage_course(self.s["Noor"], self.t3.pk).task
        with self.assertRaises(engine.Forbidden):
            engine.mark_no_pairing(self.s["Jordan"], course.pk)
        engine.mark_no_pairing(self.s["Elise"], course.pk)
        course = fresh(course)
        self.assertEqual((course.pairing_status, course.pairing_resolved_by), (PairingStatus.NOT_NEEDED, self.s["Elise"]))
        with self.assertRaises(engine.Conflict):
            engine.confirm_pairing(self.s["Jordan"], course.pk)
        engine.release_course(self.s["Elise"], course.pk)

    def test_sommelier_sees_pending_courses(self):
        course = engine.stage_course(self.s["Noor"], self.t3.pk).task
        self.assertIn(course, list(selectors.sommelier_board(self.s["Jordan"])["pending"]))


class CoordinatedServiceTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("coordinated_service", prefix="c-")
        self.t3 = table(self.loc, "3")

    def test_release_rejected_until_pairing_and_team_readiness_confirmed(self):
        course = engine.stage_course(self.s["Noor"], self.t3.pk).task
        engine.confirm_pairing(self.s["Jordan"], course.pk)
        with self.assertRaises(engine.Conflict) as ctx:
            engine.release_course(self.s["Elise"], course.pk)
        self.assertIn("team is ready", ctx.exception.message)
        with self.assertRaises(engine.Forbidden):
            engine.confirm_team_ready(self.s["Mateo"], course.pk)
        engine.confirm_team_ready(self.s["Elise"], course.pk)
        course = fresh(course)
        self.assertEqual(course.team_ready_by, self.s["Elise"])
        engine.release_course(self.s["Elise"], course.pk)
        course = fresh(course)
        self.assertEqual(course.state, TaskState.OFFERED)
        self.assertIsNotNone(course.offered_to)  # exactly one runner

    def test_team_readiness_alone_is_not_enough(self):
        course = engine.stage_course(self.s["Noor"], self.t3.pk).task
        engine.confirm_team_ready(self.s["Elise"], course.pk)
        with self.assertRaises(engine.Conflict):
            engine.release_course(self.s["Elise"], course.pk)


class PresetSwitchTests(TestCase):
    def test_switching_presets_changes_rules_without_new_code_paths(self):
        loc, s = sample("captain_release", prefix="w-")
        t3 = table(loc, "3")
        course = engine.stage_course(s["Noor"], t3.pk).task
        config_ops.update_rules(s["Kim"], profile_key="coordinated_service")
        s["Elise"].location.refresh_from_db()
        with self.assertRaises(engine.Conflict):
            engine.release_course(s["Elise"], course.pk)  # checks now apply
        with self.assertRaises(engine.Conflict):
            config_ops.update_rules(s["Kim"], profile_key="regular")  # edition change needs an empty pass
        with self.assertRaises(engine.Forbidden):
            config_ops.update_rules(s["Elise"], profile_key="captain_release")  # captain isn't a manager
