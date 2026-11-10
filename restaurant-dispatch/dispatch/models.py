"""Data model. Stores only what dispatch needs: no guest names, payment
details, payroll or employee location tracking."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property

from .permissions import ROLE_CHOICES, ROLE_LABELS
from .profiles import PROFILE_CHOICES, get_profile
from .states import OfferStage, PairingStatus, TableState, TaskKind, TaskState, VisitState


class Restaurant(models.Model):
    """The tenant. Every location, staff member and task hangs off one."""

    name = models.CharField(max_length=120)
    is_demo = models.BooleanField(default=False)
    demo_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    demo_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Location(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=120)
    profile_key = models.CharField("Edition and preset", max_length=40, choices=PROFILE_CHOICES, default="regular")
    offer_timeout_seconds = models.PositiveIntegerField(
        default=45, help_text="How long the first person has to claim an offer."
    )
    backup_timeout_seconds = models.PositiveIntegerField(
        default=45, help_text="How long backup coverage has before it escalates."
    )
    stall_minutes = models.PositiveIntegerField(default=8, help_text="Claimed work older than this is flagged as stalled.")
    time_zone = models.CharField(max_length=64, default=settings.TIME_ZONE)
    # Host-set context for the shift report: are guests waiting for a table?
    waitlist_active = models.BooleanField(default=False)
    waitlist_changed_at = models.DateTimeField(null=True, blank=True)
    # Identifier a future POS adapter must present for this location (shadow mode only).
    pos_ref = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["restaurant__name", "name"]

    def __str__(self) -> str:
        return f"{self.restaurant.name} — {self.name}"

    @property
    def profile(self):
        return get_profile(self.profile_key)

    @property
    def display_name(self) -> str:
        if self.name and self.name != self.restaurant.name:
            return f"{self.restaurant.name} · {self.name}"
        return self.restaurant.name


class StaffMember(models.Model):
    """A person working at one location. A user may hold several memberships
    (two locations, or the personas of a demo sandbox); every screen URL names
    the membership and the server checks it belongs to the signed-in user."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="memberships"
    )
    display_name = models.CharField(max_length=60)
    on_shift = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_demo_account = models.BooleanField(default=False)
    sections = models.ManyToManyField("Section", blank=True, related_name="servers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name

    @cached_property
    def role_set(self) -> set[str]:
        return {grant.role for grant in self.role_grants.all()}

    @property
    def role_labels(self) -> list[str]:
        order = [key for key, _ in ROLE_CHOICES]
        return [ROLE_LABELS[r] for r in sorted(self.role_set, key=order.index)]

    @property
    def roles_display(self) -> str:
        return ", ".join(self.role_labels) or "No role yet"

    def set_roles(self, roles) -> None:
        roles = {r for r in roles if r in ROLE_LABELS}
        self.role_grants.exclude(role__in=roles).delete()
        existing = set(self.role_grants.values_list("role", flat=True))
        StaffRole.objects.bulk_create([StaffRole(staff=self, role=r) for r in roles - existing])
        self.__dict__.pop("role_set", None)


class StaffRole(models.Model):
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="role_grants")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["staff", "role"], name="uniq_staff_role")]


class PairingCode(models.Model):
    """One-time code that signs a staff member's phone or pass tablet in."""

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="pairing_codes")
    code_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class Section(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=40)
    sort = models.PositiveIntegerField(default=0)
    # Backup coverage: who gets offers first, and who gets them next.
    primary_runner = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    backup_runner = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    primary_busser = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    backup_busser = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["sort", "name"]
        constraints = [models.UniqueConstraint(fields=["location", "name"], name="uniq_section_name")]

    def __str__(self) -> str:
        return self.name


