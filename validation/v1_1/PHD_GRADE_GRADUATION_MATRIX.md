# GRADUATION MATRIX

§32 / §57. Status per requirement. **No fake promotion**: a row moves only
when the evidence for that column exists in the repository.

Columns: `NOT_STARTED` · `DESIGNED` · `IMPLEMENTED` · `VALIDATED_SITL`
(deterministic replay/SITL) · `VALIDATED_HIL` · `VALIDATED_PHYSICAL` ·
`PUBLICATION_READY`.

| | requirement | status | exact blocker |
|---|---|---|---|
| **G1** | physical FC / HIL validation | `NOT_STARTED` | no hardware in this environment; no HIL runbook or scripts written yet |
| **G2** | real-aircraft shadow flight | `NOT_STARTED` | no aircraft; no shadow runbook, no preflight automation. The **output firewall is now built and unit-tested** (`csia/v1_1/firewall.py`, default-deny, 14 named control operations rejected) on top of the existing transport guard, so that sub-item is no longer a blocker — the aircraft is |
| **G3** | verified-clean exposure + false-alert denominator | `NOT_STARTED` | no clean protocol, no exclusion rules, no registry. **Zero verified-clean hours.** No rate claim is made or supportable |
| **G4** | rigorous GRAPH vs FLAT baseline | **`VALIDATED_SITL`** | complete. Phase 3A verdict `GRAPH_NO_MATERIAL_GAIN`, confirmed in Phase 3B with the sequential channel present (`T4 − T3` differs on 1 of 9 and is 0.28 s *worse*). Full five-arm selection done; architecture decided as `E: TRUST_FLAT_PLUS_SEQUENTIAL`. Blocker for higher: not replicated on HIL or real flight; no GNSS step mechanism exists in the frozen injector; not re-run on a denser graph or a distrusted-hub topology |
| **G5** | support / ambiguity-aware diagnosis | **`VALIDATED_SITL`** | implemented and validated on 9 scenarios. Blocker for higher: not exercised on real telemetry; `UNKNOWN`/unmodeled deliberately not implemented pending a model-adequacy test |
| **G6** | Python ↔ embedded C/C++ equivalence | `NOT_STARTED` | **everything except the C now exists.** Architecture and API frozen; the golden corpus is frozen (11 cases, 13 500 ticks, hashed manifest); the Tier-B tolerance is derived from IEEE-754 binary32 unit roundoff **before any port exists**; the 2 near-boundary ticks are enumerated. `PHASE5_READY: YES`. The only blocker is that **no C source has been written** — deliberately, per §29 |
| **G7** | multi-platform + multi-sensor replication | `NOT_STARTED` | Phase 1 fixed ingestion on ArduPilot **and** PX4 paths, but no replication matrix has been run. Phases 2/3A used the ArduPilot-derived scenario catalogue only |
| **G8** | contribution surviving a full-text prior-art audit | `NOT_STARTED` | candidate B closed as formulated (`PROVENANCE_METRIC_INSUFFICIENT`); the prior-art gate returned `INCONCLUSIVE_MISSING_FULLTEXT` because no scholarly host is reachable from this environment. **Blocker is library access, not analysis** |
| **G9** | formal + empirical result that is not an implementation defect | `NOT_STARTED` | no surviving research candidate. Everything delivered in v1.1 is engineering and is labelled as such |

**G4 and G5 stay at `VALIDATED_SITL`.** Phase 4 froze an architecture and
built an interface on top of them; it did not add flight data, so neither row
moves. §39 is explicit that no other row may be promoted.

---

## Engineering milestone — not a PhD requirement (§39)

| | |
|---|---|
| **PHASE 4: ARCHITECTURE / API FREEZE** | **COMPLETE** |
| **PHASE 4.5: DEPLOYMENT-SEMANTICS FREEZE** | **COMPLETE** — `PHASE5_READY: YES` |

Gates A–J all pass (`§41`): legacy mode reproduces the GRAPH arm and the
default reproduces T3 `FLAT+SEQUENTIAL`, both bit-identically; requirements
were frozen before outcomes; clean eligibility is stable after a fully
explained 201-tick startup; a 0.9998 posterior with no discriminating
evidence cannot carry a function; one-IMU and dual-IMU behave differently;
the ledger reproduces 159 events over 9 mechanisms; 13 500 payloads validate;
the firewall denies every write and control operation; the full suite passes.

This is an **engineering** milestone. It is deliberately not a row in the
matrix above, because freezing an interface is not evidence about the world.

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
- M3 embedded-equivalent — **no C port exists.** Phase 4 does not move M2 → M3
  and does not claim to: freezing the architecture is a precondition for the
  port, not the port. What changed is that the runtime architecture is now
  `V1_1_ARCHITECTURE_FROZEN`
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
2. ~~Run Phase 3B (T0–T4)~~ — **done.** Architecture decided, so §33 no
   longer blocks the C port. Phase 4 (eligibility / ledger / API) then
   Phase 5 (embedded) is the recommended order; Phase 3C is **not**
   recommended (see `PHASE3C_FEASIBILITY_NOTE.md`).
3. **A Pixhawk-class FC on a bench** — unblocks G1, then G2, then G3.
4. ~~A PX4 replay or bench regression for the `motor_esc` staleness~~ —
   **superseded.** Phase 4.5 reproduced it and found the predicted exposure is
   not reachable: `motor_esc` is inadmissible on both platforms, so it never
   reaches the frozen core at all. The staleness rule was fixed anyway (the
   real exposure was `baro` under jitter) and the live shadow path now passes
   the derived override. See `engineering/v1_1/STALENESS_RUNTIME_SPEC.md`.
5. **Writing the C port** — G6 is the only row with nothing left blocking it
   but the work itself.
