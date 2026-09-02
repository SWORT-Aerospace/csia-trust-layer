# CSIA publication and hygiene targets.
#
# Nothing here changes production behaviour. `make check` is what CI runs for
# the publication lane; the science suite is `make test`.
#
# LaTeX: pinned by the Debian TeX Live packages installed in
# .github/workflows/publication.yml and reproduced locally by `make tex-deps`.
# Builds go to build/papers/<name>/ and are never committed.

PY      ?= python
PAPERS  := csia_systems gate_conditioning
BUILD   := build/papers
TEXOPTS := -interaction=nonstopmode -halt-on-error

.PHONY: help
help:
	@echo "Publication:"
	@echo "  make paper-systems   build CSIA Systems Paper I"
	@echo "  make paper-math      build the gate-conditioning paper (scaffold)"
	@echo "  make papers          build both"
	@echo "  make tex-deps        install the pinned TeX Live package set"
	@echo "Guards:"
	@echo "  make bib-guard       fail on unresolved citation markers"
	@echo "  make artifact-map    validate every paper's artifact map"
	@echo "  make figure-sync     check paper figure bundles match figures/"
	@echo "  make phase-guard     Phase-I papers must not cite Phase-II results"
	@echo "  make manuscript-rules  csia_systems hard style rules"
	@echo "  make secrets-scan    credential and local-path scan"
	@echo "  make release-check   scratch-build + sanitize the public archives"
	@echo "  make check           every guard above"
	@echo "Release:"
	@echo "  make evidence-export rebuild the 16-file Paper I evidence export"
	@echo "  make public-release  pack + sanitize the public archives"
	@echo "  make text-bundles    plain-text transfer bundles (committed)"
	@echo "Science:"
	@echo "  make test            full pytest suite (includes doc-count guard)"
	@echo "  make figures         regenerate all figures from committed results"
	@echo "v1.1 deployment:"
	@echo "  make qualification   live channel-semantics check, both platforms"
	@echo "  make sim-ardupilot   qualify against ArduPilot SITL"
	@echo "  make sim-px4         qualify against PX4 SITL"
	@echo "  make gate2-timing    R13 on target hardware (LOG=<flight.jsonl>)"
	@echo "  make campaign        run the scenario suite"
	@echo "  make shadow-run      run CSIA in SHADOW mode"
	@echo "  make replay          replay a flight log"
	@echo "  make test-fast       tests that need no simulator"

# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------
.PHONY: tex-deps
tex-deps:
	apt-get update -qq && apt-get install -y --no-install-recommends \
	  texlive-latex-base texlive-latex-recommended texlive-latex-extra \
	  texlive-fonts-recommended

define build_paper
	@mkdir -p $(BUILD)/$(1)
	@echo "=== building papers/$(1)/main.tex"
	@cd papers/$(1) && pdflatex $(TEXOPTS) -output-directory=$(CURDIR)/$(BUILD)/$(1) main.tex >/dev/null
	@cd papers/$(1) && pdflatex $(TEXOPTS) -output-directory=$(CURDIR)/$(BUILD)/$(1) main.tex >/dev/null
	@test -f $(BUILD)/$(1)/main.pdf || (echo "FAIL: no PDF produced for $(1)"; exit 1)
	@echo "    $(BUILD)/$(1)/main.pdf  ($$(pdfinfo $(BUILD)/$(1)/main.pdf 2>/dev/null | awk '/^Pages/{print $$2" pages"}' || echo built))"
endef

.PHONY: paper-systems
paper-systems:
	$(call build_paper,csia_systems)

.PHONY: paper-math
paper-math:
	$(call build_paper,gate_conditioning)

.PHONY: papers
papers: paper-systems paper-math

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
.PHONY: bib-guard
bib-guard:
	$(PY) tools/publication/bib_guard.py

.PHONY: artifact-map
artifact-map:
	$(PY) tools/publication/artifact_map_check.py

.PHONY: figure-sync
figure-sync:
	$(PY) tools/publication/sync_paper_figures.py --check

