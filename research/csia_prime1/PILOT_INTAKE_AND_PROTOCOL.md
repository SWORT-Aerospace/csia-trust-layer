# Pilot intake, blind protocol and local data workflow (PRIME-1 Phases 22, 23, 27, 30)

**2026-10-03. Privacy-conscious: ask only for what the analysis needs.**

## 1. Intake specification (Phase 22)

**Per log, and nothing more.** The fields are those
`engagement.INTAKE_FIELDS` accepts:

| field | why it is needed | required |
|---|---|---|
| the ULog file | the analysis input | yes |
| `px4_version` | the support decision cross-checks the log's own version record | yes |
| `airframe_or_vehicle_class` | the support decision cross-checks the vehicle type | yes |
| `esc_telemetry` | whether ESC RPM telemetry was enabled (propulsion evidence needs it) | yes |
| `known_modifications` | hardware or firmware changes the log cannot show | if any |
| `notes` | anything the customer wants recorded | optional |
| `expected_event_time_s` | **only in NON-BLIND mode**, if the customer chooses; stored, never given to the Analyzer | blind: refused |

**Not asked for:**
- customer identity beyond an engagement label;
- mission data;
- locations;
- operator names;
- the customer's diagnosis (until after the seal).

## 2. The blind protocol (Phase 23), enforced by `csia-assure engagement`

| step | who | what | enforcement |
|---|---|---|---|
| 1 | customer | selects logs | - |
| 2 | customer | withholds the diagnosis | `ingest` refuses an expected-event time in blind mode |
| 3 | SWORT | hashes the received inputs | `ingest`: SHA-256, stored read-only in `raw/`, append-only `INTAKE.json` |
| 4 | SWORT | records version and configuration | `run`: release, view, support contract, profile, producer versions, code digest per log in `RUNS.json` |
| 5 | SWORT | runs the Analyzer once | `run` analyses each log once; it refuses after the seal |
| 6 | SWORT | freezes the result | `seal`: every input and output hash, every version, and the seal's own hash in `final/SEAL.json` |
| 7 | customer | reveals the ground truth or engineering diagnosis | `reveal` refuses before the seal; the reveal records the seal hash it follows |
| 8 | both | compare | against the sealed outputs; `verify` recomputes every hash |

**No tuning against the pilot before scoring.** The Analyzer version is the
frozen pilot release (`PILOT_FREEZE.json`). A change after the seal is a new
version and a new engagement, never an edit.

## 3. The local data workflow (Phase 27)

```
csia-assure engagement init  ACME-01 --mode blind
csia-assure engagement ingest ACME-01 flight1.ulg flight2.ulg --intake intake.json
csia-assure engagement run    ACME-01
csia-assure engagement seal   ACME-01
csia-assure engagement reveal ACME-01 diagnosis.json
csia-assure engagement verify ACME-01
```

| requirement | how |
|---|---|
| hash inputs | SHA-256 at intake; re-checked before analysis and at `verify` |
| immutable manifest | `final/SEAL.json` with its own hash; written once |
| analysis, profile and producer versions | per log in `derived/RUNS.json`, sealed |
| report hashes | every output file's SHA-256, sealed |
| raw / derived / final folders | `raw/` (read-only customer logs), `derived/` (Analyzer outputs), `final/` (seal, reveal) |
| no accidental git commit of customer logs | every engagement folder gets a `*` `.gitignore`; the repository ignores `*.ulg`, `engagements/` and `customer_data/` |
| no cloud | nothing in the workflow opens a network connection |

## 4. If genuine real logs arrive during the phase (Phase 30)

1. **Hash and freeze them** (`ingest`, then the frozen release).
2. **Do not look at labels or customer diagnosis before analysis** where
   blind use is possible.
3. **Run the frozen PRIME-1 Analyzer once** (`run`) and **seal**.
4. **Only then** reveal and score.
5. **No algorithm change before scoring.** Any change afterwards is a new
   release, evaluated on new data.

**No genuine real propulsion log arrived during PRIME-1.**
