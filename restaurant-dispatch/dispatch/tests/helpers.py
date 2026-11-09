from datetime import timedelta

from django.utils import timezone

from dispatch.models import Location
from dispatch.seeding import build_sample


def sample(profile_key="regular", prefix="a-"):
    """A complete sample location; returns (location, {name: StaffMember})."""
    location, staff = build_sample(profile_key, username_prefix=prefix, password=None)
    by_name = {m.display_name: m for m in staff.values()}
    return Location.objects.get(pk=location.pk), by_name


def table(location, label):
    return location.tables.get(label=label)


def later(seconds):
    return timezone.now() + timedelta(seconds=seconds)


def fresh(obj):
    obj.refresh_from_db()
    return obj
