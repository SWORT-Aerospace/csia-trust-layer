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
    # The daily report's subject is that this file never existed: the CI step
    # named "determinism" ran it behind `|| true` and was green for years.
    # Citing it is the point of the paragraph.
    "tests/test_determinism.py":
        "documented as never having existed; the citation IS the finding",
    # A specification for a measurement tool that is explicitly still to be
    # written -- the spec itself says "Write ... against this spec".
    "research/wp_c5/measure_q_gvalid.py":
        "forward reference; the spec instructs that it be written",
    # Shorthand for the range wp_c1 ... wp_c8, not a path.
    "research/wp_c1..c8":
        "range shorthand in prose, not a filesystem path",
    # Directory placeholders in planning documents.
    "docs/adr/": "planned directory named in an organisational blueprint",
    "docs/external/reading/":
        "planned directory named in a research request document",
}


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
