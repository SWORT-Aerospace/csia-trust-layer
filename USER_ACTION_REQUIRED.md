# User action required

**Written:** 2026-09-06 · physical-validation + standards-candidate program.
**Audience:** the repository owner. Every item below is blocked on a decision
or a permission that this agent does not have and must not assume.

Each item states **what is blocked**, **what was measured**, **what the agent
did instead**, and **what specifically is needed**. Nothing here is a
suggestion for improvement; these are things that cannot proceed.

---

## A. BLOCKING — the three freeze tags exist only on this machine

**Measured, 2026-09-06:**

```
$ git tag -l
archive/handoff-source-of-record
csia-dual-paper-evidence-freeze
csia-v1.0-research-final
csia-v2-phasec-frozen
v0.7.0

$ git ls-remote --tags origin
758f4ae...  refs/tags/v0.7.0        <- the only tag on the remote
```

**Why it matters more than it looks.** Four load-bearing tags are local-only,
and one of them —`csia-v1.0-research-final`— is what
`tests/test_v1_frozen.py::test_diagnostic_core_is_unchanged_since_the_freeze`
diffs against. On a fresh clone that tag does not exist, so the freeze test
**skips**, and a skipped freeze test reads as green. The repository already hit
this: the tag push was refused with HTTP 403 while the commits went through,
and `test_diagnostic_core_matches_its_recorded_hashes` exists precisely because
of it — a hash-file check that works without git history.

Beyond CI, every claim of the form "the frozen core is unchanged since the
freeze" is checkable by a reviewer **only if the reviewer can fetch the tag.**
Today they cannot.

**What is needed:** push the four tags, or grant this agent tag-push
permission. `git push origin --tags` from a session that has it.

**What was done instead:** the hash-file fallback is in place and passing, and
`docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md` and the failure ledger both record the
tags as local-only rather than implying they are published.

---

## B. BLOCKING — zero bibliography entries are verified, and this environment
cannot verify them

**Measured, 2026-09-06** (`papers/BIB_VERIFICATION_LEDGER.yaml`):

| status | count |
|---|---|
| `UNVERIFIED` | 10 |
| `CORROBORATED_NO_PUBLISHER_RECORD` | 9 |
| **`VERIFIED`** | **0** |

**Why this environment cannot close it.** Re-measured this session:

```
$ curl -o /dev/null -w '%{http_code}' https://doi.org/            -> 000
  (dl.acm.org, ieeexplore.ieee.org, link.springer.com,
   www.sciencedirect.com, arxiv.org: all 000)

$ curl "$HTTPS_PROXY/__agentproxy/status"
  "recentRelayFailures": [
    {"kind": "connect_rejected",
     "detail": "gateway answered 403 to CONNECT (policy denial or upstream
                failure)",
     "host": "api.crossref.org:443"}, ...
```

The agent proxy negotiates the CONNECT tunnel and the gateway then answers 403.
This is a policy denial at the gateway, not a TLS problem and not something a
retry or a different client fixes. WebSearch works; fetching a publisher record
does not.

**What is needed:** a human with journal access confirms each entry against the
publisher's record — title, authors, venue, year, DOI — and marks it
`VERIFIED`. Nine entries are already corroborated from search results and need
only the publisher check; ten have not been read at all.

**What was NOT done, deliberately:** no entry was marked verified on the
strength of a search snippet, and no citation was invented to make a guard
pass. `tools/publication/bib_guard.py` enforces the marker vocabulary and
`tests/test_bib_verification_ledger.py` asserts the two lists agree.

**Consequence if unresolved:** neither manuscript can be submitted. This is the
single hardest blocker in the repository.

---

## C. DECISION REQUIRED — unify `configs/vehicle/*.yaml` and `profiles/*.yaml`,
or keep them separate

**The seam** is documented in full at `docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md`
and was first recorded as FL-005.

**Why the agent did not decide it.** `csia/deploy/flight_log.py` writes
`sha256(json.dumps(vehicle_config, sort_keys=True))[:16]` into every flight-log
header. Merging the two files changes that hash for every existing deployment
config, which **orphans every committed trial manifest that cites one**. That
is an evidence consequence, not a refactor, and it is the owner's call.

**What was done instead:** the two files are now checkable against each other
(`csia-edge validate --deployment` exits 3 on conflict, never prefers one), and
`csia.deployment/2` adds an opt-in profile reference in **new files only**.
`configs/vehicle/example_quad.yaml` still hashes to `da6321053178df5b`, pinned
by a test.

