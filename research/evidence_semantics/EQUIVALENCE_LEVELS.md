# Equivalence levels

Items 7, 8 and 9. Five levels, each defined on a run of the pipeline, each
measured by `contract_checker.py`. The point of separating them is item 8's
question: **does divergence at one level propagate to the next?** It does not,
and the counterexamples below are measured, not constructed.

---

## The levels

Let `r` be a run: an input word driven through one ingest path into the frozen
core and the failsafe policy, sampled at every 25 Hz tick from word onset.

| Level | `~_L` holds when… | Read at | Projection |
|---|---|---|---|
| **VALUE** | the numeric payloads crossing into the core are equal, in order | `T5` | `proj_value` |
| **STATE** | the quality tokens crossing into the core are equal, in order, AND the core's slot history agrees | `T5`, `T6` | `proj_state` |
| **EVIDENCE** | operational admissibility agrees: whether `fresh[sensor]` ever closes, and how long after word onset | `T7` | `proj_evidence` |
| **DIAGNOSIS** | the sensor's trust trajectory agrees | `T8` | `proj_diagnosis` |
| **ASSURANCE** | the failsafe level history, the time of first escalation, and the set of issued actions all agree | `T9` | `proj_assurance` |

The order is the order of the pipeline, not a lattice: none of these implies
another in either direction, which is the whole point of §"Non-propagation".

### `~_D`, the relation item 7 asks to be pinned down

Item 7 asks for the exact meaning of "diagnostic/assurance equivalence" in

> if `P(r1,r2)` then `T(r1) ≁_D T(r2)`

There is no single right answer, so the contracts name which one they mean.
`ARDUPILOT_INGEST_CONTRACTS/*.json` states, per forbidden merge, the
downstream consumer that needs the distinction (`needed_by`), cited to a line
in `failsafe.py`. The checker then reports the **first level at which the two
runs become equivalent** (`first_equivalent_level`) rather than asserting one
definition — so a reader who disagrees about which level should count can
re-read the same result at their own level.

### Stamp invariance

Every projection is order-only or a duration from word onset. The v1.1
adapter stamps a core sample with the tick it handed it over on; `plugins.py`
and `ulog_source.py` stamp with the message's own time. A tick-indexed
comparison would report that convention as a semantic difference — the
previous package established this the hard way — so no projection here is
tick-indexed. Residual error from the two conventions is at most one tick
(0.040 s), against reported effects of 0.12–0.32 s.

### The null control

Every cross-path number is accompanied by the same comparison on `V^k`, an
all-nominal word of the same length. If the control already diverges at a
level, that level is reported `CONFOUNDED_BY_CONTROL` and contributes
**nothing** to any finding. Measured control trust deltas:

| family | pairs involving `plugins_py` | `v1_1_adapter` vs `ulog_source_py` |
|---|---|---|
| gnss | 0.0001 | 0.0 |
| battery | 0.034 | 0.0 |
| mag | 0.025 | 0.0001 |

The v1.1 adapter and `ulog_source.py` agree **exactly** on nominal words for
gnss and battery, which is what makes that pair the clean one to reason from.
`plugins.py` differs from both at the fourth decimal or worse even with no
fault present, because it feeds the core at message times with a different
effective sample rate.

---

## Non-propagation: three measured counterexamples

### 1. VALUE diverges; STATE, EVIDENCE, DIAGNOSIS and ASSURANCE do not

**Word `X` (one `BATTERY_STATUS` with `current_battery == -1`),
`v1_1_adapter` vs `ulog_source_py`.** All five controls are equivalent, so
nothing here is confounded.

What crosses into the frozen core:

| path | token | value |
|---|---|---|
| `v1_1_adapter` | `V` | **5.00 A** — the previous reading, retained |
| `ulog_source_py` | `V` | **−1.00 A** — the sentinel, passed through as a measurement |

| level | equivalent? |
|---|---|
| VALUE | **No** |
| STATE | Yes |
| EVIDENCE | Yes |
| DIAGNOSIS | Yes |
| ASSURANCE | Yes |

