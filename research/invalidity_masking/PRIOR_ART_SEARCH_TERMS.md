# Prior-art search terms

**No literature search was performed in this environment.** This file is the
search plan and an honest statement of what the phenomenon most likely already
has a name for. Novelty is recorded as `NOT_ESTABLISHED` in `CLAIM_LEDGER.json`
and nothing in this work package should be read as a novelty claim.

## What would have to be shown to claim novelty

Three separable things, and only the third is a plausible candidate:

1. **The phenomenon** — that intermittent faults can hide from a fault
   detector. Certainly old. Do not claim.
2. **The mechanism family** — that last-value retention plus a staleness
   watchdog can mask intermittency. Very likely old, under several names in
   several communities. Do not claim without a search.
3. **The specific composition** — that an adapter which *correctly* discards an
   invalid observation (and correctly records *why*) can destroy the very
   distinction it preserved, because the interface to the consumer has only
   two states where the producer has three, and the consumer's timeout is
   measured from *accepted* samples rather than from *observations*. This is
   the part worth searching for. It is an interface-arity argument, not a
   filtering argument.

## Terms, grouped by community

### Fault detection and diagnosis
- intermittent fault detection observability
- intermittent fault masking fault detection isolation
- fault detectability intermittent versus permanent faults
- residual generator intermittent fault duty cycle
- missed detection intermittent sensor fault threshold
- fault signature aliasing sampling rate

### Real-time systems and sensor fusion middleware
- last known good value sensor fusion staleness
- sample validity flag propagation middleware
- stale data detection watchdog timeout sensor
- data freshness semantics real-time database
- zero-order hold sensor dropout state estimation
- sensor sample age deadline miss detection

### Avionics, autopilot, integrity monitoring
- GNSS fix type validity flag consumer semantics
- receiver autonomous integrity monitoring intermittent loss of lock
- GPS fix loss detection latency autopilot EKF
- MAVLink GPS_RAW_INT fix_type consumer handling
- signal validity BIT built-in test intermittent

### Type systems and API design
- three-valued sensor reading absent invalid missing
- option type loses failure reason
- error swallowed as absence API design
- distinguishing missing data from invalid data semantics
- null versus not-applicable versus unknown SQL three-valued logic

### Security-adjacent framing (only if an adversary model is ever built)
- intermittent jamming detection evasion duty cycle
- pulsed jamming GNSS receiver reacquisition
- on-off attack trust management reputation systems

> The last one is worth flagging: **on-off attacks against trust and reputation
> systems** are a well-established topic, and the arrangement-versus-density
> result (H2) is structurally similar to it. If a search is ever run, start
> there — it is the most likely place for this to already exist under a
> different name. This work package constructs no adversary model and makes no
> attack claim; the resemblance is noted so that it is not later mistaken for
> novelty.

## Nearest things in this repository

Not prior art, but the closest existing statements of the same distinction:

- `csia/aircraft/sample.py:52-61` — `MissingReason` exists precisely to keep
  "absent" from collapsing into one undifferentiated state. Its docstring is
  *"Never collapse these to None."*
- `csia/aircraft/adapters/base.py:151-171` — `_reject_sentinel`'s docstring
  records an earlier round of exactly this error, one layer up: a sentinel that
  was counted but not *delivered* reached the flight log as `NOT_RECEIVED`,
  "byte for byte identical to a message that never came".
- `csia/runtime/online.py:43-46` — the staleness watchdog's own comment says a
  sensor that stops producing "is as failed as one that produces bad ones".
  The finding here is the converse case, which that comment does not cover: a
  sensor that keeps producing, mostly badly.
