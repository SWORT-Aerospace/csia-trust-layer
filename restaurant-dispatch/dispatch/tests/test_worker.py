"""Offer expiration runs in its own process, independent of any browser."""

import os
import subprocess
import sys
import time
from urllib.parse import quote
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from dispatch import config_ops, engine
from dispatch.models import Task, WorkerHeartbeat
from dispatch.selectors import WORKER_NAME, worker_status
from dispatch.states import TaskState

from .helpers import fresh, sample, table


class WorkerCommandTests(TestCase):
    def test_single_sweep_advances_expired_offers_and_beats(self):
        loc, s = sample("regular", prefix="w-")
        run = engine.food_ready(s["Sam"], table(loc, "4").pk).task
        Task.objects.filter(pk=run.pk).update(offer_expires_at=run.offer_expires_at - timedelta(minutes=5))
        call_command("run_dispatch_worker", "--once")
        self.assertEqual(fresh(run).offered_to, s["Dev"])
        beat = WorkerHeartbeat.objects.get(name=WORKER_NAME)
        self.assertEqual(beat.sweeps, 1)
        self.assertTrue(worker_status()["online"])


class IndependentWorkerProcessTests(TransactionTestCase):
    """Start the real worker as a separate OS process against the test database.
    No browser, no client and no request is involved: the run must still move
    to backup and then escalate to the floor lead."""

    def test_offer_expiration_progresses_with_no_client_connected(self):
        db = connection.settings_dict
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"}
        if connection.vendor == "sqlite":
            db_path = str(db["NAME"])
            if ":memory:" in db_path or "mode=memory" in db_path:
                self.skipTest("needs a file-backed SQLite test DB")
            env["DISPATCH_SQLITE_PATH"] = db_path
        else:  # point the worker at the PostgreSQL *test* database
            env["DATABASE_URL"] = (
                f"postgres://{quote(db['USER'])}:{quote(db['PASSWORD'])}@{db['HOST'] or 'localhost'}:{db['PORT'] or 5432}/{db['NAME']}"
            )
        loc, s = sample("regular", prefix="x-")
        config_ops.update_rules(s["Kim"], offer_timeout=10, backup_timeout=10)
        run = engine.food_ready(s["Sam"], table(loc, "4").pk).task
        # Make the first offer due now instead of sleeping through the timeout.
        Task.objects.filter(pk=run.pk).update(offer_expires_at=timezone.now() - timedelta(seconds=1))
        worker = subprocess.Popen(
            [sys.executable, "manage.py", "run_dispatch_worker", "--interval", "0.2"],
            cwd=settings.BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.worker = worker
        try:
            self._wait(lambda: fresh(run).offered_to_id == s["Dev"].pk, "backup offer")
            Task.objects.filter(pk=run.pk).update(offer_expires_at=timezone.now() - timedelta(seconds=1))
            self._wait(lambda: fresh(run).state == TaskState.ESCALATED, "escalation")
            self.assertEqual(fresh(run).escalated_to_role, "lead")
        finally:
            worker.terminate()
            output = worker.communicate(timeout=10)[0].decode()
        self.assertIn("advanced", output)

    def _wait(self, condition, what, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.2)
        self.worker.terminate()
        self.fail(f"worker process never produced the {what}: {self.worker.communicate(timeout=10)[0].decode()[-2000:]}")
