# CSIA v1.1 ENGINEERING MANIFEST

Item 0. What the baseline is, what changed, and what that invalidates.

**This is engineering. Nothing here is a novelty claim.** The vocabulary is
FIXED / HARDENED / VALIDATED / SIMPLIFIED / IMPROVED (item 48).

---

## 1. BASELINE

| | |
|---|---|
| frozen v1 diagnostic-core tag | `csia-v1.0-research-final` |
| frozen v1 tag SHA | `ec5acd189295dab9259d4989657d42184d6142a3` |
| v1.1 starting SHA | `1ba69a5` (Stage 0A commit, on `claude/code-reviewer-repo-export-zicovg`) |
| tree at start | clean |
| test count at start | 971 passing |
| ArduPilot revision | `01a504b` (`/home/user/ardupilot/ardupilot`) |
| PX4 revision | working tree at `/home/user/px4` |

**Frozen core untouched.** `FROZEN_PATHS` — `csia/trust_engine`,
`csia/diagnosis`, `csia/runtime/online.py`, `csia/runtime/failsafe.py`,
`csia/scenarios.py`, `csia/profiles.py` — carry **zero** diff against the
frozen tag. `tests/test_v1_frozen.py` enforces this and passes (Gate A).

### Branch

Item 0 asks for a `csia-v1.1-engineering` branch. It exists locally and points
at this work. **Pushes still go to `claude/code-reviewer-repo-export-zicovg`**,
the branch this session is pinned to; the v1.1 branch has not been pushed
because doing so was not explicitly authorised. Say the word and it goes up.

---

## 2. PHASES

Item 52 requires phase-by-phase commits and forbids writing everything before
the earlier layers are validated.

| phase | scope | status |
|---|---|---|
| **1** | canonical ingestion + known defect fixes | **COMPLETE** |
| 2 | support / ambiguity / unknown | not started |
| 3 | graph-vs-flat + sequential baseline | not started |
| 4 | eligibility + ledger + API | not started |
| 5 | embedded equivalence / benchmark | not started |
| 6 | validation / HIL tooling | not started |

The specs item 50 lists for phases 2–6 —
`SUPPORT_STATE_SPEC.md`, `AMBIGUITY_UNKNOWN_SPEC.md`,
`GRAPH_FLAT_ABLATION_SPEC.md`, `SEQUENTIAL_DETECTOR_SPEC.md`,
`FUNCTION_ELIGIBILITY_SPEC.md`, `ASSURANCE_LEDGER_SPEC.md`,
`OUTPUT_API_SPEC.md`, `EMBEDDED_PORT_SPEC.md`, `PROVENANCE_LOGGING_SPEC.md`,
`VALIDATION_PLAN.md`, `HIL_SHADOW_PLAN.md` — **are deliberately not written.**
Writing a spec for a layer that has not been built is the thing item 52
forbids, and an empty file that looks like a deliverable is worse than an
absent one.

---

## 3. EVERY PRODUCTION BEHAVIOUR CHANGED

Four files, 77 insertions, 5 deletions. None is in `FROZEN_PATHS`.

### 3.1 `csia/aircraft/adapters/base.py` — `_reject_sentinel`

**Was:** recorded the sentinel in `_sentinel_at` and left `_latest` alone.
**Now:** also clears `_latest` for the channel.

**Why:** `_put` already cleared `_sentinel_at` — a real value superseded an
earlier sentinel. The reverse was missing, and `_channel_value` consults
`_latest` first, so a producer saying "not measured now" was masked by
whatever it had measured a moment earlier, until the old value aged out as
**STALE** — the wrong reason. The GNSS path had worked around this locally by
popping `_latest` itself, which is why `NO_3D_FIX` reached the sample
correctly while the battery sentinel did not. That workaround is now the
general rule, applied once.

**Blast radius:** every channel on every adapter that calls
`_reject_sentinel`. This is the widest change in Phase 1.

### 3.2 `csia/aircraft/adapters/ardupilot.py` — magnetometer all-zero

**Was:** `if any(mag) and all(finite(...))` with no `else`.
**Now:** an `else` calling `_reject_sentinel("mag.field_ut")`.

**Why:** the condition correctly recognised the all-zero sentinel and then
dropped it on the floor. Recognising a sentinel and saying nothing about it is
indistinguishable, downstream, from never having looked.

