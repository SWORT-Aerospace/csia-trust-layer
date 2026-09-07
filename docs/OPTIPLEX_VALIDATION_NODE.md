# OptiPlex validation node — a permanent Linux assurance worker

**What it is for:** running the assurance suite continuously on a machine that
is not this container, so portability stops being a claim and becomes a
measurement.

**What it must never do:** modify source. It reports; a human decides.

---

## 1. Do not assume the distribution — detect and record it

Every run records what it ran on, and **nothing in this document assumes an
Ubuntu version.** `tools/assurance/portability_probe.py` captures OS, kernel,
architecture, distro id and version, interpreter, and a hash of the full
installed distribution set.

**This container measured itself** and the record is committed at
`research/physical_validation/results/PORTABILITY_HOST_current.json`:

| field | value |
|---|---|
| distro | Ubuntu 24.04.4 LTS |
| kernel | 6.18.44-fc-v24 |
| architecture | x86_64 |
| Python | 3.12.3, CPython |

**That is one row of the portability matrix, and one row is not a matrix.**
See §5.

## 2. Setup

```bash
git clone <repo> csia-trust-layer && cd csia-trust-layer
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pip install z3-solver hypothesis psutil   # assurance extras
.venv/bin/python tools/assurance/portability_probe.py --out /var/lib/csia/host.json
```

The probe is the **first** thing to run: if the host cannot produce a
fingerprint, nothing measured on it can be attributed.

## 3. The nightly sequence

Each stage runs even if an earlier one fails, so one broken stage does not hide
the rest. `scripts/optiplex_nightly.sh` is the script; the order is:

| # | stage | command |
|---|---|---|
| 1 | environment fingerprint | `tools/assurance/portability_probe.py` |
| 2 | unit tests | `.venv/bin/python -m pytest tests/ -q` |
| 3 | publication guards | `make check-blocking` |
| 4 | support firewall | `pytest tests/test_assurance_*.py` |
| 5 | bounded formal | `tools/assurance/bounded_verify.py` |
| 6 | hostile-input fuzz | `tools/assurance/hostile_input.py` |
| 7 | minimized reproducers | `tools/assurance/minimize.py` |
| 8 | decision replay | `tools/assurance/decision_replay.py` |
| 9 | portability comparison | `portability_probe.py --compare` against the stored baseline |
| 10 | resource envelope | `tools/assurance/resource_envelope.py` |
| 11 | differential, five implementations | `tools/assurance/differential.py` |
| 12 | process failure and recovery | `tools/assurance/process_recovery.py` |
| 13 | configuration proof | `tools/assurance/config_proof.py` |
| 14 | build and dependency provenance | `tools/assurance/build_provenance.py` |
| 15 | mission-layer tests | `pytest tests/test_mission_*.py` |
| 16 | mutation probe | `tools/xr/mutation_probe.py` |
| 17 | **quality ratchet** | `tools/xr/quality_ratchet.py --check` |
| 18 | stress-layer tests | `pytest tests/test_stress_layer.py tests/test_stress_regression.py` |
| 19 | stress catalog | `csia_stress/campaign.py --mode catalog` |
| 20 | **stress regression** | `tools/xr/stress_regression.py --check` |

**The ratchet is the stage that stops quality drifting down.** Coverage and
mutation score may not fall below `research/mission/results/QUALITY_FLOOR.json`,
which records what was actually achieved rather than a target. The floor only
moves **up**, by a deliberate `--update` in the commit that earned it; lowering
it is an edit somebody has to justify in review. Stage 16 is slow — minutes,
not seconds — and runs against a copy of the tree, so it sits near the end
where a hang cannot starve the fast stages.

**A ratchet only ratchets within one measurement definition.** Each mutation
entry in the floor records the *targets* and *test subset* it was measured
over, and the ratchet compares scores only when both match. If they differ it
reports `NOT_COMPARABLE` and exits **2**, which the nightly maps to
INCONCLUSIVE — not PASS, and not FAIL either, because nothing was compared and
a false regression is as misleading as a false pass. Re-baselining onto a new
subset is then a deliberate `--update`. This exists because MX-015 records the
cost of forgetting it: two subsets were compared, a conclusion was drawn about
the frozen core, and the decisive test file was missing from *both* sides.
Including it moved `hypothesis.py` from 0.000 to 0.448.

That also means the floor's `mutation_frozen_core: 0.35` must be read next to
the nine-file `test_subset` stored beside it. **It is not "the frozen core's
mutation score."** It is what that probe measured over those tests.

**Stage 20 is exact, not tolerant.** The stress campaign is bit-for-bit
deterministic, so the regression gate compares detection latency, recovery
time, escalation and attribution *exactly* — no tolerance band, because a
tolerance band is where a behavioural change hides. It exits 2 (INCONCLUSIVE)
when the baseline was recorded under a different seed, count or applicability
matrix, and 1 when behaviour actually moved. Stages 19 and 20 take roughly a
minute and six minutes respectively; see `docs/STRESS_TESTING.md`.

**Stage 8 is expected to FAIL, and that is not a broken node.** Decision replay
is DIVERGENT on both platforms (HF-004) and the software-hardening gate does
not count it as PASS. It runs nightly anyway so that the day it *changes* is
visible — in either direction. A nightly report reading `decision_replay FAIL`
is the current, correct state.

## 4. The three outcomes

| verdict | meaning |
|---|---|
| **PASS** | every stage met its declared criterion |
| **REGRESSION** | a stage that previously passed now fails |
| **INCONCLUSIVE** | a stage could not run, or could not compare — missing dependency, absent artifact, timeout, or a measurement the stored baseline is not comparable to. **Never reported as PASS** |

`INCONCLUSIVE` exists because a skipped stage reading as green is the failure
mode this repository has already hit once: a freeze test that *skips* on a
fresh clone because the tag is local-only, and a skip looks like a pass.

A stage declares its own "could not compare" exit code by prefixing its call
with `INCONCLUSIVE_RC=<n>` in `scripts/optiplex_nightly.sh`; stage 17 uses
`INCONCLUSIVE_RC=2`. Without that prefix every non-zero, non-timeout exit is
still a FAIL, so a stage cannot quietly downgrade a real failure.

## 5. The portability matrix, and why it is nearly empty

| environment | status |
|---|---|
| this container — Ubuntu 24.04.4, x86_64, CPython 3.12.3 | **MEASURED** |
| Ubuntu 22.04 x86_64 | **NOT MEASURED** |
| Debian 12 x86_64 | **NOT MEASURED** |
| containerised clean environment | **NOT MEASURED** |
| ARM64, physical | **NOT MEASURED** |

**Containers cannot be run in the environment that wrote this.** The Docker
client is installed and there is no daemon:

```
$ docker pull ubuntu:22.04
failed to connect to the docker API at unix:///var/run/docker.sock ...
```

So the cross-distribution matrix **was not run**, and is reported empty rather
than approximated. Running a second interpreter on the same host and calling it
a second environment would have been worse than an empty table.

**Emulated ARM is not physical ARM.** If ARM64 is ever added under emulation,
its timing figures are not comparable to a physical board's, and the contract's
level 4 already says timing is never compared across hosts.

## 6. What a green nightly does and does not establish

**Does:** the suite passes on this host, with this dependency set, at this
commit; the decisions match the stored baseline at contract levels 1 and 2.

**Does not:** anything about a host that has not run it. A host with no
recorded measurement is **UNDECLARED**, not "probably fine".
