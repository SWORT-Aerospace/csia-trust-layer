# GRADUATION MATRIX

§32 / §57. Status per requirement. **No fake promotion**: a row moves only
when the evidence for that column exists in the repository.

Columns: `NOT_STARTED` · `DESIGNED` · `IMPLEMENTED` · `VALIDATED_SITL`
(deterministic replay/SITL) · `VALIDATED_HIL` · `VALIDATED_PHYSICAL` ·
`PUBLICATION_READY`.

| | requirement | status | exact blocker |
|---|---|---|---|
| **G1** | physical FC / HIL validation | `NOT_STARTED` | no hardware in this environment; no HIL runbook or scripts written yet |
| **G2** | real-aircraft shadow flight | `NOT_STARTED` | no aircraft; no shadow runbook, no output firewall test, no preflight automation |
| **G3** | verified-clean exposure + false-alert denominator | `NOT_STARTED` | no clean protocol, no exclusion rules, no registry. **Zero verified-clean hours.** No rate claim is made or supportable |
| **G4** | rigorous GRAPH vs FLAT baseline | **`VALIDATED_SITL`** | done on 9 deterministic scenarios. Verdict `GRAPH_NO_MATERIAL_GAIN`. Blocker for higher: not replicated on HIL or real flight; not re-run on a denser graph or a distrusted-hub topology |
| **G5** | support / ambiguity-aware diagnosis | **`VALIDATED_SITL`** | implemented and validated on 9 scenarios. Blocker for higher: not exercised on real telemetry; `UNKNOWN`/unmodeled deliberately not implemented pending a model-adequacy test |
| **G6** | Python ↔ embedded C/C++ equivalence | `NOT_STARTED` | deliberately deferred: §33 forbids porting before the architecture decision, and that decision is still partial (sequential arms not run) |
| **G7** | multi-platform + multi-sensor replication | `NOT_STARTED` | Phase 1 fixed ingestion on ArduPilot **and** PX4 paths, but no replication matrix has been run. Phases 2/3A used the ArduPilot-derived scenario catalogue only |
| **G8** | contribution surviving a full-text prior-art audit | `NOT_STARTED` | candidate B closed as formulated (`PROVENANCE_METRIC_INSUFFICIENT`); the prior-art gate returned `INCONCLUSIVE_MISSING_FULLTEXT` because no scholarly host is reachable from this environment. **Blocker is library access, not analysis** |
| **G9** | formal + empirical result that is not an implementation defect | `NOT_STARTED` | no surviving research candidate. Everything delivered in v1.1 is engineering and is labelled as such |

---

## Product maturity (§56)

**M2 — cross-platform simulation validated**, and that is the ceiling the
evidence supports.

- M0 research algorithm — passed long ago
- M1 deterministic software prototype — yes
- **M2 cross-platform simulation validated — partial**: ingestion is fixed and
  tested on ArduPilot, PX4 and ULog paths (Phase 1); diagnosis and ablation
  are validated on the deterministic scenario catalogue only. Claimed as M2
  with that caveat stated, not as a clean M2
- M3 embedded-equivalent — no C port exists
- M4 physical-FC HIL — no hardware
- M5 real-aircraft shadow — no aircraft
- M6 meaningful clean exposure — zero verified hours
- M7 — out of scope by instruction

## Research maturity

**None established.** The current frontier candidate is closed as formulated.
`research/effective_evidence_independence/` records why, and the prior-art
question is unanswered rather than answered favourably.

## What would move the most rows, in order

1. **Library access** — unblocks G8 alone, and it is the only blocker for it.
2. **Run Phase 3B (T0–T4)** — completes the architecture decision, which
   unblocks G6 (§33 forbids porting before it).
3. **A Pixhawk-class FC on a bench** — unblocks G1, then G2, then G3.