.PHONY: phase-guard
phase-guard:
	$(PY) tools/publication/phase_guard.py

.PHONY: manuscript-rules
manuscript-rules:
	$(PY) papers/csia_systems/check.py

.PHONY: secrets-scan
secrets-scan:
	$(PY) tools/publication/secrets_scan.py

# Verifies a release is buildable and clean without leaving an archive behind:
# every allowlisted path exists and is tracked, and a scratch build of each
# archive passes the post-pack scan. Packing is reproducible, so the scratch
# archive is byte-identical to the one `make public-release` ships.
.PHONY: release-check
release-check:
	$(PY) tools/publication/build_public_release.py --check

# `check` deliberately runs every guard and reports all of them before
# failing, so one red guard does not hide the state of the others.
# Guards split by WHO CAN CLEAR THEM.
#
# BLOCKING guards fail on something a change to this repository can fix, so a
# red one is a defect to go and fix now.
#
# ADVISORY guards fail on something only a human with an outside source can
# clear. bib-guard is the case in point: its 37 markers mean "not checked
# against the publisher record", and only a publisher comparison retires them
# (see `make bib-verify`). Leaving it in the same bucket made the aggregate
# check permanently red, and a check that is always red is a check everyone
# learns to ignore -- which is how a genuine blocking failure would slip past.
#
# `check` still fails if EITHER bucket fails, so nothing is hidden; it just
# says which kind of failure it is.
BLOCKING_GUARDS  = artifact-map figure-sync phase-guard manuscript-rules \
                   secrets-scan release-check
ADVISORY_GUARDS  = bib-guard

.PHONY: check-blocking
check-blocking:
	@rc=0; \
	for t in $(BLOCKING_GUARDS); do \
	  echo ""; echo "############ $$t"; \
	  $(MAKE) --no-print-directory $$t || rc=1; \
	done; \
	echo ""; \
	if [ $$rc -ne 0 ]; then echo "BLOCKING GUARDS: FAIL"; else echo "BLOCKING GUARDS: PASS"; fi; \
	exit $$rc

.PHONY: check-advisory
check-advisory:
	@rc=0; \
	for t in $(ADVISORY_GUARDS); do \
	  echo ""; echo "############ $$t"; \
	  $(MAKE) --no-print-directory $$t || rc=1; \
	done; \
	echo ""; \
	if [ $$rc -ne 0 ]; then \
	  echo "ADVISORY GUARDS: FAIL -- needs a human with an outside source"; \
	else echo "ADVISORY GUARDS: PASS"; fi; \
	exit $$rc

.PHONY: check
check:
	@b=0; a=0; \
	$(MAKE) --no-print-directory check-blocking || b=1; \
	$(MAKE) --no-print-directory check-advisory || a=1; \
	echo ""; \
	echo "  blocking guards : $$( [ $$b -eq 0 ] && echo PASS || echo FAIL )"; \
	echo "  advisory guards : $$( [ $$a -eq 0 ] && echo PASS || echo 'FAIL (human verification outstanding)' )"; \
	if [ $$b -ne 0 ] || [ $$a -ne 0 ]; then echo "PUBLICATION CHECK: FAIL"; else echo "PUBLICATION CHECK: PASS"; fi; \
	[ $$b -eq 0 ] && [ $$a -eq 0 ]

# ---------------------------------------------------------------------------
# Release packaging (decisions H-1 .. H-5)
#
# `public-release` is the ONLY way an archive is produced. It packs exactly the
# paths in publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml, then
# unpacks what it built and scans it. A failed scan deletes the archive.
# ---------------------------------------------------------------------------
.PHONY: evidence-export
evidence-export:
	PYTHONPATH=. $(PY) publication/system_paper_i/build_evidence_export.py

.PHONY: public-release
public-release: evidence-export
	$(PY) tools/publication/build_public_release.py

# Plain-text transfer bundles. The tarball handoff failed twice; a .txt
# degrades gracefully where an archive does not -- it can be attached, pasted,
# split, or read straight from the GitHub blob view. Unlike the archives these
# ARE committed, so there is always a retrievable copy that needs no transfer.
.PHONY: text-bundles
text-bundles:
	$(PY) publication/system_paper_i/build_text_bundles.py

