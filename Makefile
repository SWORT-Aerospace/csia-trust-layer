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
.PHONY: check
check:
	@rc=0; \
	for t in artifact-map figure-sync phase-guard manuscript-rules secrets-scan release-check bib-guard; do \
	  echo ""; echo "############ $$t"; \
	  $(MAKE) --no-print-directory $$t || rc=1; \
	done; \
	echo ""; \
	if [ $$rc -ne 0 ]; then echo "PUBLICATION CHECK: FAIL"; else echo "PUBLICATION CHECK: PASS"; fi; \
	exit $$rc

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

# Checks refs.bib against Crossref field by field. This is the ONLY route to
# clearing a provenance marker: the marker means "not checked against the
# publisher", so only a publisher comparison retires it. Needs network; exits
# 2 rather than reporting a pass when Crossref is unreachable.
.PHONY: bib-verify
bib-verify:
	$(PY) tools/publication/verify_bibliography.py \
	  --json research/v1_1/results/bibliography_verification.json