A six-amp disagreement about a safety-relevant channel, and **every level
above VALUE is identical.** The consequence classification is `NONE` and it
is recorded as `NONE`. Item 19 is explicit: do not inflate severity when the
consequence stops upstream.

(Add `plugins_py` and the same raw condition produces a third answer:
**0.00 A**, token `M`, from `max(msg.current_battery, 0) / 100.0` at
`plugins.py:194`. Three committed decoders, one raw condition, three
different currents into the same frozen core: **5.00 A, 0.00 A, −1.00 A**.)

### 2. VALUE and STATE diverge; EVIDENCE and ASSURANCE do not

**Same word `X`, `v1_1_adapter` vs `plugins_py`.** Tokens differ (`V` vs `M`)
and values differ (5.00 A vs 0.00 A):

| level | equivalent? | note |
|---|---|---|
| VALUE | No | |
| STATE | No | |
| EVIDENCE | **Yes** | |
| DIAGNOSIS | (control also diverges — CONFOUNDED, not counted) | |
| ASSURANCE | **Yes** | |

Across the whole battery alphabet this pair diverges at STATE on 90/120 words
and at EVIDENCE on only 15/120. So **75 words diverge at STATE and stop
there.**

### 3. EVIDENCE diverges; the failsafe reaches the same state with the same actions

**GNSS, `v1_1_adapter` vs the other two paths.** 106 attributable word-pairs
are classified `ASSURANCE_STATE`. In every one of them:

* the level history is `NORMAL → CAUTION` on **both** paths,
* the issued action set is identical on both paths
  (`SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES`) — it never differs, on any word,
* and the only difference is **when**: the v1.1 adapter escalates
  **0.32 s later** (80 words) or **0.12 s later** (26 words).

So the consequence is a latency, not a decision. `CONTROL_FAILSAFE` — a
different action set — is **never reached** anywhere in this package.
That is the honest ceiling of the finding.

---

## Semantic collapse (item 9) vs semantic divergence (item 10)

**Divergence** compares two implementations on one input:
`T_A(w) ≁ T_B(w)`. **Collapse** compares two inputs on one implementation:
`r1 ≠ r2`, the contract requires them to stay distinct, and yet
`T(r1) ~ T(r2)`.

Item 9's warning is enforced structurally: a merge is a violation **only** if
it appears in a contract's `forbidden_merges` with a `needed_by` clause
citing a downstream consumer. `allowed_merges` are declared and never
reported — for example `N` and `S` are merged deliberately in all three
contracts, because past `max_age` "never arrived" and "arrived too long ago"
both mean the consumer has no current measurement and `FailsafePolicy` reads
only `state.fresh`.

### Shortest collapsing pairs found by exhaustive search

Distinguishable at the wire (`T1` projections differ), indistinguishable
downstream. Search is breadth-first over lengths 1–4, so each is minimal by
construction.

| family | path | shortest collapsing pair | words explored before it was found |
|---|---|---|---|
| gnss | `v1_1_adapter` | **`I` / `N`** | 3 |
| gnss | `plugins_py` | `II` / `INI` | 29 |
| gnss | `ulog_source_py` | `II` / `INI` | 29 |
| battery | `v1_1_adapter` | **`V` / `X`** | 2 |
| battery | `ulog_source_py` | **`V` / `X`** | 2 |
| battery | `plugins_py` | `VNX` / `NVX` | 32 |
| mag | `v1_1_adapter` | **`Z` / `N`** | 3 |
| mag | `plugins_py` | **`Z` / `N`** | 3 |
| mag | `ulog_source_py` | `ZV` / `ZZ` | 8 |

Three length-1 collapses on the v1.1 adapter, one per family. Each is the
shortest possible counterexample in its alphabet: a single message.

## What is NOT claimed

* Not that these levels are the right ones in general. They are the levels
  this pipeline actually has.
* Not that the hierarchy is new. Multi-level observational equivalence is
  standard in process algebra and DES.
* Not that non-propagation is surprising. It is what the data-processing
  inequality would lead you to expect; measuring **where** each divergence
  dies is the only part that required running anything.
