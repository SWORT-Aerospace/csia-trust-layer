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


def subprocess_db_env(connection):
    """Environment that points a child process at the *test* database."""
    import os
    from urllib.parse import quote

    db = connection.settings_dict
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"}
    if connection.vendor == "sqlite":
        path = str(db["NAME"])
        if ":memory:" in path or "mode=memory" in path:
            return None
        env["DISPATCH_SQLITE_PATH"] = path
        env.pop("DATABASE_URL", None)
    else:
        env["DATABASE_URL"] = (
            f"postgres://{quote(db['USER'])}:{quote(db['PASSWORD'])}@{db['HOST'] or 'localhost'}:{db['PORT'] or 5432}/{db['NAME']}"
        )
    return env
