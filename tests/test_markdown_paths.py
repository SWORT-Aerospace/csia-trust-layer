"""Every repository path a Markdown file cites in backticks must exist.

WHY THIS EXISTS. Three separate breakages shipped before anyone noticed, and
all three were invisible to every other check in the repo:

  * `research/v1_1/MECHANISM_B_PREREGISTRATION.md` was renamed to
    `..._MAG_EMI_PREREGISTRATION.md`, leaving the probe document -- and the
    `prereg` field written into freshly generated result JSON -- pointing at a
    file that did not exist. A published result citing its own preregistration
    by a dead path is a provenance defect, not a typo.
  * `research/wp-e1` (hyphen) was cited in twelve documents; the directory is
    `research/wp_e1` (underscore).
  * `research/wp1-formalization` was cited in two; the directory is
    `research/formalization`.

`tests/test_ci_env.py::test_every_test_path_named_in_a_workflow_exists` does
exactly this for workflow files. Markdown is where the publication package
actually points its readers, and it had no equivalent guard.

WHAT IS CHECKED. Only backticked, repository-rooted paths -- `docs/...`,
`tools/...`, `csia/...`, `tests/...`, `research/...`, `papers/...`,
`reports/...`, `scripts/...`. Prose is not scanned, so a sentence mentioning a
directory in passing cannot trip this. A trailing `:123` or `:123-145` source
citation is stripped before the existence check, because `file.py:42` is a line
reference to `file.py`.
"""

import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Backticked paths rooted at a real top-level directory of this repository.
PATH_RE = re.compile(
    r'`((?:docs|tools|csia|tests|research|scripts|papers|reports)'
    r'/[A-Za-z0-9_./+-]+)`')

SKIP_DIRS = {".venv", ".git", "node_modules", "build", "__pycache__"}

# Deliberate references to things that do not exist. Each entry must say WHY,
# because an allowlist without reasons becomes a place to hide real breakage.
ALLOWED_MISSING = {
    # tests/test_determinism.py WAS allowlisted here, as "documented as never
    # having existed". It exists now -- it was written to close exactly that
    # gap -- so the exemption is stale and removed. The staleness test is what
    # caught it, which is the whole reason that test exists.
    # A specification for a measurement tool that is explicitly still to be
    # written -- the spec itself says "Write ... against this spec".
    "research/wp_c5/measure_q_gvalid.py":
        "forward reference; the spec instructs that it be written",
    # Shorthand for the range wp_c1 ... wp_c8, not a path.
    "research/wp_c1..c8":
        "range shorthand in prose, not a filesystem path",
    # A hash-domain separator string, quoted so a reader can reproduce the
    # seed derivation. It is shaped like a path because domain separation
    # conventionally uses slash-delimited namespaces; nothing lives there.
    "csia/consequence_closed_loop_phase3/2026-09-20":
        "seed-derivation domain string in csia_consequence/"
        "phase3_partitions.py, not a filesystem path",
    "csia/actionability_precondition_phase31/2026-09-20":
        "seed-derivation domain string in csia_consequence/"
        "phase31_partitions.py, not a filesystem path",
    "csia/direct_consequence_test_phase32/2026-09-20":
        "seed-derivation domain string in csia_consequence/"
        "phase32_partitions.py, not a filesystem path",
    "csia/detector_performance_phase4/2026-09-20":
        "seed-derivation domain string in csia_consequence/"
        "phase4_partitions.py, not a filesystem path",
    # Directory placeholders in planning documents.
    "docs/adr/": "planned directory named in an organisational blueprint",
    "docs/external/reading/":
        "planned directory named in a research request document",
    # Stage R0.2 selected a candidate and wrote the Stage-0 design and prompt
    # for it. Item 36 of that brief forbids implementing any of it, and
    # tests/test_frontier_selection.py asserts that the first of these does
    # NOT exist -- executing the prompt in the stage that wrote it would be a
    # violation. Both exemptions must be deleted the moment Stage 0 runs.
    "research/evidence_independence/":
        "forward reference; Stage-0 output directory, deliberately not created",
    "tests/test_evidence_independence.py":
        "forward reference; specified by the Stage-0 prompt, not yet written",
    # The public-log exposure study was NOT RUN: review.px4.io and
    # logs.px4.io are denied by this environment's egress policy. The plan
    # names the manifest it would write. Delete this exemption the moment the
    # study runs -- an existing manifest makes it stale, and the staleness
    # test will say so.
    "research/systems-paper/results/public_logs/MANIFEST.csv":
        "forward reference; the study is blocked, see PUBLIC_LOG_STUDY_PLAN.md",
}


def _latex_files():
    r"""LaTeX cites repository paths too, in \code{} and \texttt{}.

    The publication package points readers at source through the manuscript,
    not only through Markdown, and the rename that broke five Markdown
    references could break a manuscript citation just as silently.
    """
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "papers")):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith((".tex", ".bib")):
                yield os.path.join(dirpath, name)


# LaTeX escapes underscores, so `csia\_core.c` in source means `csia_core.c`
# on disk. Without unescaping, every path with an underscore reads as broken.
LATEX_PATH_RE = re.compile(
    r'\\(?:code|texttt|path|url)\{((?:docs|tools|csia|tests|research|scripts'
    r'|papers|reports)/[A-Za-z0-9_./+\\-]+)\}')


