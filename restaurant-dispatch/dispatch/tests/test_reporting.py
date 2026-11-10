"""Shift report: derived metrics, shift windows, export scope and safety."""

import csv
import io
import zoneinfo
from datetime import date, datetime, time, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from dispatch import engine, reporting
from dispatch.models import AuditEvent, ShiftObservation, StaffMember, Table, Task
from dispatch.reporting import ShiftFilter, Stat, percentile

from .helpers import fresh, later, sample, table

NY = zoneinfo.ZoneInfo("America/New_York")


def local(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=NY)


def retime(task, **fields):
    Task.objects.filter(pk=task.pk).update(**fields)
    return fresh(task)


def day_filter(d):
    return ShiftFilter(d, d, time(4), time(4), "day", "day")


class PercentileTests(TestCase):
    def test_median_and_p90_use_linear_interpolation(self):
        values = list(range(1, 11))  # 1..10
        self.assertEqual(percentile(values, 0.5), 5.5)
        self.assertAlmostEqual(percentile(values, 0.9), 9.1)
        self.assertIsNone(percentile([], 0.5))
        stat = Stat.of([30, None, 10, 20])
        self.assertEqual((stat.n, stat.median), (3, 20))
        self.assertTrue(stat.small)
        self.assertFalse(Stat.of(list(range(25))).small)


class RegularReportTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular", prefix="rp-")
        Task.objects.filter(location=self.loc).delete()  # drop the seeded reset
        self.t0 = local(2026, 11, 9, 19, 0)

    def make_run(self, label, ready, done_after=None):
        run = engine.food_ready(self.s["Sam"], table(self.loc, label).pk).task
        engine.claim(run.offered_to, run.pk)
        if done_after is not None:
            engine.complete(fresh(run).owner, run.pk)
            return retime(run, ready_at=ready, completed_at=ready + timedelta(seconds=done_after))
        return retime(run, ready_at=ready)

    def test_only_completed_runs_produce_handoff_times(self):
        self.make_run("4", self.t0, 40)
        self.make_run("5", self.t0 + timedelta(minutes=5), 80)
        open_run = self.make_run("6", self.t0 + timedelta(minutes=6))
        cancelled = engine.food_ready(self.s["Sam"], table(self.loc, "1").pk).task
        retime(cancelled, ready_at=self.t0, state="cancelled")
        report = reporting.build(self.loc, day_filter(date(2026, 11, 9)))
        self.assertEqual(report["runs"].n, 2)
        self.assertEqual(report["runs"].median, 60)
        self.assertEqual(report["outcomes"]["run"], {"completed": 2, "open": 1, "cancelled": 1})
        open_row = next(r for r in report["rows"] if r.task.pk == open_run.pk)
        self.assertIsNone(open_row.ready_to_done)  # an open run is never a delivery

    def test_counts_are_distinct_and_interventions_are_explicit(self):
        # Run A: Maria misses, Dev misses -> escalates -> lead assigns (1 intervention).
        a = engine.food_ready(self.s["Sam"], table(self.loc, "4").pk).task
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + 1))
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + self.loc.backup_timeout_seconds + 2))
        engine.assign(self.s["Rae"], a.pk, self.s["Maria"].pk)
        # Run B: Maria declines -> backup Dev; lead takes it over from Dev (1 intervention).
        b = engine.food_ready(self.s["Sam"], table(self.loc, "5").pk).task
        engine.decline(self.s["Maria"], b.pk)
        engine.claim(self.s["Rae"], b.pk)
        # Table override (no task, 1 intervention).
        reset = engine.mark_departed(self.s["Ana"], table(self.loc, "1").pk).task
        engine.seat_override(self.s["Rae"], table(self.loc, "1").pk, 2)
        today = reporting.service_date(self.loc)
        counts = reporting.build(self.loc, day_filter(today))["counts"]
        self.assertEqual(counts["missed_offers"], 2)  # per offer
        self.assertEqual(counts["declined_offers"], 1)
        self.assertEqual(counts["routed_to_backup"], 2)  # per task: A and B
        self.assertEqual(counts["escalated"], 1)  # only A ran out of people
        self.assertEqual(counts["interventions"], 3)
        self.assertEqual(fresh(reset).state, "cancelled")

    def test_overnight_shift_crosses_midnight_in_local_time(self):
        late_evening = self.make_run("4", local(2026, 11, 9, 23, 30), 30)
        after_midnight = self.make_run("5", local(2026, 11, 10, 1, 30), 30)
        next_morning = self.make_run("6", local(2026, 11, 10, 3, 0), 30)
        late = ShiftFilter(date(2026, 11, 9), date(2026, 11, 9), time(21), time(2), "late", "late")
        self.assertTrue(late.crosses_midnight)
        ids = {r.task.pk for r in reporting.build(self.loc, late)["rows"]}
        self.assertEqual(ids, {late_evening.pk, after_midnight.pk})
        next_night = ShiftFilter(date(2026, 11, 10), date(2026, 11, 10), time(21), time(2), "late", "late")
        self.assertEqual(reporting.build(self.loc, next_night)["rows"], [])
        whole_day = {r.task.pk for r in reporting.build(self.loc, day_filter(date(2026, 11, 9)))["rows"]}
        self.assertEqual(whole_day, {late_evening.pk, after_midnight.pk, next_morning.pk})

    def test_reset_times_filter_by_recorded_waitlist(self):
        engine.set_waitlist(self.s["Ana"], True)
        busy = engine.mark_departed(self.s["Ana"], table(self.loc, "1").pk).task
        engine.set_waitlist(self.s["Ana"], False)
        quiet = engine.mark_departed(self.s["Ana"], table(self.loc, "2").pk).task
        for reset, seconds in ((busy, 50), (quiet, 300)):
            engine.claim(fresh(reset).offered_to, reset.pk)
            engine.complete(fresh(reset).owner, reset.pk)
            retime(reset, ready_at=self.t0, completed_at=self.t0 + timedelta(seconds=seconds))
        self.assertTrue(fresh(busy).waitlist_active)
        self.assertFalse(fresh(quiet).waitlist_active)
        d = date(2026, 11, 9)
        self.assertEqual(reporting.build(self.loc, day_filter(d), "waiting")["resets"].median, 50)
        self.assertEqual(reporting.build(self.loc, day_filter(d), "no_wait")["resets"].median, 300)
        self.assertEqual(reporting.build(self.loc, day_filter(d))["resets"].n, 2)
        with self.assertRaises(engine.Forbidden):
            engine.set_waitlist(self.s["Maria"], True)

    def test_practice_tickets_are_excluded(self):
        practice = engine.food_ready(self.s["Kim"], table(self.loc, "4").pk, practice=True).task
        retime(practice, ready_at=self.t0)
        self.assertEqual(reporting.build(self.loc, day_filter(date(2026, 11, 9)))["rows"], [])


class FineDiningReportTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("captain_release", prefix="fr-")
        Task.objects.filter(location=self.loc).delete()
        self.t0 = local(2026, 11, 9, 20, 0)

    def set_event_times(self, task, times):
        events = list(AuditEvent.objects.filter(task=task, verb__in=list(times)).order_by("at", "id"))
        seen = {}
        for e in events:
            idx = seen.get(e.verb, 0)
            AuditEvent.objects.filter(pk=e.pk).update(at=times[e.verb][idx])
            seen[e.verb] = idx + 1

    def test_hold_time_is_separate_from_release_to_delivery(self):
        c = engine.stage_course(self.s["Noor"], table(self.loc, "3").pk).task
        engine.release_course(self.s["Elise"], c.pk, self.s["Mateo"].pk)
        engine.claim(self.s["Mateo"], c.pk)
        engine.complete(self.s["Mateo"], c.pk)
        t = self.t0
        retime(c, ready_at=t, staged_at=t, released_at=t + timedelta(seconds=60), completed_at=t + timedelta(seconds=90))
        self.set_event_times(c, {"course.released": [t + timedelta(seconds=60)]})
        r = reporting.build(self.loc, day_filter(date(2026, 11, 9)))
        self.assertEqual((r["courses_held"].median, r["courses_release"].median, r["courses_total"].median), (60, 30, 90))

    def test_rehold_after_a_missed_offer_counts_only_intentional_hold(self):
        c = engine.stage_course(self.s["Noor"], table(self.loc, "3").pk).task
        engine.release_course(self.s["Elise"], c.pk, self.s["Mateo"].pk)
        engine.expire_due_offers(now=later(self.loc.offer_timeout_seconds + 1))  # back to captain
        engine.hold_course(self.s["Elise"], c.pk)
        engine.release_course(self.s["Elise"], c.pk, self.s["Priya"].pk)
        engine.claim(self.s["Priya"], c.pk)
        engine.complete(self.s["Priya"], c.pk)
        t = self.t0
        s = lambda n: t + timedelta(seconds=n)  # noqa: E731
        retime(c, ready_at=t, staged_at=t, released_at=s(100), completed_at=s(130))
        self.set_event_times(c, {"course.released": [s(60), s(100)], "course.held": [s(80)]})
        row = reporting.build(self.loc, day_filter(date(2026, 11, 9)))["rows"][0]
        self.assertEqual(row.held_at_pass, 80)  # 0-60 staged + 80-100 re-held; 60-80 was a missed offer
        self.assertEqual(row.release_to_delivery, 30)
        self.assertEqual(row.ready_to_done, 130)
        self.assertEqual(row.missed_offers, 1)

    def test_staged_course_is_unresolved_not_a_delivery(self):
        c = engine.stage_course(self.s["Noor"], table(self.loc, "3").pk).task
        retime(c, ready_at=self.t0, staged_at=self.t0)
        r = reporting.build(self.loc, day_filter(date(2026, 11, 9)))
        self.assertEqual(r["courses_total"].n, 0)
        self.assertEqual(r["outcomes"]["course"]["open"], 1)


class ReportAccessAndExportTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular", prefix="ra-")
        self.other, self.o = sample("regular", prefix="rb-")
        self.client = Client()

    def test_report_and_export_are_manager_only(self):
        self.client.force_login(self.s["Maria"].user)
        sid = self.s["Maria"].pk
        self.assertEqual(self.client.get(reverse("web:manage_report", args=[sid])).status_code, 403)
        self.assertEqual(self.client.get(reverse("web:manage_report_csv", args=[sid])).status_code, 403)
        self.client.force_login(self.s["Rae"].user)  # floor lead: not a manager
        self.assertEqual(self.client.get(reverse("web:manage_report_csv", args=[self.s["Rae"].pk])).status_code, 403)

    def test_export_cannot_reach_another_location(self):
        self.client.force_login(self.s["Kim"].user)
        other_manager = self.o["Kim"].pk
        self.assertEqual(self.client.get(reverse("web:manage_report_csv", args=[other_manager])).status_code, 404)
        self.assertEqual(self.client.get(reverse("web:manage_report", args=[other_manager])).status_code, 404)
        # Query parameters can't redirect the export to another location either.
        theirs = engine.food_ready(self.o["Sam"], table(self.other, "4").pk).task
        response = self.client.get(
            reverse("web:manage_report_csv", args=[self.s["Kim"].pk]) + f"?location={self.other.pk}&sid={self.o['Kim'].pk}"
        )
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))[1:]
        exported = {int(row[2]) for row in rows}
        self.assertNotIn(theirs.pk, exported)
        self.assertTrue(exported <= set(Task.objects.filter(location=self.loc).values_list("pk", flat=True)))

    def test_export_escapes_formulas_and_contains_no_names(self):
        Table.objects.filter(pk=table(self.loc, "4").pk).update(label="=HYPERLINK(1)")
        engine.food_ready(self.s["Sam"], table(self.loc, "=HYPERLINK(1)").pk, note="+SUM(A1)")
        self.client.force_login(self.s["Kim"].user)
        response = self.client.get(reverse("web:manage_report_csv", args=[self.s["Kim"].pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        header, body = rows[0], rows[1:]
        self.assertEqual(header, reporting.CSV_HEADER)
        cells = [cell for row in body for cell in row]
        self.assertIn("'=HYPERLINK(1)", cells)
        self.assertFalse(any(cell.startswith(("=", "+", "@")) for cell in cells))
        self.assertNotIn("+SUM(A1)", response.content.decode())  # notes are never exported
        for member in StaffMember.objects.filter(location=self.loc):
            self.assertNotIn(member.display_name, cells)
        self.assertTrue(AuditEvent.objects.filter(location=self.loc, verb="report.export").exists())

    def test_demo_locations_are_flagged_in_report_and_export(self):
        self.client.post(reverse("web:demo_start"), {"profile": "regular"})
        kim = StaffMember.objects.filter(location__restaurant__demo_owner__isnull=False, display_name="Kim").first()
        page = self.client.get(reverse("web:manage_report", args=[kim.pk]))
        self.assertContains(page, "nothing here can count as pilot evidence")
        rows = list(csv.reader(io.StringIO(self.client.get(reverse("web:manage_report_csv", args=[kim.pk])).content.decode("utf-8-sig"))))
        self.assertTrue(all(row[0] == "demo" for row in rows[1:]))

    def test_manual_observations_stay_separate_and_drive_proposed_targets(self):
        from dispatch.models import Restaurant

        Restaurant.objects.filter(pk=self.loc.restaurant_id).update(is_demo=False)  # a real pilot venue
        self.client.force_login(self.s["Kim"].user)
        url = reverse("web:manage_report", args=[self.s["Kim"].pk]) + "?from=2026-11-09&to=2026-11-09&shift=dinner"
        form = {
            "source": "baseline", "service_date": "2026-11-09", "shift_label": "Dinner",
            "start_time": "17:00", "end_time": "23:00", "covers": "120", "waitlist": "some",
            "waitlist_peak_parties": "4", "staff_runners": "2", "staff_bussers": "2", "staff_servers": "4",
            "staff_hosts": "1", "staff_managers": "1", "order_errors": "3", "guest_complaints": "1",
            "manager_interventions": "12", "food_handoff_p90_seconds": "100", "food_handoff_samples": "25",
            "reset_p90_seconds": "400", "reset_samples": "20", "method": "Stopwatch at the pass", "notes": "",
        }
        self.assertEqual(self.client.post(url, form).status_code, 302)
        syncora = {**form, "source": "syncora", "food_handoff_p90_seconds": "5", "manager_interventions": ""}
        self.client.post(url, syncora)
        observations = ShiftObservation.objects.filter(location=self.loc).order_by("source")
        self.assertEqual([o.source for o in observations], ["baseline", "syncora"])
        self.assertIsNone(observations[1].food_handoff_p90_seconds)  # never a stopwatch number for Syncora shifts
        # 20 Syncora runs at 70s during that dinner beat the 100s baseline p90 by 30%.
        t0 = local(2026, 11, 9, 18, 0)
        for i in range(20):
            run = engine.food_ready(self.s["Sam"], table(self.loc, "4").pk).task
            engine.claim(fresh(run).offered_to, run.pk)
            engine.complete(fresh(run).owner, run.pk)
            retime(run, ready_at=t0 + timedelta(minutes=i), completed_at=t0 + timedelta(minutes=i, seconds=70))
        page = self.client.get(url)
        self.assertContains(page, "not Syncora event data")
        rows = page.context["comparison"]
        self.assertEqual(rows[0]["change"], -30.0)
        self.assertEqual(rows[0]["verdict"], "Meets proposed target")  # -30% beats the proposed -20%
        self.assertEqual(rows[1]["verdict"], "Not enough measured data yet")  # no Syncora resets that dinner
