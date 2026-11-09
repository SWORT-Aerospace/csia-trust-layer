"""Seed the local demo restaurants with sign-in accounts.

Local development only: refuses to create password accounts unless DEBUG is on.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dispatch.models import Restaurant
from dispatch.seeding import FINE_SAMPLE, REGULAR_SAMPLE, build_sample


class Command(BaseCommand):
    help = "Create the sample Regular Service and Fine Dining restaurants with local staff accounts."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and recreate the seeded restaurants.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo creates known-password accounts and only runs with DJANGO_DEBUG=true.")
        password = settings.DISPATCH_DEMO_STAFF_PASSWORD or "service-demo-local"
        seeded = Restaurant.objects.filter(is_demo=True, demo_owner__isnull=True)
        if seeded.exists():
            if not options["reset"]:
                self.stdout.write("Demo restaurants already seeded (use --reset to recreate).")
                self._print(password)
                return
            seeded.delete()
        build_sample("regular", username_prefix="jp-", password=password)
        build_sample("pairing_coordination", username_prefix="mr-", password=password)
        self.stdout.write(self.style.SUCCESS("Seeded Juniper & Pine (Regular Service) and Marrow Room (Fine Dining)."))
        self._print(password)

    def _print(self, password):
        self.stdout.write("Local staff accounts (password for all: %s):" % password)
        for prefix, spec in (("jp-", REGULAR_SAMPLE), ("mr-", FINE_SAMPLE)):
            people = ", ".join(f"{prefix}{key} ({'/'.join(roles)})" for key, _, roles in spec["staff"])
            self.stdout.write(f"  {spec['restaurant']}: {people}")