### 3.3 `csia/runtime/ulog_source.py` — battery

**Was:** `"current": float(d["current_a"][i]), "valid": True` — unconditional.
**Now:** `current` is `None` and `current_valid` is `False` when
`current_a == -1`; voltage validity is judged separately on its own sentinel
(`0`).

**Why:** PX4 declares both sentinels machine-readably in its own message
definition, `msg/versioned/BatteryStatus.msg`:

```
float32 voltage_v # [V] [@invalid 0] Battery voltage
float32 current_a # [A] [@invalid -1] Battery current
```

The measured PX4 log in this repository carries 216 battery samples and
**every one is `-1.0`**, so this is the normal case on that hardware, not an
edge case. Voltage keeps its own validity because a pack can report voltage
with no current shunt fitted; dropping it would trade one false statement for
another.

### 3.4 `csia/runtime/plugins.py` — battery

**Was:** `"current": max(msg.current_battery, 0) / 100.0, "valid": True`.
**Now:** `current` is `None` and `current_valid` is `False` on the sentinel.

**Why:** `max(-1, 0) = 0` turned MAVLink's documented not-measured sentinel
(`<field ... name="current_battery" units="cA" invalid="-1">`) into a
confident reading of zero amps. Zero amps is a claim about the aircraft;
"not measured" is a claim about the sensor.

### 3.5 New schema field

Both decode paths now emit **`current_valid`** alongside `valid` in the
`battery` channel dict. `valid` remains the whole-sensor gate and is now
`False` when either constituent is a sentinel. Consumers reading `current`
must handle `None`.

---

## 4. RESEARCH TOOLING REPOINTED (not rewritten)

Item 0 forbids rewriting the research packages. Fixing the defects moved line
numbers in `ardupilot.py` and removed the retained-value behaviour entirely,
so four citations that were **correct about the code they were taken from**
stopped resolving.

The claims did not become wrong. The pointers did. Two verifiers were
repointed at the revision their citations were taken at, rather than at the
working tree:

| file | change |
|---|---|
| `research/semantic_authority_conflict/authorities.py` | added `CITED_REVISION = "76eaa17"` and `_v1_source()`; `csia/` citations now read from that commit |
| `research/evidence_semantics/cross_sensor_audit.py` | added `CITED_REVISION = "2036a2a"`; `pin()` reads `csia/` files from that commit |
| `tests/test_evidence_semantics.py` | the citation re-check resolves against `CITED_REVISION` too |

**Not the v1.0 tag.** `csia-v1.0-research-final` froze the diagnostic core
before the aircraft adapters existed — `csia/aircraft/adapters/ardupilot.py`
is absent from it entirely. Each package pins to its own commit.

### One research artifact regenerated itself

`research/invalidity_masking/results/SOURCE_TO_GATE_TRACE.json` is produced by
a generator that re-derives line numbers from the working tree and records a
sha256 of each cited file, precisely so drift is visible. Running the suite
regenerated it. The diff is **only** `cite`, `line` and the file hashes:

- every `source` string is byte-identical;
- every `establishes` claim is byte-identical;
- `every_gvalid_relation_has_gps_as_an_endpoint` is still `true`.

The GNSS path this package traces was not modified by Phase 1; the pointers
moved because the magnetometer fix added 13 lines above it. The regenerated
file is committed: this artifact is designed to track the current tree and
saying "here is where the GPS invalidity logic lives now" stays true and
useful. Unlike the two verifiers above, nothing here needed repointing.

No research **finding**, report, CSV or claim ledger was edited. This makes v1
research *more* reproducible than before, not less: previously a v1 claim was
being verified against whatever CSIA happened to be today.

---

## 5. KNOWN RESULTS INVALIDATED OR REQUIRING REMEASUREMENT

