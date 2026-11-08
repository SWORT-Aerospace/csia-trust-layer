# 14 — Reproduction commands

Every command is run from the repository root at the Phase-I freeze commit.
Commit hashes are in `15_REPOSITORY_STATE.json`.

```bash
git clone https://github.com/SWORT-Aerospace/csia-trust-layer
cd csia-trust-layer
git checkout <phase1_scientific_reference.freeze_commit_full>
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,data,logs,mavlink]"
bash csia/native/build.sh          # so the C-vs-Python parity tests run
```

---

## 1. Results that need no autopilot

These run from the checkout alone.

| result | command | writes |
|---|---|---|
| **self-occlusion arms A / B / C** | `PYTHONPATH=. python research/wp_c4/self_occlusion_experiment.py` | `research/wp_c4/results/self_occlusion.json` |
| **fix-preserving contrast** | same command; arm A is in the same artifact | same |
| **structural enumeration, signature and SOI** | `PYTHONPATH=. python research/wp_c3/effective_signature.py` | `research/wp_c3/results/effective_signature.json` |
| reliability structure | `PYTHONPATH=. python research/wp_c3/reliability_structure.py` | `research/wp_c3/results/reliability_structure.json` |
| design-rule audit | `PYTHONPATH=. python research/wp_c3/design_rule_audit.py` | `research/wp_c3/results/design_rule_audit.json` |
| certificate and exposure set | `PYTHONPATH=. python research/wp_c1/certificate.py` | `research/wp_c1/results/certificate.json` |
| joint lattice | `PYTHONPATH=. python research/wp_c1/lattice.py` | `research/wp_c1/results/joint_lattice.json` |
| design inverse | `PYTHONPATH=. python research/wp_c1/design_inverse.py` | `research/wp_c1/results/design_inverse.json` |
| criticality | `PYTHONPATH=. python research/wp_c2/criticality.py` | `research/wp_c2/results/criticality.json` |
| **repair comparison (IMU, behind a flag)** | `PYTHONPATH=. python research/wp_c2/repair_experiment.py` | `research/wp_c2/results/repair_experiment.json` |
| **repair candidate table (GPS)** | `PYTHONPATH=. python research/wp_c6/minimum_repair.py` | `research/wp_c6/results/minimum_repair.json` |
| cut sets | `PYTHONPATH=. python research/wp_c4/cutsets_post_promotion.py` | `research/wp_c4/results/cutsets_post_promotion.json` |
| sparsity probe | `PYTHONPATH=. python research/wp_c4/sparsity_probe.py` | `research/wp_c4/results/sparsity_probe.json` |
| adversarial search | `PYTHONPATH=. python research/wp_c4/adversarial_search.py` | `research/wp_c4/results/adversarial_search.json` |
| boundary inputs | `PYTHONPATH=. python research/wp_c4/boundary_inputs.py` | `research/wp_c4/results/boundary_inputs.json` |
| field-set universe | `PYTHONPATH=. python research/wp_c6/field_set_universe.py` | `research/wp_c6/results/field_set_universe.json` |
| partial-containment sweep | `PYTHONPATH=. python research/wp_c6/partial_containment_sweep.py` | `research/wp_c6/results/partial_containment_sweep.json` |
| `gvalid` unconditional check | `PYTHONPATH=. python research/wp_c6/gvalid_unconditional.py` | `research/wp_c6/results/gvalid_unconditional.json` |
| **closed-form escalation verification** | `PYTHONPATH=. python research/wp_c8/escalation_algebra.py` | `research/wp_c8/results/escalation_algebra.json` |

**The closed-form verification is the one to run first if you only run one.**
It reads its constants from `csia/trust_engine/engine.py` and
`csia/runtime/failsafe.py` and re-derives the boundary against the shipping
`TrustCore`. It needs no autopilot.

---

## 2. Results that need ArduCopter 3.3 SITL

