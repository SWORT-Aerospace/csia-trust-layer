# Tooling feasibility, physical validation, and a CI shape

Items 16, 27 and 28. What the prototype costs, what it would take to trust it
against hardware, and what it would look like in CI. **Nothing here is
productionised and item 32 forbids it.**

---

## 1. What the prototype is (item 16)

```
input    an ingest path      (a Python callable driving real committed code)
         a canonical contract (JSON, validated against the schema)
         a bounded alphabet  (3 symbols per family, words of length 1..4)

output   PASS, or
         the violated clause
         the shortest counterexample
         the first transformation that destroys the distinction
         the downstream equivalence level at which the loss becomes invisible
         the consequence class
```

Deliberately not over-engineered (item 16 says so). It is ~500 lines of
checker plus ~500 lines of probe, no solver, no symbolic execution, no
instrumentation of the code under test beyond reading two private
dictionaries on the adapter.

### Cost, measured

| step | runtime |
|---|---|
| full cross-path check, 3 families × 3 paths × 120 words | **191 s** |
| self-audit, 4 injected defects | ~35 s |
| cross-sensor source audit (10 channels, regex-pinned) | < 1 s |
| PX4 probe including a 9.6 MB ULog read | ~30 s |
| prior-result reproduction (item 12 hard stop) | ~90 s |

One run of a single word through the v1.1 adapter path: **0.21 s**; through
`plugins.py` or `ulog_source.py`: **0.06 s**. The cost is dominated by
running the real frozen core at 25 Hz over a 15 s window, not by the search.

### Scaling

The alphabet is 3 symbols and the search is exhaustive, so words grow as
`3^n`: 120 words to length 4, 363 to length 5, 1092 to length 6. At 0.33 s per
word per path per family, length 5 costs roughly 10 minutes and length 6
roughly 30. **This is the honest ceiling of the approach as built.** Every
counterexample found in this package has length ≤ 3, so the bound was never
binding — but a defect needing a length-8 witness would not be found this way,
and no claim is made that one does not exist.

Cheaper alternatives exist and are standard: symbolic execution of the ingest
branch, or lifting each path to an FSA and comparing symbolically as `ParDiff`
does. Neither was built, because the point of this stage was feasibility, not
performance.

### What makes it work at all

The three paths are **short**. A MAVLink message reaches the frozen core
through at most five transformations, all in three files. A checker of this
shape would not survive a pipeline with dynamic dispatch, threads, or state
shared across channels.

## 2. Self-validation (item 17)

`TOOL_SELF_AUDIT.json`. Four deliberately faulty NON-SCORED fixtures injected
into the **probe** — the instrument, not CSIA:

| fixture | detected | predicted quantity moved |
|---|---|---|
| D1 one-message phase shift | yes | **no — prediction refuted, kept** |
| D2 wrong freshness event | yes | yes |
| D3 sentinel converted to stale | yes | yes |
| D4 invalid converted to no-observation | yes | yes |

All four detected; instrument restored exactly afterwards
(`instrument_restored_exactly: true`).

Two disciplines are enforced mechanically, both learned from real mistakes in
the previous package:

* `assert C.P is P` and `assert sys.modules["probe"] is P` — the Stage 2
  self-audit once passed because it patched a different module object than the
  checker used.
* Detection is defined in advance as "at least one published quantity moves",
  and the *prediction* of which quantity is scored separately. **D1's
  prediction was wrong and was not re-aimed.** The measured `A`-close delay
  does not move under a one-period shift, because on that path the no-fix
  report does not affect admissibility at all — which is an independent
  confirmation of the GNSS-F1 collapse arriving from an unexpected direction.

## 3. Physical validation plan (item 27)

**No physical HIL was executed. No hardware is connected.** `pyserial`
enumerates only `/dev/ttyS0` on this machine, which is a console, not a flight
controller. Item 27 forbids executing physical HIL without hardware and it was
not executed. Nothing in this package is presented as a hardware result.

What would make the software counterexamples trustworthy on real interfaces:

### Criterion 0 — do the raw conditions occur on hardware at all?

Before any preservation claim, confirm the source states exist on a physical
link:

| state | how to produce it physically | what to record |
|---|---|---|
| GNSS `I` | disconnect the GNSS antenna, or shield it, on a real receiver feeding a real flight controller | `fix_type` histogram over the disconnection window, from a raw MAVLink capture |
| GNSS `N` | pull the telemetry link (unplug the radio), leaving the vehicle powered | inter-message gap distribution; confirm no `GPS_RAW_INT` arrives |
| battery `X` | a BMS or power module that does not measure current, or a protocol emulator injecting `current_battery = -1` | `current_battery` histogram |
| mag `Z` | a flight controller with no external compass and the internal one disabled | `xmag/ymag/zmag` triples over the window |