# ---------------------------------------------------------------------------
# Science
# ---------------------------------------------------------------------------
.PHONY: test
test:
	$(PY) -m pytest -q

.PHONY: figures
figures:
	PYTHONPATH=. $(PY) research/wp_c4/figures.py
	PYTHONPATH=. $(PY) research/wp_c6/figures.py
	PYTHONPATH=. $(PY) research/wp_c7/figures.py
	PYTHONPATH=. $(PY) research/wp_c8/figures.py
	$(PY) tools/publication/sync_paper_figures.py

.PHONY: clean
clean:
	rm -rf $(BUILD)
	find . -name '__pycache__' -not -path './.venv/*' -not -path './.git/*' -prune -exec rm -rf {} +
	find . -name '*.pyc' -not -path './.venv/*' -delete

# ---------------------------------------------------------------------------
# v1.1 simulation qualification and deployment (S1-S10)
#
# `qualification` is the gate: it launches the REAL simulator, runs the REAL
# adapter, and checks every channel's semantics against the committed
# contract. It arms and flies the vehicle first -- an informativeness probe on
# a stationary airframe measures nothing.
# ---------------------------------------------------------------------------
AP_ROOT  ?= /home/user/ardupilot/ardupilot
PX4_ROOT ?= /home/user/px4

.PHONY: sim-ardupilot
sim-ardupilot:
	CSIA_AP_ROOT=$(AP_ROOT) $(PY) tools/simulation/qualify_platform.py \
	  --platform ardupilot --seconds 45

.PHONY: sim-px4
sim-px4:
	CSIA_PX4_ROOT=$(PX4_ROOT) $(PY) tools/simulation/qualify_platform.py \
	  --platform px4 --seconds 30

# Gate 2: run this ON THE TARGET companion computer. Needs no autopilot, no
# simulator and no network -- only a recorded shadow flight log. It reports
# the R13 verdict AND whether the environment is fit to certify one; a PASS
# under an unconstrained scheduler is a measurement, not a deadline result.
#   make gate2-timing LOG=logs/shadow-sitl-ardupilot/....jsonl
.PHONY: gate2-timing
gate2-timing:
	@test -n "$(LOG)" || (echo "usage: make gate2-timing LOG=<flight.jsonl>"; exit 2)
	chrt -f 80 taskset -c 2 $(PY) tools/deploy/gate2_timing.py "$(LOG)" \
	  || $(PY) tools/deploy/gate2_timing.py "$(LOG)"

# Both platforms. Reports each; fails if either fails.
.PHONY: qualification
qualification:
	@rc=0; \
	for p in ardupilot px4; do \
	  echo ""; echo "############ qualification: $$p"; \
	  $(MAKE) --no-print-directory sim-$$p || rc=1; \
	done; \
	echo ""; \
	if [ $$rc -ne 0 ]; then echo "QUALIFICATION: FAIL"; else echo "QUALIFICATION: PASS"; fi; \
	exit $$rc

.PHONY: campaign
campaign:
	CSIA_AP_ROOT=$(AP_ROOT) $(PY) tools/simulation/run_campaign.py \
	  --config configs/simulation/scenarios_ardupilot.yaml \
	  --profile $(or $(PROFILE),FIELD_DERIVED_NOISE)

# Shadow deployment. CSIA_MODE defaults to SHADOW; there is no mode with
# command authority, and an unrecognised value is a hard error.
.PHONY: shadow-run
shadow-run:
	CSIA_MODE=$(or $(CSIA_MODE),SHADOW) $(PY) -m csia.deploy.cli \
	  --config $(or $(VEHICLE),configs/vehicle/example_quad.yaml) \
	  --log-dir $(or $(LOGDIR),logs/shadow)

.PHONY: replay
replay:
	$(PY) tools/simulation/replay_flight_log.py $(LOG)

