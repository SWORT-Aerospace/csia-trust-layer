# eVTOL certification relevance

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1. Every regulatory
statement below is **V0** (search summaries of EASA, FAA and Federal Register
documents). None was read in full.

## What certification already forces

| requirement | what it forces | runtime or design time? | source |
|---|---|---|---|
| EASA SC-VTOL continued safe flight and landing | account for changes in performance ("range, expected height loss, remaining rate of climb") after a single failure **or combination of failures** not extremely improbable | **design time and flight manual**: performance data and procedures | K034 (gap-search R053) |
| EASA MOC SC-VTOL VTOL.2135 controllability | the Modified Handling Qualities Rating Method is an accepted means of compliance, including after lift/thrust-unit failures | design time (flight test) | K034 |
| EASA MOC battery documents (e.g. thermal runaway) | battery safety | design time | K034 |
| FAA AC 21.17-4, powered-lift type certification | airworthiness criteria by certification level | design time | K034 |
| FAA powered-lift SFAR (Nov 2024) | energy reserve: 20 min VFR, 30 min IFR | operational rule (planning) | K034 |
| NASA eVTOL design practice | battery sized "for boosted hover, boosted climb, and OEI operations" | design time | K035 |
| dynamic reserve research | reserves that depend on battery state | proposal | K020 |
| eVTOL emergency-landing power research | predicted power limit including emergency-landing power | research | K019 |

## Does certification already force an equivalent calculation?

- **At design time, yes.** CSFL analyses and OEI power sizing are a
  **design-time** equivalent of G02's composition for defined failure cases.
  They compute performance after failures and combinations of failures
  (K034, K035).
- **At runtime, no requirement was found.** No searched source shows a
  runtime requirement to compute a composed, conservative capability margin
  (FT: the MOC text was not read).
- **The certification pull is therefore toward design-time performance
  data.** It points to runtime estimation only indirectly:
  - through state-dependent reserves (K020);
  - through emergency-landing power prediction (K019).
- **Certification value of the G02 residue: moderate.** It is higher for
  G02-L, the battery-side emergency-landing power, than for the four-way
  composed margin.
