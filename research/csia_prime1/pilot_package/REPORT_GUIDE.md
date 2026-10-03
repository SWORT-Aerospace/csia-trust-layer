# Reading the CSIA Flight Assurance first page (PRIME-1)

**The first page is `assurance_summary.txt`.** It answers the same questions
in the same order for every log. This guide explains each section and each
state word. It explains no particular log.

## 1. The header

```
CSIA FLIGHT ASSURANCE (PRIME-1): ASSURANCE SUMMARY (offboard; no flight-control authority)
log: P01.ulg   release prime1, analyzer ..., semantics ..., profile ..., view ..., support contract ...
SUPPORT: <state> (configuration ...; validation level ...)
```

- **The versions** fix exactly which rules produced the page.
- **SUPPORT** is decided **before** anything is interpreted (`QUICKSTART.md`
  section 3).
- **The validation level** says how that configuration has been validated:
  SIMULATION, HIL, REAL_LOG_CONTEXT_ONLY or PHYSICAL_VALIDATED. None is
  PHYSICAL_VALIDATED yet.

## 2. The ten sections, in order

| section | what it tells you |
|---|---|
| **1. WHAT HAPPENED** | each confirmed conclusion with its state word, then each adverse observation that was **not** confirmed, with its size as a multiple of its threshold. Or "nothing adverse was observed in the records CSIA could judge" |
| **2. WHEN** | each discovered event and what opened it (section 4 below) |
| **3. WHAT CSIA CAN JUSTIFY** | the statements the admitted evidence supports, and the explanations it eliminates |
| **4. WHAT CSIA CANNOT JUSTIFY** | what the log does not support: a single root cause when several remain; a physical fault from an unconfirmed observation; anything about records that were not observed |
| **5. WHY** | the reason codes behind the attribution and each conclusion |
| **6. KEY EVIDENCE** | the adverse outputs: monitor, value, unit, threshold, time window |
| **7. EVIDENCE REJECTED** | outputs that were refused or unavailable, with a plain reason (e.g. "vehicle maneuvering: valid only in near-steady flight") |
| **8. DEPENDENCY / SHARED SOURCES** | how many independent lines of evidence the adverse outputs amount to. Two monitors fed by the same signal count once |
| **9. MISSING INSTRUMENTATION** | what the log cannot measure, and which measurement would separate the remaining explanations |
| **10. NEXT ENGINEERING CHECK** | the check that would settle what remains |
| **TECHNICAL DETAIL** | remaining and eliminated explanations, coverage counts, configuration changes, grouped alerts |

## 3. State words (no percentages anywhere)

| word | meaning |
|---|---|
| UNIQUE | exactly one explanation remains, and the evidence for it is sufficient |
| AMBIGUOUS | the symptom is established; more than one explanation remains (listed, with what would separate them) |
| SUPPORTED | supported by admitted evidence |
| NO_CONSISTENT | the admitted evidence contradicts every explanation in the profile |
| NO_EVIDENCE | nothing adverse was admitted |
| observed, not confirmed | an adverse output no conclusion may use; the reason is given |

**AMBIGUOUS is a correct answer** when the log lacks the evidence to separate
the explanations.

## 4. Event semantics

| event | meaning |
|---|---|
| RPM_DEFICIT_EVENT | an ESC reported less rotor speed than its recent level, against the other rotors |
| RPM_EXCESS_EVENT | an ESC reported more rotor speed than its recent level, against the other rotors |
| COMPENSATION_CHANGE_EVENT | the controller started asking one motor for more than the others, in steady flight |
| ESC_OFFLINE_EVENT | an ESC reported itself offline |
| px4.* | PX4's own monitors (warnings, failsafes, failure detector, allocator, estimator) |

**An event only says that a channel changed enough to analyse.** It is
never a conclusion.

## 5. Coverage classes (`coverage_states.json`)

| class | meaning |
|---|---|
| OBSERVED | an adverse value was observed |
| NO_ANOMALY | observed and within threshold (**partial**: not for the whole flight). For a before/after monitor: no change at that event, not "the signal is correct" |
| NO_COVERAGE | no monitor in this log covers the record |
| UNAVAILABLE | missing or refused (the reason is kept) |
| STALE | too old to use |
| FAULTED | the monitor itself was not valid |
| NOT_APPLICABLE | the record does not apply here |
| UNKNOWN | anything else |

**A record that was not observed is never reported as fine.**

## 6. Receipts (`receipts.json`)

**One receipt per conclusion, with these fields:**
- type, conclusion and status;
- supporting, refuting and rejected evidence, and the rejection reasons;
- source lineage and independent line count;
- producer health and content times;
- configuration epoch and coverage;
- what would resolve the ambiguity;
- version.