# Fast lane: everything that does NOT need a simulator. This is what runs on
# every commit; the SITL-dependent qualification is a separate lane.
.PHONY: test-fast
test-fast:
	$(PY) -m pytest -q -m "not sitl"

.PHONY: test-v11
test-v11:
	$(PY) -m pytest -q tests/test_channel_semantics.py tests/test_adapters.py \
	  tests/test_shadow_mode.py tests/test_simulation_contract.py \
	  tests/test_flight_log.py tests/test_v1_frozen.py

# ---------------------------------------------------------------------------
# Mechanism campaigns and their analyses. Every other workflow in this file has
# a target; these were shell-only, which is how the mag_emi runner came to be
# overwritten without anything noticing.
#
# The campaign grids are module constants, NOT command-line options: a grid you
# can widen from the shell is not a preregistered grid. These targets run the
# campaigns exactly as preregistered and nothing else.
# ---------------------------------------------------------------------------

# Mechanism B, authoritative: fix-preserving GNSS position glitch, T* = 0.75.
# Preregistration research/v1_1/CURRENT_STACK_REPLICATION.md (blob 0e18611).
.PHONY: mechanism-b
mechanism-b:
	$(PY) tools/deploy/mechanism_b_campaign.py --platform ardupilot

.PHONY: mechanism-b-report
mechanism-b-report:
	$(PY) tools/simulation/current_stack_replication.py --platform ardupilot

# POST-HOC, not preregistered. Reads existing traces only; runs no flights.
.PHONY: mechanism-b-s0-sensitivity
mechanism-b-s0-sensitivity:
	$(PY) tools/simulation/s0_sensitivity_posthoc.py

# The mag_emi PROBE (T* = 0.60) -- a separate experiment, not Mechanism B.
.PHONY: mechanism-b-mag-emi
mechanism-b-mag-emi:
	$(PY) tools/deploy/mechanism_b_mag_emi_campaign.py --platform ardupilot
	$(PY) tools/deploy/mechanism_b_mag_emi_campaign.py --platform px4

.PHONY: mechanism-b-mag-emi-report
mechanism-b-mag-emi-report:
	$(PY) tools/simulation/mag_emi_probe_report.py

# Publication-package guards that need no simulator.
.PHONY: paper-audit
paper-audit:
	$(PY) tools/simulation/paper_scalar_audit.py
	$(PY) -m pytest -q tests/test_markdown_paths.py

# Cross-checks over the COMMITTED artifacts: which evidence was actually
# available, whether every injection reached the vehicle, whether a campaign's
# trials are mutually comparable, and why each relation was live or dark.
# Reads artifacts and frozen source; launches no simulator and rewrites no
# result.
#
# THESE TARGETS ARE EXPECTED TO EXIT NON-ZERO TODAY, and that is the point:
# evidence-coverage reports four PX4 relations STARVED_BY_TRANSPORT
# (altitude_baro, power_thrust, temp_bias_drift, vibration_prop_freq), whose
# single shared cause is measured and scoped in
# research/v1_1/PX4_LINK_RATE_FINDING.md and deliberately not yet fixed. That
# verdict means the passive shadow LINK under-delivered against the freshness
# contract -- not that PX4 lacks the channels, and not that the declared rate
# is wrong. Do NOT append `|| true` to make the lane green:
# a guard that cannot report is not a guard. The same defect class is already
# guarded for pytest steps in the workflows by
# tests/test_ci_env.py::test_no_pytest_invocation_swallows_its_own_result;
# nothing enforces it here, so it is a convention these targets rely on.
#
# Each is its own target so a failure names itself instead of hiding behind
# whichever line ran first. `make -k evidence-audit` runs them all.
.PHONY: evidence-availability injection-effectiveness provenance-backfill \
        evidence-coverage mechanism-a-confound qualification-audit \
        evidence-audit
evidence-availability:
	$(PY) tools/simulation/evidence_availability.py

injection-effectiveness:
	$(PY) tools/simulation/injection_effectiveness.py

provenance-backfill:
	$(PY) tools/publication/provenance_backfill.py

