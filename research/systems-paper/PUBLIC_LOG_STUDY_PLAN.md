# PUBLIC REAL-LOG EXPOSURE STUDY — PLAN

Brief B5. Claim `SC-22` in `CLAIMS.csv`, status **PROVISIONAL**.

---

## 0. STATUS: NOT RUN. BLOCKED BY EGRESS POLICY.

No logs were downloaded. No result exists. Nothing in this document reports a
measurement.

Measured, this session:

```
review.px4.io:443   CONNECT -> 403   (policy denial, recorded by the agent proxy)
logs.px4.io:443     CONNECT -> 403
doi.org:443         CONNECT -> 403
api.crossref.org    CONNECT -> 403
dblp.org            CONNECT -> 403
```

The organisation's egress policy denies these hosts for this session. Per the
proxy's own guidance a policy denial is reported, not retried or routed
around. **A study of public flight logs cannot be executed from here.** The
plan below is what to run when a host with access exists.

## 1. Question

Descriptive **exposure**, not detection accuracy:

> On real flights that nobody staged, how much of the time does the layer hold
> a concentrated leader while the evidence that would distinguish it from its
> nearest rival is absent?

**This is not a fault-detection accuracy study, and must never be written up
as one.** Public logs carry no ground truth. An operational event in a log is
not a labelled fault, and labelling one would be inventing the answer.

## 2. Source, and why this one

**PX4 Flight Review public logs** (`review.px4.io`), using the site's own bulk
download mechanism (`/download?...`) rather than scraping.

Do **not** create a new dataset. If the public corpus suffices — and for a
descriptive exposure study it does — creating one adds unverifiable
provenance and a licensing question for no scientific gain.

## 3. Provenance to preserve, per log, no exceptions

| field | why |
|---|---|
| original URL | the only way a reader can fetch the same bytes |
| licence | PX4 Flight Review logs are user-uploaded; licence is per-log and must be recorded, not assumed |
| source ID | the site's own log id |
| original SHA-256 | of the downloaded file, before any processing |
| download timestamp | UTC, ISO-8601 |
| PX4 version | from the log header, not inferred |
| vehicle type | from the log header |
| normalization version | the version of *our* ingest that produced the derived record |

Stored as `research/systems-paper/results/public_logs/MANIFEST.csv`, one row
per log, committed. A log whose licence cannot be established is **excluded
and recorded as excluded**, never silently dropped.

## 4. Sample selection — BEFORE looking at any CSIA output

The selection rule is fixed and written down **before** the first log is
scored. Target **≥ 100 usable logs** if compute and download permit.

Proposed rule, to be frozen at run time:

1. Enumerate the site's log index over a stated date range.
2. Keep logs with: a complete GPS stream, a complete IMU stream, duration
   ≥ 120 s, and an establishable licence.
3. Order by source ID ascending and take the first N.

**This is a deterministic prefix, NOT a random sample, and it must not be
called random.** If a genuinely randomised sample is wanted, the seed and the
enumeration snapshot must both be committed, and the word "random" may then be
used — and only then.

## 5. Quantities to measure

All of these are properties of *our layer's output*, not of the vehicle, and
none requires ground truth:

| quantity | definition |
|---|---|
| `T_identifiable` | time with `support_state = EVIDENCE_BACKED` |
| `T_ambiguous` | time with `support_state = NON_IDENTIFIABLE` |
| `T_support_lost` | time with `D(leader, nearest rival) = ∅` while a leader exists |
| `T_high_posterior_no_support` | time with leader posterior ≥ 0.9 **and** `T_support_lost` |
| `T_unavailable` | time with `support_state = NO_APPLICABLE_EVIDENCE` |
| `T_not_applicable` | time the relation is inapplicable by construction (distinct from unavailable) |

Reported per log and pooled, with the pooled figure carrying the per-log
spread — a mean over 100 logs of wildly different durations is close to
meaningless on its own.

**`T_high_posterior_no_support` is the headline.** It is the field
counterpart of the bench result in `MECHANISM_A.md`, and it is measurable
without knowing whether anything was actually wrong.

## 6. What may and may not be concluded

**May:** "on N public flights totalling H hours, the layer spent X% of armed
time holding a leader above 0.9 with no active term distinguishing it from its
nearest rival."

**May not:**
- any statement containing "false negative", "missed fault", "detection rate",
  "precision" or "recall";
- any statement that an operational event *was* a fault;
- any statement that the exposure is *harmful* — that requires knowing what
  the vehicle was doing and what a consumer would have done with the output.

## 7. Reproducibility

The manifest plus a pinned ingest version makes the study re-runnable from the
same URLs. If a log is later deleted from the site, the manifest's SHA-256
still identifies what was used, and the study reports how many of its inputs
are still retrievable at write-up time.

## 8. Cost estimate

Unknown from here — the site's log sizes could not be sampled. Budget the
download and the ingest separately and record both, because a study that
cannot state its own compute cost cannot be planned by anyone else.
