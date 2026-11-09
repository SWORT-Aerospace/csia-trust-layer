from django.core.management.base import BaseCommand

from dispatch.seeding import cleanup_expired_demos


class Command(BaseCommand):
    help = "Delete demo sandboxes past their expiry (the worker also does this every 5 minutes)."

    def handle(self, *args, **options):
        self.stdout.write(f"Removed {cleanup_expired_demos()} expired demo sandbox(es).")