class Table(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="tables")
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL, related_name="tables")
    label = models.CharField(max_length=20)
    sort = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=20, choices=TableState.CHOICES, default=TableState.READY)
    current_visit = models.ForeignKey("Visit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    state_changed_at = models.DateTimeField(default=timezone.now)
    version = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort", "label"]
        constraints = [models.UniqueConstraint(fields=["location", "label"], name="uniq_table_label")]

    def __str__(self) -> str:
        return f"Table {self.label}"


class Visit(models.Model):
    """One party's stay at a table. Party size only — no guest names."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="visits")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="visits")
    party_size = models.PositiveSmallIntegerField(default=2)
    state = models.CharField(max_length=20, choices=VisitState.CHOICES, default=VisitState.SEATED)
    next_course = models.PositiveSmallIntegerField(default=1)
    client_token = models.UUIDField(null=True, blank=True)
    seated_at = models.DateTimeField(default=timezone.now)
    seated_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    departed_at = models.DateTimeField(null=True, blank=True)
    departed_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["location", "client_token"], condition=Q(client_token__isnull=False), name="uniq_visit_token"
            )
        ]


class Task(models.Model):
    """One run, course or reset. Shared by both editions."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField(max_length=10, choices=TaskKind.CHOICES)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="tasks")
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="tasks")
    state = models.CharField(max_length=12, choices=TaskState.CHOICES)
    version = models.PositiveIntegerField(default=0)

    item_count = models.PositiveSmallIntegerField(default=1)
    course_number = models.PositiveSmallIntegerField(null=True, blank=True)
    note = models.CharField(max_length=140, blank=True)
    allergy_alert = models.BooleanField(default=False)
    is_practice = models.BooleanField(default=False)
    # Resets only: were guests waiting for a table when the party left?
    # Null = not recorded (tasks created before the host toggle existed).
    waitlist_active = models.BooleanField(null=True, blank=True)

    offered_to = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    offer_stage = models.CharField(max_length=10, choices=OfferStage.CHOICES, blank=True, default="")
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    offered_history = models.JSONField(default=list, blank=True)  # staff ids already offered
    owner = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_tasks")
    assigned_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    escalated_to_role = models.CharField(max_length=20, blank=True)

    pairing_status = models.CharField(
        max_length=12, choices=PairingStatus.CHOICES, default=PairingStatus.NOT_REQUIRED
    )
    pairing_resolved_by = models.ForeignKey(
        StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    pairing_resolved_at = models.DateTimeField(null=True, blank=True)
    team_ready_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    team_ready_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    client_token = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completed_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cancel_reason = models.CharField(max_length=140, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    ready_at = models.DateTimeField(null=True, blank=True)
    staged_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    offered_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["location", "state"]),
            models.Index(fields=["state", "offer_expires_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "client_token"], condition=Q(client_token__isnull=False), name="uniq_task_token"
            ),
            # A visit gets at most one live reset, however many times "Party has left" is tapped.
            models.UniqueConstraint(
                fields=["visit"], condition=Q(kind="reset") & ~Q(state="cancelled"), name="one_reset_per_visit"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} #{self.pk} — {self.title}"

    @property
    def title(self) -> str:
        if self.kind == TaskKind.COURSE:
            return f"Table {self.table.label} · Course {self.course_number}"
        if self.kind == TaskKind.RESET:
            return f"Reset table {self.table.label}"
        plates = "plate" if self.item_count == 1 else "plates"
        return f"Table {self.table.label} · {self.item_count} {plates}"

    @property
    def is_open(self) -> bool:
        return self.state in TaskState.OPEN

    def seconds_left(self, now=None) -> int | None:
        if self.state != TaskState.OFFERED or not self.offer_expires_at:
            return None
        now = now or timezone.now()
        return max(0, int((self.offer_expires_at - now).total_seconds()))


class AuditEvent(models.Model):
    """Timestamped activity log. Append-only from the application's point of view."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="audit_events")
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_name = models.CharField(max_length=60, blank=True)  # snapshot; "Timer" for the worker
    verb = models.CharField(max_length=40, db_index=True)
    summary = models.CharField(max_length=240)
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    table = models.ForeignKey(Table, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-at", "-id"]


class SetupSession(models.Model):
    """Instrumentation for the browser setup wizard (design target: under 10 minutes)."""

    STEPS = ["location", "edition", "tables", "staff", "pair", "practice"]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.CASCADE, related_name="setups")
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    steps = models.JSONField(default=dict, blank=True)  # step -> ISO timestamp completed
    practice = models.JSONField(default=dict, blank=True)  # ids of the practice table/run/reset

    @property
    def duration_seconds(self) -> int | None:
        if not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds())

    def mark(self, step: str) -> None:
        self.steps[step] = timezone.now().isoformat()
        self.save(update_fields=["steps"])


class IntegrationEvent(models.Model):
    """An event received from a POS adapter. Shadow mode only in this release:
    recorded with what *would* have happened; never changes floor state."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="integration_events")
    provider = models.CharField(max_length=30)
    mode = models.CharField(max_length=10, default="shadow")
    kind = models.CharField(max_length=30)
    external_ref = models.CharField(max_length=80, blank=True)
    external_event_id = models.CharField(max_length=120, blank=True)
    table_label = models.CharField(max_length=20, blank=True)
    course_number = models.PositiveSmallIntegerField(null=True, blank=True)
    identity_check = models.CharField(max_length=40, blank=True)  # "match" or why it failed
    received_at = models.DateTimeField(default=timezone.now)
    would_do = models.CharField(max_length=200)
    applied = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # A vendor retrying the same event is recorded once.
            models.UniqueConstraint(
                fields=["location", "provider", "external_event_id"],
                condition=~Q(external_event_id=""),
                name="uniq_integration_event",
            )
        ]


class WorkerHeartbeat(models.Model):
    name = models.CharField(max_length=40, unique=True)
    beat_at = models.DateTimeField()
    pid = models.PositiveIntegerField(default=0)
    sweeps = models.PositiveBigIntegerField(default=0)
    actions = models.PositiveBigIntegerField(default=0)


class ShiftObservation(models.Model):
    """A manually recorded pilot observation (baseline or Syncora shift).

    Deliberately separate from Syncora's event data: these numbers come from a
    person with a stopwatch, the POS or the venue's own tools, and the report
    never mixes them into event-derived metrics."""

    BASELINE = "baseline"
    SYNCORA = "syncora"
    SOURCES = [(BASELINE, "Baseline shift (without Syncora)"), (SYNCORA, "Syncora shift")]
    WAITLIST = [("none", "No wait"), ("some", "Some waiting"), ("heavy", "Heavy wait")]

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="observations")
    source = models.CharField(max_length=10, choices=SOURCES)
    service_date = models.DateField()
    shift_label = models.CharField(max_length=40)
    start_time = models.TimeField()
    end_time = models.TimeField()
    covers = models.PositiveIntegerField(help_text="From the POS or host stand, not from Syncora.")
    waitlist = models.CharField(max_length=10, choices=WAITLIST, default="none")
    waitlist_peak_parties = models.PositiveIntegerField(default=0)
    staff_runners = models.PositiveSmallIntegerField(default=0)
    staff_bussers = models.PositiveSmallIntegerField(default=0)
    staff_servers = models.PositiveSmallIntegerField(default=0)
    staff_hosts = models.PositiveSmallIntegerField(default=0)
    staff_managers = models.PositiveSmallIntegerField(default=0)
    order_errors = models.PositiveIntegerField(default=0, help_text="Wrong or missing items reaching a table.")
    guest_complaints = models.PositiveIntegerField(default=0)
    manager_interventions = models.PositiveIntegerField(
        null=True, blank=True, help_text="Baseline only: tallied by the observer."
    )
    food_handoff_p90_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Baseline only: measured manually.")
    food_handoff_samples = models.PositiveIntegerField(null=True, blank=True)
    reset_p90_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Baseline only: measured manually.")
    reset_samples = models.PositiveIntegerField(null=True, blank=True)
    method = models.CharField(max_length=200, blank=True, help_text="Native tools and how times were taken.")
    notes = models.TextField(blank=True, max_length=2000)
    recorded_by = models.ForeignKey(StaffMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]

    @property
    def staffing_total(self) -> int:
        return self.staff_runners + self.staff_bussers + self.staff_servers + self.staff_hosts + self.staff_managers