| result | status after Phase 1 |
|---|---|
| **evidence-semantics**: battery emitted vocabularies `['V']` / `['M','V']` / `['V']` across the three paths | **REQUIRES REMEASUREMENT.** All three paths now refuse the sentinel. The recorded v1 numbers stay labelled v1 and stay in the package; they no longer describe the working tree |
| **evidence-semantics**: "three decoders, one raw condition, three currents: 5.00 / 0.00 / −1.00 A" | **REQUIRES REMEASUREMENT.** Now 5.00 / absent / absent |
| **semantic-authority-conflict**: `DECLARED_VS_EFFECTIVE_SEMANTICS.csv` battery row `(5.0,) / (0.0,) / (-1.0,)` | **REQUIRES REMEASUREMENT** for v1.1. The v1 row stands as a v1 result |
| **semantic-authority-conflict**: 17 conflicts, 8 CROSS_CONSUMER | **REQUIRES REMEASUREMENT.** The battery cross-consumer conflicts are the ones Phase 1 removes |
| **evidence-semantics**: mag collapse at `T3_ingest` | **REQUIRES REMEASUREMENT** |
| **evidence-semantics / authority**: "action sets never differ", "0 of 9 pairs reach ACTION" | **UNAFFECTED as a v1 result**, and the fixes make an action-level difference no more likely |
| frozen-core behaviour, `test_v1_frozen.py` | **UNAFFECTED.** Zero diff |
| the Stage 0A candidate-B findings | **UNAFFECTED.** They cite ArduPilot and PX4 source, not CSIA |

**No v1 number was edited to match v1.1.** Item 49's separation holds: v1
results stay labelled v1; v1.1 results must be newly measured, and Phase 1 has
not re-run those campaigns.

---

## 6. TESTS CHANGED

Two tests asserted the pre-fix behaviour and had to change. Both are recorded
here rather than quietly edited.

| test | was | now |
|---|---|---|
| `test_adapter_core_equivalence.py::test_battery_current_sentinel_is_a_deliberate_improvement` → `..._is_refused_by_both_paths` | asserted `map_mavlink` returns `0.0` (the v1 behaviour) and the adapter refuses | asserts **both** paths refuse. The pre-fix value is preserved in `KNOWN_DEFECTS_PRE_FIX.json` case D4 |
| `test_dual_admissibility_confirmatory.py::test_battery_defect_is_reproducible_from_the_committed_adapter` → `..._is_fixed_and_its_pre_fix_record_preserved` | asserted the retained 5.00 A is still served and that the channel reports `STALE` | asserts the channel reports `SENTINEL` with no value. Turned from a defect reproduction into a defect regression test |

Test count: **971 before, 971 after.**

---

## 7. GATES (item 46)

| gate | requirement | status |
|---|---|---|
| **A** | frozen v1 still reproduces exactly | **PASS** — `tests/test_v1_frozen.py`, zero diff on `FROZEN_PATHS` |
| **B** | canonical ingestion tests pass | **PASS** — `tests/test_v1_1_canonical_ingest.py` |
| **C** | known sentinel/path defects disappear | **PASS** — `KNOWN_DEFECTS_POST_FIX.json`, all four cases |
| **D** | fix-loss reports loss of discriminating support honestly | **NOT REACHED** — Phase 2 |
| **E** | graph-vs-flat comparison executable and matched | **NOT REACHED** — Phase 3 |
| **F** | sequential baseline executable and matched | **NOT REACHED** — Phase 3 |
| **G** | function eligibility deterministic | **NOT REACHED** — Phase 4 |
| **H** | assurance ledger reconstructs transitions | **NOT REACHED** — Phase 4 |
| **I** | Python/C equivalence | **NOT REACHED** — Phase 5 |
| **J** | full test suite passes | **PASS** — 971 passed |

---

## 8. WHAT PHASE 1 DID NOT DO

- **No canonical `ChannelSample` type was introduced.** Item 3 asks for one
  internal representation and warns against ontology inflation. `ChannelValue`
  (`csia/aircraft/sample.py:84-110`) already carries value, unit, quality,
  frame, `missing` reason, `t_source`, `age_s` and note, and already enforces
  that exactly one of value/missing is set. Adding a second type would have
  been the inflation item 3 warns against. What was missing was not a type but
  the **discipline that a sentinel supersedes a stale value** — §3.1. The gap
  in the existing type is `provenance` / `producer` / `transport`, which
  belongs to Phase 9 and is not invented here.
- **No ingest-equivalence campaign across all five paths.** Item 6 asks for
  regression tests over the ArduPilot live adapter, PX4 live adapter, plugins,
  ULog and replay. Phase 1 covers the four defect cases on three of those
  paths. The full matrix is not built.
- **No remeasurement** of the research campaigns §5 lists.
