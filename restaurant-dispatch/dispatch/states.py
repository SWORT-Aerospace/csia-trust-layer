"""Explicit states for tasks, tables and visits.

A *table* is the physical furniture; a *visit* is one party's stay at it; a
*task* is one specific run, course or reset. Keeping the three separate is what
lets the engine refuse a late reset from a previous visit.
"""


class TaskKind:
    RUN = "run"  # Regular Service: plates from expo to a table
    COURSE = "course"  # Fine Dining: a course held at the pass until released
    RESET = "reset"  # A busser resetting a table after the party physically left

    CHOICES = [(RUN, "Food run"), (COURSE, "Course"), (RESET, "Table reset")]


class TaskState:
    STAGED = "staged"  # Fine Dining only: held at the pass, invisible to runners
    OFFERED = "offered"  # offered to exactly one person, with an expiry
    ESCALATED = "escalated"  # nobody claimed it: with the floor lead / returned to captain
    CLAIMED = "claimed"  # one owner, until completed, released or reassigned
    COMPLETED = "completed"  # physically done (delivered / table reset)
    CANCELLED = "cancelled"

    CHOICES = [
        (STAGED, "Held at pass"),
        (OFFERED, "Offered"),
        (ESCALATED, "Needs an owner"),
        (CLAIMED, "Claimed"),
        (COMPLETED, "Done"),
        (CANCELLED, "Cancelled"),
    ]
    OPEN = (STAGED, OFFERED, ESCALATED, CLAIMED)
    UNCLAIMED = (STAGED, OFFERED, ESCALATED)
    CLOSED = (COMPLETED, CANCELLED)


class OfferStage:
    NONE = ""
    PRIMARY = "primary"  # section runner/busser (or least-busy eligible)
    BACKUP = "backup"  # configured backup coverage (or next eligible)
    ASSIGNED = "assigned"  # chosen by the captain/lead on release or reassignment

    CHOICES = [(NONE, "—"), (PRIMARY, "Primary"), (BACKUP, "Backup"), (ASSIGNED, "Assigned")]


class PairingStatus:
    NOT_REQUIRED = "not_required"  # preset has no pairing check
    PENDING = "pending"  # waiting for the sommelier (or captain's "no pairing")
    READY = "ready"  # sommelier confirmed
    NOT_NEEDED = "not_needed"  # captain marked: this course needs no pairing

    CHOICES = [
        (NOT_REQUIRED, "Not part of this preset"),
        (PENDING, "Waiting for sommelier"),
        (READY, "Pairing ready"),
        (NOT_NEEDED, "No pairing for this course"),
    ]
    RESOLVED = (NOT_REQUIRED, READY, NOT_NEEDED)


class TableState:
    READY = "ready"  # ready to seat
    OCCUPIED = "occupied"  # a visit is seated
    NEEDS_RESET = "needs_reset"  # party physically left; reset not yet claimed
    RESETTING = "resetting"  # a busser owns the reset

    CHOICES = [
        (READY, "Ready to seat"),
        (OCCUPIED, "Seated"),
        (NEEDS_RESET, "Needs reset"),
        (RESETTING, "Being reset"),
    ]


class VisitState:
    SEATED = "seated"
    DEPARTED = "departed"  # guests physically left (never inferred from payment)
    CLOSED = "closed"  # table reset confirmed, or table reseated by an authorized override

    CHOICES = [(SEATED, "Seated"), (DEPARTED, "Departed"), (CLOSED, "Closed")]