`I` and `N` must be produced by **physically different** causes — an antenna
fault and a link fault — because the whole question is whether the pipeline
can tell them apart. Producing both by a parameter change would beg it.

### Criterion 1 — does the predicted collapse appear?

Capture the raw MAVLink stream and the CSIA flight log simultaneously, then
check the specific predictions this package makes:

1. On the v1.1 adapter, a real antenna disconnection and a real link loss
   produce **identical** `fresh["gps"]` trajectories and **identical**
   failsafe reason strings ("GPS data invalid").
2. `A` closes at the previous fix's age-out, not at the no-fix report — so
   the measured delay from the first `fix_type < 3` message to
   `fresh["gps"] == False` is drawn from the message-interval distribution,
   not concentrated at zero.
3. On a power module reporting `current_battery = -1`, the CSIA log shows
   `battery.current` usable for up to 0.5 s after the first sentinel, with a
   `sentinel_counts` entry for the same channel and window.

Prediction 3 is the sharpest: it is falsifiable from a single log and does not
need a matched pair.

### Hardware needed

A flight controller (Pixhawk-class) running ArduCopter 4.8, a real GNSS
receiver with a detachable antenna, a telemetry radio pair, and a power module
whose current sense can be disabled or emulated. A CAN/serial protocol
emulator would substitute for the last item and is the cheaper route.

### What SITL can and cannot substitute

ArduPilot SITL is installed here and the previous package used it to answer
criterion 0 for `SIM_GPS1_ENABLE=0` versus a stopped `MAV_DATA_STREAM`. That
is a **simulator** answer and was labelled as one. It cannot answer criterion
0 for the battery sentinel, because SITL's power model always reports a
current — which is exactly why the PX4 `platform_qualification` override
exists.

## 4. CI shape (item 28)

Designed, **not productionised**. The trigger is a change to any file listed
in a contract's `stage_sites`.

```
adapter / decoder / bridge change
        │
        ▼
extract the alphabet from the contract's accepted_input_states
        │
        ▼
run the bounded checker against every path the contract names
        │
        ├── PASS  → merge
        └── FAIL  → block, with the shortest counterexample
```

Output shape, filled in from a real result in this package:

```
EVIDENCE SEMANTICS CHECK: FAIL   (gnss.mavlink.gps_raw_int.v0)

clause             GNSS-F1  I must remain distinguishable from N
source state       OBSERVED_INVALID   (GPS_RAW_INT.fix_type < 3)
expected downstream a state distinguishable from NOT_OBSERVED
actual             no emission -- identical to no message ever arriving
first collapse     T5_core_bridge
                   csia/aircraft/adapters/base.py:306-337 (to_core_samples)
shortest witness   'I'   (1 message; exhaustive over 120 words, lengths 1-4)
downstream         first equivalent level VALUE; consequence NONE
needed by          failsafe.py:145-152 records the reason "GPS data invalid"
                   for both inputs
```

### What would have to be true first

1. **The contracts must be maintained by the people who own the adapters.**
   Three JSON files exist here; a real deployment has dozens of channels.
   `docs/simulation/CHANNEL_SEMANTICS.yaml` already carries a
   `missing_semantics` sentence per channel — the realistic path is to make
   *that* field machine-readable rather than to introduce a second contract
   format. That is the honest engineering recommendation and it makes this
   package's schema an intermediate artifact, not a deliverable.
2. **The runtime budget must fit.** 191 s for three families is fine for a
   nightly job and marginal for a pre-merge hook. Restricting to the families
   whose `stage_sites` a diff touches would bring a typical run under 60 s.
3. **Flakiness must be zero.** The checker is deterministic — no randomness,
   no wall-clock dependence, fixed tick grid — and re-running it produces
   byte-identical artifacts. That was verified by re-running after every
   change in this session.

### What it would NOT catch

* Anything needing a witness longer than the bound.
* Anything involving two channels interacting, since each contract is
  single-family.
* Anything about numeric correctness. The checker is deliberately blind to
  whether 5.00 A is the right current; it only asks whether the pipeline can
  still tell you where the number came from.
* A missing `accepted_input_state`. If nobody writes down that
  `current_battery == -1` means something, the checker has nothing to check.
  **This is the binding limitation:** the tool's value is bounded above by the
  quality of a hand-written declaration, and the declaration is the hard part.
