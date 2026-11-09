"""The timer worker: advances expired offers independently of any browser.

Run it next to the web server:  python manage.py run_dispatch_worker
"""

import os
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from dispatch.engine import expire_due_offers
from dispatch.models import WorkerHeartbeat
from dispatch.seeding import cleanup_expired_demos
from dispatch.selectors import WORKER_NAME


class Command(BaseCommand):
    help = "Advance expired offers (backup coverage, escalation) on a fixed tick."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=1.0, help="Seconds between sweeps (default 1).")
        parser.add_argument("--once", action="store_true", help="Run a single sweep and exit.")

    def handle(self, *args, **options):
        self._stop = False
        signal.signal(signal.SIGTERM, self._request_stop)
        signal.signal(signal.SIGINT, self._request_stop)
        interval = max(0.2, options["interval"])
        if not options["once"]:
            self.stdout.write(f"Dispatch timer worker running (pid {os.getpid()}, every {interval:g}s). Ctrl+C to stop.")
        last_cleanup = 0.0
        while True:
            advanced = expire_due_offers()
            if time.monotonic() - last_cleanup > 300:
                removed = cleanup_expired_demos()
                last_cleanup = time.monotonic()
                if removed:
                    self.stdout.write(f"Removed {removed} expired demo sandbox(es).")
            beat, _ = WorkerHeartbeat.objects.get_or_create(name=WORKER_NAME, defaults={"beat_at": timezone.now()})
            WorkerHeartbeat.objects.filter(pk=beat.pk).update(
                beat_at=timezone.now(), pid=os.getpid(), sweeps=beat.sweeps + 1, actions=beat.actions + advanced
            )
            if advanced:
                self.stdout.write(f"{timezone.localtime():%H:%M:%S} advanced {advanced} offer(s)")
            if options["once"] or self._stop:
                return
            time.sleep(interval)
            close_old_connections()  # recover from DB restarts between sweeps

    def _request_stop(self, *_):
        self._stop = True
