# Evidence-semantic equivalence — Stage 0

**Verdict: `IMPLEMENTATION_DEFECTS_ONLY`. Novelty: not established, and
actively reduced.** Read `CHATGPT_REVIEW_REPORT.md` first.

The question was: *can an assurance pipeline be automatically verified for
end-to-end preservation of evidence semantics?* The answer is yes, cheaply,
and it is not a research contribution — every component is prior art, and
`PRIOR_ART_MATRIX.md` says so before any code is discussed. What the work
produced is three reproducible defects and a 500-line checker that finds them
in three minutes.

## What is here

| file | what |
|---|---|
| `CHATGPT_REVIEW_REPORT.md` | **the report.** 26 sections, hostile review |
| `PRIOR_ART_MATRIX.md` | the kill-first search, with its method limits stated |
| `CANONICAL_STATE_MODEL.md` | `E = (x,q)`, six states, each with a named producer |
| `EQUIVALENCE_LEVELS.md` | VALUE / STATE / EVIDENCE / DIAGNOSIS / ASSURANCE + non-propagation counterexamples |
| `GNSS_SEMANTIC_TRACE.md` | where `I` becomes `N`, stage by stage |
| `BATTERY_SEMANTIC_TRACE.md` | the disowned 5.00 A, and the three-decoder split |
| `COMPOSITIONAL_ANALYSIS.md` | why per-stage contracts would not have caught this |
| `PX4_FEASIBILITY.md` | the same contracts against `PX4Adapter`; the real ULog |
| `TOOLING_FEASIBILITY.md` | cost, self-validation, HIL plan, CI shape |
| `CLAIM_LEDGER.json` | 24 claims, 3 refuted predictions, 4 self-corrections |
| `EVIDENCE_SEMANTICS_CONTRACT.schema.json` | the contract schema |
| `ARDUPILOT_INGEST_CONTRACTS/` | `gnss.json`, `battery.json`, `mag.json` |

Generated deliverables (item 29 names these; they are rebuilt by the
commands below): `CROSS_PATH_EQUIVALENCE.csv`,
`MINIMAL_COUNTEREXAMPLES.json`, `CAUSAL_BLAME_TRACES.json`,
`DOWNSTREAM_CONSEQUENCES.csv`, `TOOL_SELF_AUDIT.json`,
`CROSS_SENSOR_AUDIT.csv`. Intermediates live in `results/`.

## Code

| file | what |
|---|---|
| `probe.py` | the stage-indexed probe. Drives the REAL adapters, decoders, core and failsafe; reads a canonical token at nine pipeline stages |
| `contract_checker.py` | bounded exhaustive checker: PASS, or violated clause + shortest witness + first collapse + downstream consequence |
| `self_audit.py` | four injected NON-SCORED defects the checker must catch |
| `cross_sensor_audit.py` | all 10 channels, every citation regex-pinned and re-read |
| `px4_probe.py` | `PX4Adapter` as a fourth path; the committed 9.6 MB ULog |
| `reproduce_prior_results.py` | **item 12 hard stop.** Exit 2 = STOP |

## Running it

```bash
make evidence-reproduce     # item 12 hard stop -- run this first
make evidence-check         # the full cross-path check (~190 s)
make evidence-self-audit    # the four injected defects
make evidence-sensors       # source audit, all channels
make evidence-px4           # cross-platform + real ULog
```

Nothing is random and nothing reads the wall clock; re-running produces
byte-identical artifacts.

## The three findings

**1. GNSS.** On the v1.1 adapter, "the receiver reports no 3-D fix" and "no
message arrived" are indistinguishable from the core bridge onward. Shortest
witness: **one message**. First collapse: `to_core_samples`
(`base.py:306-337`) — *not* the adapter, which pops the retained fix and
records `MissingReason.NO_3D_FIX` correctly. The flight log records
"GPS data invalid" for both.

**2. Battery.** `current_battery == -1` — the documented "not measured"
sentinel — leaves `5.00 A` being served as a usable current for 0.5 s, because
`ardupilot.py:181` records the sentinel without popping `_latest`. And the
same raw condition produces **three different currents** across the three
committed decoders: **5.00 A / 0.00 A / −1.00 A**. The `−1.00 A` case is not
synthetic: the committed PX4 log carries `current_a == -1.0` on all 216
`battery_status` samples.

**3. Magnetometer.** An all-zero triple is the source's way of saying "no
magnetometer", and `ardupilot.py:143` has no `else` branch at all — no
`_put`, no `_reject_sentinel`. It collapses **two stages earlier** than the
other families, at `T3_ingest`.

## What the consequence actually is

The strongest downstream effect measured anywhere is a **failsafe latency of
0.12–0.32 s**. The failsafe reaches the same level and issues the **same
actions** on every word, in every family. `CONTROL_FAILSAFE` is never reached
and is not claimed.

## Hard stops honoured

* **Item 12** — 79/120 and shortest `'I'` reproduce **exactly**, and an
  independently written probe agrees on the one fact both can see.
* **Item 27** — no physical HIL. No hardware is connected; `pyserial`
  enumerates only `/dev/ttyS0`. A validation plan is written and nothing here
  is presented as a hardware result.
* **Item 32** — no paper, no large campaign, no change to CSIA production
  behaviour. Nothing outside `research/` and the Makefile was touched;
  `FROZEN_PATHS` are untouched.

## Closest prior art, including internal

Codd's A-marks/I-marks (1979) for the state model; DES diagnosability under
observation masks for the formal result; ParDiff (OOPSLA 2024) for the
method; AUTOSAR E2E for the property.

And closer than any of them: **this repository already contains the
declarations.** `docs/simulation/CHANNEL_SEMANTICS.yaml` states per channel
that `fix_type < 3` is not a zero position, that `-1` is not zero current, and
that an all-zero triple is not a zero field. The field is loaded at
`qualification.py:83` and used at exactly one site as a `note=` string. The
contribution of this package to the contract is to make three existing
sentences checkable — and then to show they are violated.
