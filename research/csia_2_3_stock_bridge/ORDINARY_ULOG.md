# The ordinary-ULog experience (Phase 20)

**2026-10-02.**

## 1. The product test, as the brief set it

```
python -m csia_evidence_assurance analyze flight.ulg
```

The command takes no fault onset, no XSYS stage-1 features, no sealed
research labels and no research witness files. It must say:
- what CSIA observed and did not observe;
- what events it detected and which producers fired;
- which evidence was independent;
- which hypotheses remain, which evidence was missing, and whether
  attribution is justified.

When the ULog does not hold enough, it must say so.

## 2. What changed in the command line

**The new default.** `analyze` on a `.ulg` now takes the stock path:
- stock topics at default rates;
- event discovery;
- the five stock producers and the 2.2 estimator producer;
- the multirotor quad r1 profile;
- Semantic Core 2.1.1;
- a schema-4 report, summary first.

The default tick is 1 s. Producers run at event checkpoints, so nothing
is missed between ticks.

**The 2.2 path is kept.** `--estimator-only` gives the PX4 estimator
producer alone (schema 3). It is how every 2.2 and pilot report was made.
`runs.resolve(..., stock=False)`, the default for library callers, keeps
it as well, so the pinned reports and the 66-flight batch reproduce
unchanged.

**`analyze-many`** passes `--estimator-only` and `--tick` through to each
input.

## 3. What reaches the analysis, and what does not

| read from the ULog | not read |
|---|---|
| the stock topics in `stock_log.py`'s table, at their logged rates, decimated to PX4's default intervals | in-flight parameter changes (in SITL they are the injection; reading them would hand the onset over) |
| the initial values of the parameters the producers declare (rotor geometry, thrust model, battery cells) | any sidecar, label, onset, or research feature file |
| PX4 log messages of level WARNING and above | the run's own JSON (scoring only, read after the report exists) |
| the logger's dropout records | |

## 4. On ordinary logs

**The logs.** The ten validation flights were recorded with PX4's default
logging. They are the first ordinary logs this project has analysed
end to end.

| question | answer on the validation flights |
|---|---|
| correct | 7 of 10 as stated before flying; no wrong diagnosis in any (`VALIDATION_FLIGHTS.md`) |
| useful | the right motor named in 4/4 losses, with the magnitude (compensation 0.662-0.663 against 1/eta - 1 = 0.667); telemetry faults kept out of the motor; PX4's own warnings shown in the timeline |
| honest | every report lists what it could not observe (4 of 29 profile records observed; no ESC current; battery current not measured; the frozen CUSUM has no coverage) and why the remaining explanations could not be eliminated; attribution "no" in every run |
| reproducible | the same `report.json`, byte for byte, from another working directory with another `PYTHONHASHSEED` (checked on V1, V5, V9); the manifest carries the ULog's SHA-256, the calibration's, the contracts' digests and the code digests, and no machine path |

**Run time.** About 2 s per flight log of 18-37 MB, most of it reading the
log.

**The 2.2 pilot's S1 run** (a SITL lane-selector experiment, 44 MB) also
goes through the stock path (`VALIDATION_SET.json`).

## 5. Where the experience falls short

**Maneuvering logs carry many false events.**
- V5 and V6 have 11 events each.
- Each is dismissed (no symptom), and the report says so event by event.
- But an engineer reads eleven "something may have started here" entries
  for a normal flight (`FALSE_POSITIVES.md`).

**The answer is almost always AMBIGUOUS.** On a stock SIH log the floor is
three explanations. The product says what would resolve them. It cannot
resolve them itself.

**The report is long.**
- About 27-30 KB of text for an 80 s flight.
- The summary fits on a screen; the detail (every evidence value at every
  checkpoint) does not.

**The decoding is SIH-specific.**
- **Thresholds:** calibrated on a nearly noise-free simulator.
- **Topics:** a hardware log will have different ones (ESC current,
  battery current, two IMUs).

The bridge reads those fields, but on SIH they never vary. So the product
path has not seen them non-zero.
