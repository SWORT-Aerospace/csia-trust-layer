# CSIA v1.1 — ENGINEERING REVIEW REPORT

**Phase 1 of 6 complete.** Canonical ingestion + known defect fixes.
Engineering, not research: FIXED / HARDENED / VALIDATED / SIMPLIFIED /
IMPROVED (item 48).

The 30 items item 51 requires, in order. Items belonging to phases that have
not run say so rather than being padded.

---

### 1. EXACT BASELINE SHA

Frozen v1 diagnostic-core tag `csia-v1.0-research-final` =
**`ec5acd189295dab9259d4989657d42184d6142a3`**.
v1.1 starting commit **`1ba69a5`**, tree clean, 971 tests passing.
ArduPilot `01a504b`; PX4 working tree at `/home/user/px4`.

### 2. EXACT v1.1 SHA

The Phase 1 commit on `claude/code-reviewer-repo-export-zicovg`; the
`csia-v1.1-engineering` branch exists locally and points at the same work. It
has not been pushed — the session is pinned to the other branch and pushing a
second one was not explicitly authorised.

### 3. PRODUCTION FILES CHANGED

Four, 77 insertions, 5 deletions, none in `FROZEN_PATHS`:

| file | change |
|---|---|
| `csia/aircraft/adapters/base.py` | `_reject_sentinel` clears `_latest` |
| `csia/aircraft/adapters/ardupilot.py` | all-zero magnetometer `else` branch |
| `csia/runtime/ulog_source.py` | battery `current_a == -1` no longer valid |
| `csia/runtime/plugins.py` | `max(current_battery, 0)` clamp removed |

Plus one interface change: the `battery` dict gains `current_valid`, and
`current` may be `None`.

### 4. FROZEN v1 UNTOUCHED?

**Yes.** `git diff --stat csia-v1.0-research-final -- <FROZEN_PATHS>` is
empty. `tests/test_v1_frozen.py` passes, and
`tests/test_v1_1_canonical_ingest.py::test_the_frozen_core_was_not_touched_by_phase_one`
restates the check so a Phase 1 regression names Phase 1.

Phase 1 needed no core change. Fixing what reaches the bridge did not require
touching what is on the other side of it.

### 5. INGEST DEFECTS REPRODUCED BEFORE FIX

**Four, plus one control**, by `engineering/v1_1/reproduce_defects.py --out pre`
run against unmodified v1 ingestion.

    sha256(cases) = 7fdd3d65e1b9c7633255989ec16f10c58e288bae2d024825e1e53fbd57d59d9d

| | raw condition | v1 observed |
|---|---|---|
| **D1** | `current_battery = -1`, 20 ms after 5.00 A | **`5.0 A`, present, INFORMATIVE** — sentinel counted, then ignored |
| **D2** | all-zero magnetometer triple | **previous field present** — sentinel not even counted |
| **D3** | ULog `current_a == -1.0` | **`current: -1.0, valid: true`** |
| **D4** | plugins `current_battery = -1` | **`current: 0.0, valid: true`** |
| **D5** | GNSS `fix_type < 3` *(control)* | absent, `NO_3D_FIX` — already correct |

D2 is the worst-behaved: v1 recognised the sentinel and left no trace at all,
not even a counter. D1 at least incremented one.

### 6. INGEST DEFECTS FIXED

**All four. Control unchanged.** Same script, `--out post`:

    sha256(cases) = 7fff288ac57f3d91e865ea59e1dfb8bb324628a3b7a918ac96019f1ad830687a

D1 and D2 → absent with `SENTINEL`. D3 and D4 → `current: null`,
`current_valid: false`, `valid: false`. D5 byte-identical.

**Three decoders gave three answers to one raw condition — 5.00 A, 0.00 A,
−1.00 A. They now agree.** That is item 6's criterion, met for this condition.

The root cause was a single asymmetry. `_put` cleared `_sentinel_at`, so a
value superseded an earlier sentinel; `_reject_sentinel` did not clear
`_latest`, so a sentinel never superseded an earlier value. Because
`_channel_value` consults `_latest` first, the producer's disavowal was
recorded and then discarded, and the channel eventually died as **STALE** —
blaming the link for what the producer had said about itself. The GNSS path
had already worked around this locally by popping `_latest` itself, which is
why one channel behaved correctly while the others did not. That workaround is
now the general rule, applied in one place.

