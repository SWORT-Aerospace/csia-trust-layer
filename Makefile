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
	@echo "  make release-check   verify built archives against the allowlist"
	@echo "  make check           every guard above"
	@echo "Release:"
	@echo "  make evidence-export rebuild the 16-file Paper I evidence export"
	@echo "  make public-release  pack + sanitize the public archives"
	@echo "Science:"
	@echo "  make test            full pytest suite (includes doc-count guard)"
	@echo "  make figures         regenerate all figures from committed results"

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

# Verifies the committed archives without rebuilding them: every allowlisted
# path still exists and is tracked, and the archive on disk is still clean.
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
