# Defect D-PRIME-1: valid evidence rejected when time is not on the microsecond grid

**2026-10-02. STOP AND REPORT (the brief's stop condition 2). NOT PATCHED.**

## 1. What happens

**A physically meaningless sub-microsecond shift of a log's timestamps
changes the analysis's conclusion.** The same log, shifted by 0.7 µs, loses
its `COMMAND_NO_RESPONSE`, and 13 pieces of valid evidence are rejected as
REGIME_INVALID with "content outside the validated window".

**Reproduction 1: 2.3 V4, a hover loss on motor_0, unperturbed except for
the shift:**

| shift of every timestamp | conclusion | evidence rejected by the gate |
|---|---|---|
| 0 µs | `COMMAND_NO_RESPONSE|motor_0`, AMBIGUOUS | 0 |
| 0.3 µs | same | 0 |
| 0.4999 µs | same | 0 |
| 0.5 µs | same | 4: the rate transient, [0, 0.2] s window |
| **0.5001 µs** | **no symptom, NO_EVIDENCE** | **13** |
| **0.7 µs** | **no symptom** | **13** |
| 1.0 µs | `COMMAND_NO_RESPONSE|motor_0` | 0 |

**Reproduction 2:** the same on 2.3's SYNTHETIC stock log
(`synthetic_stock.synth("motor")`). 0, 0.3 and 1.0 µs keep the symptom;
0.7 and 2.7 µs lose it with 13 rejections. Pinned by a strict expected-fail
test in `tests/test_csia_prime.py`.

## 2. Why

**Two halves of the code round time differently:**
- **the stock adapter rounds every output's content time to the
  microsecond:** `content_time=round(content_t, 6)` in
  `adapters/px4_stock.py`. The analysis ticks are keyed the same way in
  `runs.stock_flight`.
- **the anchor the admissibility gate checks against is not rounded:**
  `events={"stock.event": current.t0}` in `runs.stock_flight`.

**The 2.2 gate** (`admissibility.check`) then requires
`event + lo - 1e-9 ≤ content_time ≤ event + hi + 1e-9`.

**What goes wrong.** When the event time is off the microsecond grid,
rounding can move the content time past the window's end. The window's end
is exactly where the stock producers put their content. The overshoot is up
to 0.5 µs, which is 500 times the gate's 1 ns tolerance. The evidence is
then refused as REGIME_INVALID: a validity verdict on correct evidence, for
a reason that is neither calibration nor context.

## 3. Where it can and cannot happen

| input | time grid | affected? |
|---|---|---|
| any PX4 ULog through `StockLog.from_ulog` | whole microseconds (ULog stores µs integers) | **no**. Every historical 2.3, RB-001 and pilot result was made this way |
| XSYS-001 known-onset replays | onsets with 3 decimals | no |
| a `.npz` extract written by another tool with float seconds | arbitrary | **yes** |
| a resampled or interpolated log | arbitrary | **yes** |
| **an external instrument producer** (the bench load cell, logic-analyzer timestamps at ns resolution: `B4_MATCHED_AB_PROTOCOL.md`) | ns | **yes**: the planned bench witness would hit it |
| the stress envelope v1's jitter variable (continuous noise on timestamps) | arbitrary | yes. That is how it was found. Its v1 "lost" results for jitter are this defect, not degradation (`STRESS_ENVELOPE.md`) |

**No historical result is affected.** Every committed result came from
ULogs or 3-decimal onsets. The 2.3 reports regenerate byte for byte
(`BASELINE_PRIME.json`).

**Some historical reports do contain this reason code, by design.** 2.3
reports V5, V6, V12 and V13, and the 2.2 invalid-window cases, contain
`CONTENT_OUTSIDE_VALIDATED_WINDOW`. Those are the designed behaviour:
- when a later event becomes the anchor, evidence held from an earlier
  event falls outside the new event's window;
- example, V5: E1's EARLY outputs (content 41.8 s) are refused at 49.9 s,
  once E2 (49.7 s) anchors the window.

They are not this defect, which needs off-grid times.

## 4. Why it is not patched here

**The brief:** "STOP and report rather than broadly patch if: … Evidence
Assurance 2.2 … rejects valid evidence for a reason not explained by
calibration/context."

**Candidate fixes, for the owner to choose (none applied):**

| fix | where | effect on history |
|---|---|---|
| round the anchor to the microsecond as well (`events={…: round(current.t0, 6)}`) | product layer (`runs.py`) | none for µs-grid inputs (rounding a µs value is the identity) |
| stop rounding content times | `adapters/px4_stock.py` | the content-time column of reports changes by < 1 µs on every log, so historical report bytes change. **Stop condition 6:** not acceptable without approval |
| raise the gate's tolerance to the time grid (1 µs) | 2.2 `admissibility.py` | changes a 2.2 rule; affects every producer |
| require every adapter to emit µs-grid times | the bench adapter's contract | a workaround, not a fix |

**Recommendation:** the first fix. It is the smallest, it keeps 2.2's rule
intact, and it removes the inconsistency where it was introduced. It
should be applied with the strict expected-fail test flipping to pass, and
with the historical replays re-verified.

## 5. Consequence for the PRIME plan

**The bench hold point gains one item:** before any external-instrument
evidence enters, D-PRIME-1 is either fixed (owner-approved) or the bench
adapter's contract requires µs-grid content times.

**The product's real-ULog behaviour is unaffected.**
