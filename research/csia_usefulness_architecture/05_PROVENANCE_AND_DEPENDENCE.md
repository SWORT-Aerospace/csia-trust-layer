# Provenance, correlated evidence and double counting (Phases 6, 7, 29)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

## 1. Phase 6: the minimum useful provenance

**The test.** A provenance field is on the runtime path only if it **changes
a decision**. Everything else is audit-only.

| provenance element | changes a decision? | how | kept where |
|---|---|---|---|
| `dependency_tags` | **yes** | targeted invalidation (`04_CONFIGURATION_TRANSITIONS.md` §3); refutation independence (§3.2 below); the `COMMON_SOURCE` explanation of a disagreement (`07_CONFLICT_SEMANTICS.md`) | record, as a bitmask |
| `derived_from` (evidence ids) | **yes** | invalidating a record invalidates what was derived from it; a derived record may not be used together with its parent as two witnesses | record |
| `context_epoch` | **yes** | admissibility against the current context | record |
| `contract_id` and hash | **yes** | admissibility rules | record |
| `producer_id` and version | indirectly | producer health; validation status | record |
| input channel ids and source identity | indirectly | become `src:` tags | record (ids); tags on the runtime path |
| transformation history, raw input hashes, computation time | no | post-flight reconstruction only | ledger debug view |

**Graph form.** No database and no generic graph store. The "provenance
graph" is:

- the `derived_from` DAG, with fan-in bounded by the contract;
- the tag inverted index (`04_CONFIGURATION_TRANSITIONS.md` §3.1).

For export, it maps one-to-one onto W3C PROV (S065):

- a record is a `prov:Entity`;
- a producer evaluation is a `prov:Activity`;
- the producer is a `prov:Agent`;
- `derived_from` is `prov:wasDerivedFrom`.

The export is an offline tool, not a runtime dependency.

**Example: an estimator lane switch.**

1. Every record carrying `est:ekf_lane_1` is invalidated.
2. So is every record whose `derived_from` chain reaches one of them.
3. Records tagged only `src:esc_telemetry` or `src:rail_5v` are untouched.

## 2. Phase 7: how correlated evidence is handled today

| mechanism | behaviour | source |
|---|---|---|
| v2 `EvidenceRecord.dependencies` | a free-form tuple, explicitly **not** an independence score | S001 |
| v2 attribution | uses dependency reachability to name a shared adverse dependency as a common-cause alternative; does not use it to discount agreement | S003 |
| v2 localization | set elimination is **idempotent**: a predicate that is true twice rules a hypothesis out exactly once, so duplicate agreement cannot inflate anything | S002 |
| v2 attribution UNIQUE | any nominal record elsewhere counts, whether or not it shares a source with the candidate | S003, S044 |
| provenance-cut metric (research) | shown **not** to be independence; runtime topology changes invisibly | S025 |

**So double counting of agreement is not the main risk in v2.** Set
elimination is idempotent, the same property Denœux requires of a cautious
rule for non-distinct evidence (S060).

**The main risk is common-mode wrong evidence:**

- one faulty source feeding several records that **refute** the true
  hypothesis together;
- a source testifying to its own health (FM-06, FM-19).

**The brief's three cases.**

- **CUSUM, a Kalman residual and a threshold detector on one signal.** All
  three carry `src:<device.channel>`. Their three NOMINAL readings are one
  source's statement, not three. None of them may refute "that device is
  faulty".
- **Two monitors sharing one estimator residual.** Both carry `est:<lane>`
  and `derived:<residual id>`. They count as one.
- **Two monitors sharing a physical model.** Both carry `model:<id>`. A model
  error moves both.
- **One item derived from another.** `derived_from` links them. They are
  never two witnesses in one predicate.

## 3. Phase 29: the policy

### 3.1 Options considered

| option | what it is | fit for CSIA |
|---|---|---|
| numerical fusion with correlation | fuse estimates, accounting for correlation | CSIA fuses no estimates; that is the estimator's job (non-goal) |
| covariance intersection (S059) | consistent fusion of estimates under unknown correlation | the right tool **for estimates**; not applicable to categorical evidence |
| cautious rule (S060) | idempotent combination for non-distinct belief functions | the property is right; CSIA's set elimination already has it without belief masses |
| independence classes or scores | a number per pair | rejected: no calibrated basis, and S025 showed a structural proxy is not independence |
| dependency groups / common-source tags | categorical tags per record | **adopted**, used conservatively in one direction (§3.3) |
| ATMS-style labels (S061) | each datum carries the assumptions it rests on; conflicts computed from labels | **adopted in reduced form**: tags are the labels; the refutation rule below is the reduced conflict logic |
| majority voting (S066) | redundancy management by vote | only for redundant **same-quantity** channels, and it belongs in the autopilot. CSIA does not vote |

### 3.2 The adopted policy (six rules)

1. **No numerical fusion across producers.** v2's categorical design stays.
2. **Every record carries typed dependency tags.** The kinds are:
   - `src:` a physical device or channel;
   - `est:` an estimator instance;
   - `model:` a model identity;
   - `calib:` a calibration identity;
   - `phys:` a named shared physical disturbance or assumption (for
     example `phys:frame_vibration`);
   - `derived:` a parent evidence id.
3. **Refutation independence.** A record may refute hypothesis H only if its
   tags do not intersect H's suspect scope. The suspect scope is the tags of
   the components H declares faulty, declared once per hypothesis in the
   signature matrix. Otherwise, for that hypothesis, the predicate is treated
   as `None` with reason `NOT_INDEPENDENT`. This removes FM-19 and bounds
   FM-06.
4. **Counting uses classes, not records.** Wherever a rule needs "at least k
   independent confirmations", it counts distinct tag classes. No rule in v2
   needs this today. The SupportCertificate's "at least one active
   discriminator" is the only candidate.
5. **No majority among shared-source records.** A disagreement between
   records that share a `src:` or `est:` tag is reported as
   `COMMON_SOURCE`, never resolved by count (`07_CONFLICT_SEMANTICS.md`).
6. **A record and its parent are never two witnesses** in one predicate. The
   existing `attributable=False` for roll-ups (S001) is generalised to this.

### 3.3 Why tags are used in one direction only

A shared tag **removes** assumed independence. A missing shared tag does
**not establish** it. S025 showed both failure directions:

- distinct sources can share a physical disturbance with no software edge;
- a shared source through different transforms can still give diagnostic
  diversity.

So the policy never concludes "independent" from tags. It only forbids
self-referential refutation and majority counting where a shared origin is
known. Known shared physical disturbances are declared explicitly as `phys:`
tags in contracts.

### 3.4 Cost

- **Tag test:** one bitwise AND per (record, hypothesis) pair, with the
  hypothesis suspect mask precompiled.
- **Scale:** 52 predicates and 30 hypotheses (S011), so at most a few hundred
  ANDs per tick.