### 7. CANONICAL STATE MODEL

`CANONICAL_INGEST_SPEC.md`. Item 3's required states map onto the existing
`ChannelValue`:

`OBSERVED_VALID` = value + admissible quality · `OBSERVED_INVALID` /
`SENTINEL` = `missing = SENTINEL` · `NOT_OBSERVED` = `NOT_RECEIVED` ·
`STALE` = `STALE` · GNSS keeps its own `NO_3D_FIX`, deliberately not folded
into `SENTINEL`.

`RETAINED` is **not modelled**. In v1 it existed by accident rather than
design, and v1.1 removes it rather than naming it.

Five rules: **R1** supersession, both directions · **R2** reason fidelity, a
disowned value reports `SENTINEL` not `STALE` · **R3** no fabrication — never
clamp, pass through or default a sentinel into a number · **R4** independent
constituents, voltage survives an unmeasured current · **R5** sentinels age
like values.

**No new type was added, on purpose.** Item 3 warns twice against ontology
inflation. `ChannelValue` already carries value, unit, frame, quality,
`missing`, `t_source`, `age_s`, `note`, and already enforces that exactly one
of value/missing is set. `usable` and `fresh` exist or are derivable;
duplicating them as booleans would let the copies disagree. The genuinely
absent fields are `provenance` / `producer` / `transport`, which belong to
Phase 9 and have no consumer yet. **The gap was a rule, not a field.**

### 8. SUPPORT-STATE IMPLEMENTATION

**NOT REACHED.** Phase 2. No support state, no `EVIDENCE_BACKED` /
`NON_IDENTIFIABLE` / `PRIOR_DOMINATED`, no discriminating-evidence count.
Nothing was stubbed.

### 9. KNOWN FIX-LOSS RESULT BEFORE/AFTER

**NOT MEASURED.** Phase 2 (Gate D). The GNSS no-fix *ingest* path is verified
as a control (D5, unchanged), but the diagnostic question — does the system
report loss of discriminating support honestly when the fix goes — is a
Phase 2 measurement and has not been made.

### 10. AMBIGUITY / UNKNOWN IMPLEMENTATION

**NOT REACHED.** Phase 2.

### 11. GRAPH ARM

**NOT REACHED.** Phase 3.

### 12. FLAT ARM

**NOT REACHED.** Phase 3. No flat baseline exists yet, so item 47's decision
rule — if FLAT ≈ GRAPH, remove the graph — cannot be applied and is not
pre-judged here.

### 13. GRAPH-VS-FLAT RESULT

**NOT MEASURED.** Phase 3.

### 14. TRUST-ONLY RESULT

**NOT MEASURED.** Phase 3.

### 15. SEQUENTIAL-ONLY RESULT

**NOT MEASURED.** Phase 3.

### 16. COMBINED RESULT

**NOT MEASURED.** Phase 3.

### 17. CLEAN CONTROLS

Phase 1 carries one: **D5**, the GNSS no-fix case, which was already correct
in v1 and had to stay byte-identical through the fixes. It did. Its role is to
catch a v1.1 edit that breaks a path that already worked, and it is asserted
both in the JSON comparison and as a standalone test.

The clean-flight exposure programme item 35 asks for is Phase 6 and has not
started. **No false-alarm rate is claimed**, because healthy exposure has not
been verified.

### 18. FUNCTION ELIGIBILITY OUTPUTS

**NOT REACHED.** Phase 4.

### 19. ASSURANCE LEDGER EXAMPLE

**NOT REACHED.** Phase 4.

### 20. API VERSION

**NOT REACHED** as a versioned schema — `csia_output_v1_1.schema.json` does
not exist (Phase 4). But Phase 1 **did** change an interface, and item 27's
"no silent schema drift" applies now:

> The `battery` channel dict from both decode paths gains `current_valid`, and
> `current` may be `None`.

That is not silent — it is in the manifest, the changelog and here — but it is
also not versioned, because the version mechanism is Phase 4 work. Consumers
outside this repository that read `battery["current"]` unconditionally will
break. The two inside it were updated and are listed in the manifest §6.

### 21. PYTHON/C EQUIVALENCE STATUS