evidence-coverage:
	$(PY) tools/simulation/evidence_coverage_ledger.py

# Needs evidence-coverage to have run: it reads the ledger's verdicts to tell
# harness starvation apart from structural absence and operating-regime gating.
mechanism-a-confound:
	$(PY) tools/simulation/mechanism_a_link_confound_audit.py

# Resolves every current-stack scalar from the artifact that produced it, at
# run time. Runs last because it reads the outputs of the targets above.
qualification-audit:
	$(PY) tools/publication/evidence_qualification_audit.py

evidence-audit: evidence-availability injection-effectiveness \
                provenance-backfill evidence-coverage mechanism-a-confound \
                qualification-audit

# Resolves the PX4 rate conflict from scratch: three arms, both links bound in
# the same boot. NEEDS THE SIMULATOR and takes ~4 min (3 x 40 s plus boots).
# Rewrites research/v1_1/results/PX4_LINK_RATE_PROBE.json, which
# tests/test_px4_link_rate.py checks the contract against.
.PHONY: px4-link-rate
px4-link-rate:
	$(PY) tools/simulation/px4_link_rate_probe.py

# Checks refs.bib against Crossref field by field. This is the ONLY route to
# clearing a provenance marker: the marker means "not checked against the
# publisher", so only a publisher comparison retires it. Needs network; exits
# 2 rather than reporting a pass when Crossref is unreachable.
.PHONY: bib-verify
bib-verify:
	$(PY) tools/publication/verify_bibliography.py \
	  --json research/v1_1/results/bibliography_verification.json

# Intermittent invalidity masking. NO SIMULATOR: the source audit is static,
# and every measurement is a deterministic replay of a recording already in the
# tree (research/maer/.../NON_SCORED_TEST_FIXTURE_M1.json.gz). About a minute,
# dominated by the 26-run boundary sweep.
.PHONY: invalidity-trace
invalidity-trace:
	$(PY) research/invalidity_masking/source_to_gate_trace.py

.PHONY: invalidity-masking
invalidity-masking: invalidity-trace
	$(PY) research/invalidity_masking/validity_semantics_matrix.py
	$(PY) research/invalidity_masking/invalid_message_gate_trace.py
	$(PY) research/invalidity_masking/boundary_sweep.py

# Dual-channel admissibility: does operational admissibility (A) need to be a
# different state variable from diagnostic evidential admissibility (D)?
# NO SIMULATOR. Every measurement is a deterministic replay of recordings
# already in the tree, or a closed-form derivation. About four minutes.
.PHONY: dual-reproduce
dual-reproduce:
	$(PY) research/dual_admissibility/reproduce_s0_s1.py

.PHONY: dual-admissibility
dual-admissibility: dual-reproduce
	$(PY) research/dual_admissibility/source_validity_role_audit.py
	$(PY) research/dual_admissibility/three_arm_experiment.py
	$(PY) research/dual_admissibility/pattern_and_transport.py
	$(PY) research/dual_admissibility/formal_analysis.py
	$(PY) research/dual_admissibility/semantic_search.py
	$(PY) research/dual_admissibility/cross_sensor_audit.py

# Dual-admissibility CONFIRMATORY STAGE: preregistration preparation only.
# This target runs NO confirmatory trial and captures NO confirmatory trace --
# item 32 is a hard stop pending independent review. Everything it runs is a
# source audit, an instrument self-check, or a design-feasibility measurement
# on already-contaminated development data.
.PHONY: dual-confirmatory-prep
dual-confirmatory-prep:
	$(PY) research/dual_admissibility_confirmatory/trace_manifest.py
	$(PY) research/dual_admissibility_confirmatory/tool_self_audit.py
	$(PY) research/dual_admissibility_confirmatory/design_feasibility.py

# Stage 2.1 kill test. Captures SIX held-out SITL traces (three matched pairs)
# and scores the frozen C0_STRONG and status-only arms against them. This is
# the 3-pair test item 4 asks for -- it is NOT the 10+10 confirmatory
# campaign, which remains blocked.
.PHONY: dual-heldout-capture
dual-heldout-capture:
	$(PY) research/dual_admissibility_confirmatory/heldout_capture.py