def _latex_cited_paths():
    found = {}
    for tex in _latex_files():
        try:
            text = open(tex, encoding="utf-8", errors="ignore").read()
        except OSError:                                # pragma: no cover
            continue
        rel = os.path.relpath(tex, ROOT)
        for ref in set(LATEX_PATH_RE.findall(text)):
            ref = ref.replace("\\_", "_").replace("\\", "")
            base = re.sub(r":[0-9]+(-[0-9]+)?$", "", ref.rstrip(".,;:"))
            found.setdefault(base, set()).add(rel)
    return {k: sorted(v) for k, v in found.items()}


def test_latex_scan_finds_real_citations():
    """Guard the guard: a regex that matches nothing would pass forever."""
    cited = _latex_cited_paths()
    assert cited, ("no repository paths found in any .tex/.bib -- the LaTeX "
                   "regex is broken and this guard is vacuous")


def test_every_repository_path_cited_in_latex_exists():
    cited = _latex_cited_paths()
    broken = {p: f for p, f in cited.items()
              if p not in ALLOWED_MISSING
              and not os.path.exists(os.path.join(ROOT, p))}
    assert not broken, (
        "the manuscript cites repository paths that do not exist:\n"
        + "\n".join(f"  {p}\n      cited by {', '.join(f)}"
                    for p, f in sorted(broken.items())))


def _markdown_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def _cited_paths():
    """{path: [citing files]} for every backticked repo path in Markdown."""
    found = {}
    for md in _markdown_files():
        try:
            text = open(md, encoding="utf-8", errors="ignore").read()
        except OSError:                                # pragma: no cover
            continue
        rel_md = os.path.relpath(md, ROOT)
        for ref in set(PATH_RE.findall(text)):
            # `file.py:42` and `file.py:42-58` are line citations of file.py
            base = re.sub(r":[0-9]+(-[0-9]+)?$", "", ref.rstrip(".,;:"))
            found.setdefault(base, set()).add(rel_md)
    return {k: sorted(v) for k, v in found.items()}


def test_every_repository_path_cited_in_markdown_exists():
    cited = _cited_paths()
    assert cited, "found no repo-path citations at all -- the regex is broken"
    broken = {p: f for p, f in cited.items()
              if p not in ALLOWED_MISSING
              and not os.path.exists(os.path.join(ROOT, p))}
    assert not broken, (
        "Markdown cites repository paths that do not exist:\n"
        + "\n".join(f"  {p}\n      cited by {', '.join(f)}"
                    for p, f in sorted(broken.items()))
        + "\n\nEither fix the path, or add it to ALLOWED_MISSING with a reason.")


def test_the_allowlist_does_not_hide_paths_that_now_exist():
    """An allowlist entry that starts resolving is stale and must be removed.

    Without this the allowlist only ever grows, and a genuinely restored file
    would keep its exemption forever.
    """
    resurrected = [p for p in ALLOWED_MISSING
                   if os.path.exists(os.path.join(ROOT, p))]
    assert not resurrected, (
        "these are allowlisted as missing but now exist -- drop them from "
        f"ALLOWED_MISSING: {resurrected}")


def test_the_guard_would_catch_the_three_breakages_it_was_written_for():
    """The guard must actually fire. A check that cannot fail is not a check."""
    for dead in ("research/v1_1/MECHANISM_B_PREREGISTRATION.md",
                 "research/wp-e1",
                 "research/wp1-formalization"):
        assert not os.path.exists(os.path.join(ROOT, dead)), (
            f"{dead} exists again; this test's premise needs updating")
        assert dead not in ALLOWED_MISSING, (
            f"{dead} must never be allowlisted -- it is a real breakage")
        assert PATH_RE.fullmatch(f"`{dead}`"), (
            f"the regex no longer matches {dead}, so the guard would miss it")


def test_line_number_citations_are_stripped_not_reported_broken():
    """`csia/runtime/online.py:351-355` is a citation of a file that exists."""
    ref = "csia/runtime/online.py:351-355"
    base = re.sub(r":[0-9]+(-[0-9]+)?$", "", ref)
    assert base == "csia/runtime/online.py"
    assert os.path.exists(os.path.join(ROOT, base))


def test_every_allowlist_entry_carries_a_real_reason():
    """An allowlist without reasons becomes a place to hide real breakage.

    Every entry today has a reason string, but nothing enforced it, so the
    next one could arrive bare and the list would quietly become a dumping
    ground for paths someone could not be bothered to fix.
    """
    bare = [p for p, why in ALLOWED_MISSING.items()
            if not isinstance(why, str) or len(why.strip()) < 20]
    assert not bare, (
        "allowlist entries need a reason of at least a short sentence "
        f"explaining why the path is deliberately absent: {bare}")


def test_the_allowlist_stays_small_enough_to_read():
    """A cap, so growth is a decision someone makes rather than a drift."""
    assert len(ALLOWED_MISSING) <= 12, (
        f"{len(ALLOWED_MISSING)} allowlisted missing paths. Past a dozen this "
        "stops being a list of known exceptions and starts being a way to "
        "ignore the guard; fix the paths instead, or raise the cap "
        "deliberately with a reason.")
