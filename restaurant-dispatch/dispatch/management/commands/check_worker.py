"""Exit non-zero if the timer worker has stopped beating (for cron, platform
health checks or uptime monitors that can run a command)."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dispatch.models import WorkerHeartbeat
from dispatch.selectors import WORKER_NAME


class Command(BaseCommand):
    help = "Report the timer worker's heartbeat; exit 1 when it is older than --max-age seconds."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=int, default=30, help="Seconds before the worker counts as stalled (default 30).")

    def handle(self, *args, **options):
        beat = WorkerHeartbeat.objects.filter(name=WORKER_NAME).first()
        if beat is None:
            raise CommandError("STALLED: the timer worker has never reported a heartbeat.")
        age = int((timezone.now() - beat.beat_at).total_seconds())
        if age > options["max_age"]:
            raise CommandError(f"STALLED: last heartbeat {age}s ago (limit {options['max_age']}s).")
        self.stdout.write(f"ok: last heartbeat {age}s ago, {beat.sweeps} sweeps")