The prebuilt binary is **not** in this repository. Obtain the dronekit-assets
ArduCopter 3.3 SITL tarball (binary dated 2015-10-22), then:

```bash
export CSIA_SITL_BINARY=/path/to/arducopter
export CSIA_SITL_EEPROM=/path/to/eeprom.bin
```

`research/wp_c6/q_gvalid_campaign.py:locate_sitl()` prints exactly what is
missing if either is unset.

| result | command | writes |
|---|---|---|
| **gate-closure campaign** | `PYTHONPATH=. python research/wp_c6/q_gvalid_campaign.py` | `research/wp_c6/results/q_gvalid_campaign.json` |
| satellite ladder / expanded campaign | `PYTHONPATH=. python research/wp_c7/campaign_expanded.py` | `research/wp_c7/results/campaign_expanded.json` |
| **step sweep and glitch mechanism** | `PYTHONPATH=. python research/wp_c7/glitch_mechanism.py` | `research/wp_c7/results/glitch_mechanism.json` |
| false-healthy exposure | `PYTHONPATH=. python research/wp_c7/false_healthy.py` | `research/wp_c7/results/false_healthy.json` |
| variance investigation | `PYTHONPATH=. python research/wp_c7/variance_investigation.py` | `research/wp_c7/results/variance_investigation.json` |
| **ramp contrast / response surface** | `PYTHONPATH=. python research/wp_c8/response_surface.py` | `research/wp_c8/results/response_surface.json` |
| **four-quantity exposure calculation** | `PYTHONPATH=. python research/wp_c8/four_quantity_metrics.py` | `research/wp_c8/results/four_quantity_metrics.json` |

Useful flags on the SITL scripts: `--speedup N` (default 10), `--flights N`
(default from `PREREG`), `--workdir PATH`, `--quiet`.

**`COMMAND ISSUED != FAULT INJECTED`.** Every SITL arm records a downstream
observable. If `gvalid_frac_closed_after_onset` is 0 in a denial arm, the
injection did not reach the receiver and the run is invalid regardless of what
was commanded.

**Do not run these against ArduCopter 4.x** without renaming the SIM
parameters; see `07` section 4.

---

## 3. Real-log aggregation

```bash
python tools/fetch_real_logs.py            # acquisition; refused on some hosts
python tools/build_dataset_manifest.py     # content-addressed manifest
```

The exposure artifact `datasets/reports/exposure_v2.json` is committed. CI
asserts the manifest regenerates byte-identically and validates the exposure
report against `datasets/schemas/result_v1.schema.json`.

Acquisition is deliberately refused on non-permitted hosts by
`csia/data/paths.py`; `datasets/reports/acquisition_backlog.json` records what
is pending and where it can be reproduced.

---

## 4. Figures

```bash
PYTHONPATH=. python research/wp_c4/figures.py
PYTHONPATH=. python research/wp_c6/figures.py
PYTHONPATH=. python research/wp_c7/figures.py
PYTHONPATH=. python research/wp_c8/figures.py
python tools/publication/sync_paper_figures.py
```

All four write to the repository-root `figures/` directory. The last command
refreshes the self-contained copies inside `papers/csia_systems/figures/`.

Or, in one step: `make figures`.

---

## 5. Manuscript and guards

```bash
make tex-deps          # pinned TeX Live set
make paper-systems     # -> build/papers/csia_systems/main.pdf
make check             # every publication guard
make test              # full pytest suite
```

`make check` currently **fails on the bibliography guard by design**: 37
unresolved provenance markers in `papers/csia_systems/refs.bib`. See `13`.

---

## 6. Regenerating this evidence export

```bash
PYTHONPATH=. python publication/system_paper_i/build_evidence_export.py
```

It reads only committed artifacts and rewrites
`publication/system_paper_i/evidence_export/` plus the tarball. If a number in
the export disagrees with an artifact, the artifact wins and the generator is
the thing to fix.