.PHONY: dual-kill-test
dual-kill-test:
	$(PY) research/dual_admissibility_confirmatory/live_vs_inherited.py
	$(PY) research/dual_admissibility_confirmatory/kill_test.py
	$(PY) research/dual_admissibility_confirmatory/cross_path_checker.py

# ---------------------------------------------------------------------------
# Evidence-semantic equivalence (research/evidence_semantics). Stage 0:
# prior-art red team, formalization, multi-path feasibility. Verdict is
# IMPLEMENTATION_DEFECTS_ONLY -- see CHATGPT_REVIEW_REPORT.md before reading
# any number out of these artifacts.
#
# Run `evidence-reproduce` FIRST. It is item 12's hard stop: if 79/120 and the
# shortest 'I' witness do not reproduce exactly it exits 2 and nothing
# downstream is valid.
.PHONY: evidence-reproduce
evidence-reproduce:
	$(PY) research/evidence_semantics/reproduce_prior_results.py

# The full bounded check: 3 families x 3 ingest paths x 120 words. ~190 s.
# Deterministic -- re-running produces byte-identical artifacts.
.PHONY: evidence-check
evidence-check:
	$(PY) research/evidence_semantics/contract_checker.py

# Four deliberately faulty NON-SCORED fixtures the checker must catch. Tool
# validation, not a scientific result.
.PHONY: evidence-self-audit
evidence-self-audit:
	$(PY) research/evidence_semantics/self_audit.py

# Source audit over every sensor family; every citation regex-pinned and the
# published line re-read against the match.
.PHONY: evidence-sensors
evidence-sensors:
	$(PY) research/evidence_semantics/cross_sensor_audit.py

# Cross-platform: the same contracts against PX4Adapter, plus the committed
# 9.6 MB real ULog.
.PHONY: evidence-px4
evidence-px4:
	$(PY) research/evidence_semantics/px4_probe.py

.PHONY: evidence-semantics
evidence-semantics: evidence-reproduce evidence-check evidence-self-audit \
                    evidence-sensors evidence-px4

# ---------------------------------------------------------------------------
# AI-assisted evidence contract synthesis (research/ai_contract_synthesis).
# Verdict is HEURISTICS_SUFFICIENT: the MAVLink schema already carries the
# sentinel semantics in a machine-readable `invalid=` attribute, and a ~20-line
# lookup beats every AI condition on the frozen pilot. Read
# CHATGPT_REVIEW_REPORT.md section 31 before quoting any number.
.PHONY: ai-contract-freeze-check
ai-contract-freeze-check:
	$(PY) research/ai_contract_synthesis/freeze.py --check

.PHONY: ai-contract-baselines
ai-contract-baselines:
	$(PY) research/ai_contract_synthesis/baselines/b0_heuristic.py

.PHONY: ai-contract-ground
ai-contract-ground:
	$(PY) research/ai_contract_synthesis/verification/grounding.py

# Six deliberately wrong contracts against six NON-SCORED fixtures. Tool
# validation, not a scientific result, and the rate is fitted.
.PHONY: ai-contract-containment
ai-contract-containment:
	$(PY) research/ai_contract_synthesis/verification/containment.py

.PHONY: ai-contract-score
ai-contract-score:
	$(PY) research/ai_contract_synthesis/score.py

.PHONY: ai-contract-defects
ai-contract-defects:
	$(PY) research/ai_contract_synthesis/defect_discovery.py

.PHONY: ai-contract-synthesis
ai-contract-synthesis: ai-contract-baselines ai-contract-ground \
                       ai-contract-containment ai-contract-score \
                       ai-contract-defects

# ---------------------------------------------------------------------------
# Semantic-authority conflict (research/semantic_authority_conflict). Verdict
# is ENGINEERING_INCONSISTENCY_ONLY: the specification and the producer never
# disagree, every conflict is consumer-side, and none reaches the failsafe
# action. Read CHATGPT_REVIEW_REPORT.md before quoting any number.
.PHONY: authority-table
authority-table:
	$(PY) research/semantic_authority_conflict/authorities.py

