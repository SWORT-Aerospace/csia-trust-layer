# Reading the CSIA Flight Assurance first page

**The first page is `assurance_summary.txt`.** It answers the same questions
in the same order for every log. This guide explains each section and each
state word. It does not explain any particular log.

## 1. The header

```
CSIA FLIGHT ASSURANCE: ASSURANCE SUMMARY (offboard; no flight-control authority)
log: P01.ulg   analyzer ..., semantics ..., profile multirotor-quad r1, view ...
SUPPORT: SUPPORTED | PARTIAL (...) | UNSUPPORTED (...)
```

- **The versions** identify exactly which rules produced the page. The same
  log and the same versions always give the same page.
- **SUPPORT** says whether the log is inside the validated scope (see
  `SUPPORT_MATRIX.json`). For PARTIAL and UNSUPPORTED it names the reasons.

## 2. The sections, in order

| section | what it tells you |
|---|---|
| **WHAT HAPPENED?** | the conclusions, each with its state word (section 3). "UNCONFIRMED" lines are observations that no conclusion was allowed to use, with the reason |
| **WHEN DID IT START?** | each detected event: the onset estimate, the first alarm, when the change was complete, and the first abnormal output |
| **WHICH SUBSYSTEM IS AFFECTED?** | only subsystems with a **confirmed** conclusion. Unconfirmed observations are not listed as affected |
| **WHAT CAUSES REMAIN POSSIBLE?** | every explanation the evidence has **not** ruled out |
| **WHAT WAS ELIMINATED, AND WHY?** | each ruled-out explanation, with the evidence that ruled it out and its value |
| **WHAT EVIDENCE SUPPORTS THIS?** | the admitted evidence behind each conclusion: monitor, value, unit, threshold, time window |
| **WHAT EVIDENCE WAS REJECTED, AND WHY?** | monitor outputs that were **not admitted**, with a plain reason (e.g. "vehicle maneuvering: valid only in near-steady flight") |
| **WHICH MONITORS SHARE THE SAME SOURCE?** | how many adverse outputs there were, and how many **independent lines** they amount to. Two monitors fed by the same signal count once |
| **WHAT WAS NOT OBSERVABLE?** | coverage counts by class (section 4), and the evidence the log cannot provide (e.g. "battery current not measured") |
| **WHAT ADDITIONAL MEASUREMENT WOULD RESOLVE THE AMBIGUITY?** | for each remaining explanation, which evidence would eliminate it |
| **WHAT CHANGED IN THE CONFIGURATION?** | estimator aiding changes, resets and sensor selection changes during the flight |
| **ALERTS** | PX4's own warnings and failsafes, with identical re-raised warnings grouped into one line |

## 3. State words

**There are no percentages on this page.** The analyzer has no calibrated
probability model, so it does not print one. It uses these words instead:

| word | meaning |
|---|---|
| **UNIQUE** | exactly one explanation remains, and the evidence for it is sufficient |
| **AMBIGUOUS** | the symptom is established, but more than one explanation remains. The page lists them and what would separate them |
| **SUPPORTED** | the symptom is supported by admitted evidence |
| **NO_CONSISTENT** | the admitted evidence contradicts every explanation in the profile |
| **NO_EVIDENCE** | nothing adverse was admitted, so there is nothing to explain |
| **UNCONFIRMED** | an adverse monitor output that no conclusion may use. The reason is given |
| **not justified: ...** | why a single attribution is not made (e.g. only one domain of evidence) |

**AMBIGUOUS is a correct answer** when the log does not contain the evidence
that would separate the explanations. It is not a failure of the tool.

## 4. Coverage classes

**Every profile record (a thing the analyzer could judge) × monitor is in
exactly one class.** None of them means "healthy" unless it says NO_ANOMALY.

| class | meaning |
|---|---|
| OBSERVED | an adverse value was observed |
| NO_ANOMALY | observed and within its threshold. **partial** = not for the whole flight. For a monitor that compares before and after an event (e.g. ESC telemetry response), it means **no change at that event**, not that the signal is correct |
| NO_COVERAGE | no monitor in this log covers the record |
| UNAVAILABLE | the evidence was missing or refused (the reason is kept) |
| STALE | the evidence was too old to use |
| FAULTED | the monitor itself was not valid (e.g. its input had a log gap) |
| NOT_APPLICABLE | the record does not apply to this vehicle or moment |
| UNKNOWN | anything the classes above do not describe |

**A record that was not observed is never reported as fine.**

## 5. Receipts (`receipts.json`)

**One receipt per conclusion, holding:**
- the conclusion and its state word;
- the supporting, refuting and rejected evidence, each with value, unit,
  threshold, window, content time and monitor health;
- the rejection reasons;
- the source lineage: which signals each piece of evidence comes from;
- the configuration;
- the profile and rule versions;
- what remains possible, and what would resolve it.

**Use a receipt when** you want to check one conclusion yourself, or hand it
to a colleague.

## 6. What the page never does

- It never turns silence into health.
- It never reports a probability.
- It never names a single cause when more than one remains.
- It never commands or changes the vehicle.
