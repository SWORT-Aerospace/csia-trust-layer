# Defect D-PRIME-2: an ESC telemetry excess is never discovered, and a late event reports it as NO_ANOMALY

**2026-10-03. STOP AND REPORT (the brief's stop condition 2). NOT PATCHED.**
Found by the pilot bundle's blinding step (`build_pilot_bundle.py`,
`PILOT_BUNDLE.json`), not by a search for it.

## 1. What happens

**2.3's V10 is ESC 3 (motor_2) reporting RPM × 10 from 50 s, with the motor
healthy.** Its committed report and the PRIME sample report show the
excess as an UNCONFIRMED telemetry observation, with no motor symptom.

**The pilot bundle removes, from each SITL log, the two records that reveal
how its fault was injected.** One of them is PX4's
`[failure_injection_manager] Injected: esc wrong, instances 3` message.
Nothing else changes. On the blinded copy:

| | V10 as flown | V10 without the injection message |
|---|---|---|
| events | E1 at 50.004 s, opened by the PX4 message (`px4.log_message`) | E1 at **56.504 s** (6.5 s late), E2 at 78.7 s; both opened by `propulsion.telemetry_change` |
| motor_2 ESC telemetry statistic | DEGRADED, L = −98.7 (an excess), listed as UNCONFIRMED | **NOMINAL** at E1 (EARLY −0.0011, AFTER 0.0002) |
| motor_2 telemetry coverage class | OBSERVED | **NO_ANOMALY** (partial) |
| first page, WHAT HAPPENED? | UNCONFIRMED telemetry excess on motor_2; attribution NO_EVIDENCE | **"nothing adverse was observed"**; attribution NO_EVIDENCE |

**The motor conclusion is still right:** no motor symptom. **The telemetry
fault disappears from the report.** An RPM report ten times too high is
summarised as "nothing adverse", and its monitor is classed NO_ANOMALY.

## 2. Reproduction on the deterministic SYNTHETIC stock log

**`synthetic_stock.synth("telemetry", motor=2, eta=s²)`:** motor_2's
reported RPM is scaled by `s` from 60 s. Commands and body rates are
unchanged, and there is no PX4 message.

| RPM scale s | events | motor_2 telemetry |
|---|---|---|
| 0.5 (deficit) | 1 | DEGRADED 0.75 (OBSERVED) |
| 0.775 (deficit, the demo's) | 1 | DEGRADED 0.399 |
| 0.9 (deficit) | 1 | DEGRADED 0.19 |
| **1.1 (excess)** | **0** | **never evaluated** |
| **1.29 (excess)** | **0** | **never evaluated** |
| **2 (excess)** | **0** | **never evaluated** |
| **10 (excess, V10's)** | **0** | **never evaluated** |

**On the noiseless synthetic log the excess opens no event at all,** so the
telemetry statistic is never computed and no coverage row names it. **On
the SITL log** the corrupted signal's amplified noise eventually trips the
deficit CUSUM 6.5 s late. The event-relative statistic then compares a
corrupted BEFORE window with a corrupted AFTER window and finds no change.

**Pinned by a strict expected-fail test** in `tests/test_csia_prime.py`.

## 3. Why

1. **The telemetry trigger is one-sided.** `events.propulsion_triggers`
   runs Page's CUSUM on `d_tel = reference − q` (`stock_stats.deviations`),
   which accumulates only a **deficit**. A report above the commanded level
   makes `d_tel` negative and never alarms. The module's own table says
   "one-sided CUSUM" (it is documented, not hidden). The consequence for
   an excess was not tested.
2. **The telemetry statistic is event-relative.** It compares the AFTER
   window with the BEFORE window around the discovered event. Its implicit
   validity condition is that **the BEFORE window precedes the change**.
   Nothing checks that. When the event is late, the 2.2 gate admits the
   comparison and it reads NOMINAL. That is **evidence admitted although its
   validity condition does not hold** (stop condition 2).
3. **In 2.3's validation the condition was met by a SITL artefact.** PX4's
   failure-injection manager prints a WARNING at the instant of injection.
   The `px4.log_message` trigger turns it into an event at the true onset.
   **A real fault prints no such message.**

## 4. Reach

**Which results relied on the injection message to open their event** (the
blinding step measured this; `PILOT_BUNDLE.json`):

| log | fault | conclusion without the message |
|---|---|---|
| 2.3 V10 | ESC RPM × 10 | **changed: the telemetry fault vanishes** |
| 2.3 V9 | ESC 2 offline | same conclusion; events differ |
| 2.3 V7 | GPS off | same conclusion; events differ |
| 2.2 pilot S1 | magnetometer off | same conclusion; events differ |
| 2.3 V8 | battery wrong | not in the bundle; not measured |

**Not affected (no injection message; the loss itself opens the event):**
- every motor loss injected through `SIH_MOT_EFFn` (2.3 V1-V4, V12, V13;
  RB-001's flights);
- the stress envelope (its corruption base is a deficit);
- the event-discovery evaluation (C3);
- the technical demo (a deficit);
- the matched-pair case B of the pilot bundle (a deficit; same result as
  the demo).

**Not reopened:** the sealed 2.3 results stand as recorded. Their V10 row
is true of the log as flown. This document records that the log as flown
contained a crutch real logs lack.

**For the product claims** (`CLAIM_EVIDENCE_MATRIX.md`):
- "a telemetry fault was not reported as a motor failure" still holds;
- "telemetry corruption is reported" holds **for deficits only**.

## 5. Why it is not patched

- **The fix is in event discovery and in the statistic's validity
  conditions** (2.3 and 2.2 layers), not in the view. Hiding it in the view
  would be patching from the product layer.
- **Any change to event discovery changes the event lists of historical 2.3
  reports** (stop condition 6). It must come as a new, versioned discovery
  mode with history kept under its old version, as C3 already concluded
  for E2.
- **The brief says STOP that issue, reproduce it, report.** Done.

## 6. Candidate fixes (for a decision, none applied)

| fix | established method | what it changes |
|---|---|---|
| two-sided telemetry CUSUM (an excess arm with its own k, h) | Page's two-sided CUSUM | discovers excesses; needs calibration on the nominal corpus |
| a level check of ESC telemetry against command (not event-relative) as the BEFORE window's validity condition | consistency/validity check | a late event's comparison is refused, not admitted as NOMINAL |
| an absolute telemetry-consistency output reported as context over the whole flight | limit checking | the first page names a telemetry report that is inconsistent with command, with or without an event |
| view wording: an event-relative NO_ANOMALY reads "no change at this event" | — | stops "NO_ANOMALY" being read as "telemetry fine" (wording only; does not fix discovery) |

**Recommended order:**
1. the validity condition (it closes the stop-condition-2 path);
2. the two-sided arm, calibrated on real nominal data with the rest of
   C3's versioned discovery mode.