**NOT REACHED.** Phase 5. No C port exists. No claim is made about embedded
behaviour.

### 22. COMPUTE

**NOT MEASURED** for v1.1. Phase 1 removes no work from the hot path and adds
one dict `pop` per sentinel, which is not worth a benchmark claim. The v1
timing figures stay labelled v1.

### 23. MEMORY

**NOT MEASURED** for v1.1. Same reasoning.

### 24. PROVENANCE LOGGING

**NOT REACHED.** Phase 9. Deliberately so — and there is a live constraint on
it: the Stage 0A research package (`research/effective_evidence_independence/`)
found that ArduPilot's `VIBRATION` message follows a **runtime-selected**
accelerometer instance with no field on the wire identifying it. That is a
provenance fact Phase 9 should log. Item 33 of the Stage 0A brief forbids
computing a production κ from it or gating any decision on it, and Phase 1
does neither.

### 25. VALIDATION DATA AVAILABLE

Unchanged by Phase 1: the real 9.6 MB PX4 ULog (345 GNSS samples, 216 battery
samples, **all `current_a == -1.0`** — which is why D3 matters), the existing
MAVLink captures, SITL, deterministic replay. The tiered validation programme
(item 34) is Phase 6 and has not started.

### 26. HIL EXECUTED?

**No.** No hardware is present in this environment. No HIL claim is made.

### 27. PHYSICAL SENSORS TESTED?

**No.**

### 28. SHADOW FLIGHT EXECUTED?

**No.** And item 44's deferral holds: no autonomous RTL, land, motor inhibit,
mode switch or control override exists or was written. CSIA remains advisory.

### 29. REMAINING BLOCKERS

1. **Research campaigns need remeasurement for v1.1.** The battery three-way
   split, the mag `T3_ingest` collapse, and the authority-conflict battery rows
   describe ingestion that no longer exists. The v1 numbers stay labelled v1
   and were not edited; the v1.1 numbers do not exist yet. Listed in the
   manifest §5.
2. **Item 6's five-path equivalence matrix is not built.** Four defect cases on
   three paths were covered.
3. **`MaxAge["gnss.position"] = 1.00 s` vs core `STALE_TIMEOUT_S["gps"] =
   0.5 s`.** Two layers disagree about when a fix goes stale. Banked, not
   fixed: it is not an ingest sentinel defect and changing a freshness limit
   moves admissibility for every downstream result.
4. **Phases 2–6 not started**, so Gates D–I are unreached.
5. **`current_valid` is an unversioned interface change** (§20).

### 30. EXACT PRODUCT MATURITY

**Research-grade runtime with one hardened layer. Not deployable.**

What is now true that was not: the ingest layer no longer fabricates
measurements. A producer that declines to measure is reported as having
declined, on all three decode paths, with the right reason, and the frozen
core sees the sensor as unavailable rather than being handed a number the
vehicle never sent.

What is still true: there is no support state, no ambiguity handling, no
function eligibility, no assurance ledger, no versioned output schema, no C
port, no benchmark, no HIL, no shadow flight, and no verified clean-flight
exposure. Five of the eleven work packages have not begun.

**Maturity: one of six phases.** The honest description is "the ingestion
layer tells the truth now", not "v1.1 is ready".

---

## Two things worth flagging to a reviewer

**The tests that had to change.** Two tests asserted the pre-fix behaviour —
one calling the divergence between decode paths "a deliberate improvement",
one reproducing the D1 defect to prove the research finding was real. Fixing
the defects broke both. Neither was deleted: the first now asserts the
agreement, the second became a regression test, and the pre-fix evidence lives
with its hash in `KNOWN_DEFECTS_PRE_FIX.json`. Both renames are in the
manifest §6.

**The citation verifiers.** Four research citations that were correct about
the code they were taken from stopped resolving, because the fixes moved lines
and removed the retained-value behaviour entirely. The claims did not become
wrong; the pointers did. Two verifiers were repointed at the commit their
citations were taken at. **Not the v1.0 tag** — that tag predates the aircraft
adapters, and `csia/aircraft/adapters/ardupilot.py` does not exist in it. This
makes v1 research more reproducible than before, since a v1 claim was
previously being checked against whatever CSIA happened to be today. No
research finding, report, CSV or ledger was edited.
