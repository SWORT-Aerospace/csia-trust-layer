# FUNCTION ELIGIBILITY — INPUT REQUIREMENTS

§34. **Preparation only. No eligibility policy is implemented.**

What a future deterministic policy table may depend on, given the surviving
v1.1 architecture (`TRUST_FLAT_PLUS_SEQUENTIAL`).

## Available inputs

| input | source | type | notes |
|---|---|---|---|
| `trust[node]` | trust recursion | float 0–1 | per sensor node; **without** neighbour propagation once §30 is approved |
| `fresh[node]` | canonical ingestion | bool | freshness against `MaxAge`; Phase 1 made this truthful |
| `missing_reason[channel]` | canonical ingestion | enum | `NOT_RECEIVED` / `STALE` / `SENTINEL` / `NO_3D_FIX` — Phase 1 |
| `sequential_alarm[node]` | CUSUM bank | bool | five covered nodes only: `gps`, `mag`, `battery`, `motor_esc`, `vibration` |
| `leader`, `posterior` | frozen diagnosis | str, float | unchanged from v1 |
| `active_evidence_count` | Phase 2 | int | |
| `discriminating_evidence[competitor]` | Phase 2 | dict | |
| `leader_identifiable` | Phase 2 | bool | |
| `ambiguity` | Phase 2 | `UNIQUE`/`AMBIGUOUS` | structural, never a score margin |
| `prior_sensitive` | Phase 2 | bool | |
| `support_state` | Phase 2 | enum of 4 | |
| `assurance_level` | frozen failsafe policy | enum | |

## What a policy must NOT depend on

- **`UNKNOWN` / model adequacy** — not implemented (§24).
- **A high posterior alone.** The Phase 2 requirement is binding: a leader at
  posterior 0.9998 with zero discriminating evidence is `NON_IDENTIFIABLE`,
  and any eligibility rule reading only the posterior would grant a function
  on evidence that does not exist.
- **A sequential alarm as cause attribution.** The CUSUM is per-node and
  carries no cause-discriminating evidence; it may gate *availability*, never
  *attribution*.
- **Anything learned.** §15 of the master brief: deterministic policy tables,
  no AI, no learned policy, no direct commands.

## The one design constraint Phase 2 imposes

Any function requiring a *named cause* must require
`leader_identifiable = True`. Any function requiring only *health* may read
trust and freshness. A function must not be granted on `SAFE_AMBIGUITY` as if
it were `EVIDENCE_BACKED`.

Nothing further should be designed until Phase 4 begins.