.PHONY: authority-conflicts
authority-conflicts:
	$(PY) research/semantic_authority_conflict/conflicts.py

# F(C_a, w) at six levels, with a null control at every level. ~60 s.
.PHONY: authority-sensitivity
authority-sensitivity:
	$(PY) research/semantic_authority_conflict/decision_sensitivity.py

.PHONY: authority-baselines
authority-baselines:
	$(PY) research/semantic_authority_conflict/baselines.py

.PHONY: semantic-authority
semantic-authority: authority-table authority-sensitivity \
                    authority-conflicts authority-baselines

# ---------------------------------------------------------------------------
# Stage R0.2 frontier selection. There is nothing to run: the stage produced
# documents only (item 36 forbids implementation). This target checks the
# honesty guards over those documents.
.PHONY: frontier-check
frontier-check:
	$(PY) -m pytest tests/test_frontier_selection.py -q

# Candidate B Stage 0A: prior-art closure and formal problem freeze. No code
# to run -- documents only (item 34). This checks the honesty guards.
.PHONY: evidence-independence-check
evidence-independence-check:
	$(PY) -m pytest tests/test_effective_evidence_independence.py -q

# v1.1 Phase 1: canonical ingestion. `v1-1-defects` re-runs the defect
# reproduction (writes KNOWN_DEFECTS_POST_FIX.json); `v1-1-ingest-check` runs
# the Gate B/C regression tests.
.PHONY: v1-1-defects
v1-1-defects:
	$(PY) engineering/v1_1/reproduce_defects.py --out post

.PHONY: v1-1-ingest-check
v1-1-ingest-check:
	$(PY) -m pytest tests/test_v1_1_canonical_ingest.py -q

# v1.1 Phase 2: support-aware diagnosis. Read-only over the FROZEN core.
.PHONY: v1-1-support
v1-1-support:
	$(PY) engineering/v1_1/support/run_phase2.py

.PHONY: v1-1-support-check
v1-1-support-check:
	$(PY) -m pytest tests/test_v1_1_support.py -q

# v1.1 Phase 3A: GRAPH vs FLAT ablation. Read-only over the FROZEN engine.
.PHONY: v1-1-ablation
v1-1-ablation:
	$(PY) engineering/v1_1/ablation/run_phase3a.py

.PHONY: v1-1-ablation-check
v1-1-ablation-check:
	$(PY) -m pytest tests/test_v1_1_graph_flat.py -q

# v1.1 Phase 3B: section-23 gate on the frozen B4 CUSUM constants.
.PHONY: v1-1-b4-verify
v1-1-b4-verify:
	$(PY) engineering/v1_1/ablation/b4_verify.py

# v1.1 Phase 3B: five-arm architecture selection (T0-T4).
.PHONY: v1-1-phase3b
v1-1-phase3b:
	$(PY) engineering/v1_1/ablation/run_phase3b.py

.PHONY: v1-1-phase3b-check
v1-1-phase3b-check:
	$(PY) -m pytest tests/test_v1_1_phase3b.py -q

# ---------------------------------------------------------------- Phase 4
# v1.1 Phase 4A: trust-mode regression (STOP gate) + architecture freeze.
.PHONY: v1-1-p4a
v1-1-p4a:
	$(PY) engineering/v1_1/phase4/run_p4a.py

.PHONY: v1-1-p4a-check
v1-1-p4a-check:
	$(PY) -m pytest tests/test_v1_1_trust_mode.py -q

# v1.1 Phase 4B: function eligibility over the nine mechanisms.
.PHONY: v1-1-p4b
v1-1-p4b:
	$(PY) engineering/v1_1/phase4/run_p4b.py

.PHONY: v1-1-p4b-check
v1-1-p4b-check:
	$(PY) -m pytest tests/test_v1_1_eligibility.py -q