**The three options, with what each costs:**

| option | cost |
|---|---|
| keep both, cross-checked (**status quo, implemented**) | two files to keep in sync; the cross-check catches disagreement but not omission |
| migrate new vehicles to schema 2, leave schema 1 files frozen | none to existing evidence; two schemas coexist indefinitely |
| unify into one file | every existing flight-log header hash becomes unresolvable, and every trial manifest citing one must be re-derived or annotated |

---

## D. DECISION REQUIRED — hardware purchase for evidence tiers E2 and above

The evidence tiers are defined in
`research/physical_validation/PAPER_IMPACT_LEDGER.yaml`. Current state:

| tier | what it needs | status |
|---|---|---|
| E0 desktop simulation | — | complete |
| E1 current-stack SITL/SIH | — | complete (ArduPilot 4.8, PX4 SIH) |
| **E2 real flight-controller hardware** | a flight controller, a companion computer, a bench harness | **NOT STARTED — needs purchase** |
| E3 real sensor + physical fault | E2 plus a fault-injection rig | NOT STARTED |
| E4 physical actuator/output path | E3 plus a thrust stand | NOT STARTED |
| E5 controlled physical flight | E4 plus an airframe, a site and an authorised pilot | NOT STARTED |

`hardware/validation_rig/PURCHASE_JUSTIFICATION.csv` itemises what each tier
requires and what claim it would license. **No purchase is assumed and no
result above E1 is written anywhere.**

**What is needed:** a decision on which tier to fund. E2 is the smallest step
that changes what either manuscript may say.

---

## E. AUTHORISATION REQUIRED — before any physical trial

Not needed today (nothing physical has run), listed so it is not discovered
late. Every shipped profile already declares these under `safety:`:

* `props_removed_for_bench: true` — props stay off for every bench phase. A
  flight phase that needs them must say so explicitly and separately.
* `independent_pilot_authority_required: true` — a human with an independent
  kill path, not the person running the experiment.
* `shadow_only: true` — CSIA has no command path in any mode, enforced
  structurally in `csia/deploy/shadow.py`, not by configuration.

**Out of scope by instruction and not implemented anywhere:** RF jamming, GPS
spoofing transmitters, counter-UAS behaviour, autonomous targeting.

---

## F. FOR INFORMATION — what is NOT blocked

So the list above is read as short rather than as everything:

* The repeated current-stack campaign (P8) needs **no new hardware**, and its
  preregistration is frozen before any trial
  (`research/physical_validation/prereg/MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md`).
  It does need a simulator, and two measured facts shape what it can claim —
  both are recorded in §2 of that preregistration:
  - neither ArduPilot SITL nor PX4 SIH was installed in this environment
    (`sim_vehicle.py`, `arducopter` and `px4` are all absent, and
    `firmware.ardupilot.org` answers 000 through the proxy). ArduPilot builds
    from source here: the clone succeeds, `waf configure --board sitl` succeeds,
    and the toolchain is present;
  - **the original E1 build cannot be identified.** No autopilot commit,
    firmware hash or build date appears in any Mechanism A artifact, and
    "ArduPilot 4.8" is a development branch — the newest release tag is
    `Copter-4.7.1`. So a repeat pins a NEW commit
    (`e21b732a07ce2b632ea99b098ee6ab7ece0971ea`) and establishes within-build
    repeatability of that build. It cannot be described as a repeat of the
    original run, and the design cannot separate a build difference from
    run-to-run variation.
* The DEA standards-candidate work is implementation-neutral and software-only.
* Mutation testing, the profile/science firewall and the clean-room structural
  reference all ran to completion in this environment.

---

## G. Where the record lives

| file | what it holds |
|---|---|
| `research/physical_validation/FAILURE_LEDGER.yaml` | every failure, negative result and self-correction, append-only |
| `research/physical_validation/PAPER_IMPACT_LEDGER.yaml` | what new evidence would license each manuscript to say — and what it would not |
| `research/physical_validation/mutation/MUTATION_SURVIVORS.md` | which parts of the science no test pins |
| `docs/VEHICLE_PROFILE_VS_DEPLOYMENT.md` | the configuration seam, §C above |
| `papers/BIB_VERIFICATION_LEDGER.yaml` | the bibliography, §B above |
