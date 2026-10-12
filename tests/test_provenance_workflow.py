"""Guards for the provenance create/validate/refresh workflow.

WHAT THESE PROTECT
------------------
`tools/assurance/provenance_workflow.py` is the gate on BUILD_PROVENANCE.json.
A gate that cannot refuse is decoration, so every refusal it is supposed to
make is exercised here against input built to trigger it, and the one
allowance it makes -- the self-referential test node -- is checked for being
exactly one node wide and not widenable from outside.

The decision logic runs for real. What is injected is the slow or
environment-dependent edge: `make check-blocking`, the git queries, and the
record path. Injecting those leaves the branching under test rather than
replacing it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.assurance import provenance_workflow as w   # noqa: E402

NODE = w.SELF_REFERENTIAL_NODE


# ------------------------------------------------------------------ fixtures

def _suite_file(tmp_path, exit_code, failures=(), dots=200):
    """A recorded pytest run, in the shape the workflow reads."""
    lines = ["." * 72 + " [ 50%]", "." * (dots - 72) + " [100%]"]
    for f in failures:
        lines.append(f"FAILED {f}")
    lines.append(f"PYTEST_EXIT={exit_code}")
    p = tmp_path / "suite.txt"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def _record(tmp_path, commit):
    p = tmp_path / "BUILD_PROVENANCE.json"
    p.write_text(json.dumps(
        {"schema": "csia.assurance.build_provenance/1",
         "source": {"commit": commit}}, indent=2) + "\n")
    return p


def _pass():
    return True, {"ok": True, "why": "guards pass (injected)"}


def _fail():
    return False, {"ok": False, "why": "blocking guards did not pass"}


@pytest.fixture
def at(monkeypatch, tmp_path):
    """Point the workflow at a temp record with a controllable git view."""
    def place(state, head="aaa111", recorded=None, tracked=False):
        path = tmp_path / "BUILD_PROVENANCE.json"
        if state != "missing":
            _record(tmp_path, recorded or head)
        monkeypatch.setattr(w, "RECORD", str(path))
        monkeypatch.setattr(w, "_tracked_at_head", lambda rel: tracked)
        monkeypatch.setattr(w, "_git", lambda *a, **k: (
            head if a[:1] == ("rev-parse",) else
            f"{head} bbb222 ccc333" if a[:1] == ("rev-list",) else ""))
        return path
    return place


# ------------------------------------------------------------------ validate

def test_validate_classifies_a_fresh_record_as_valid(at):
    at("present", head="aaa111", recorded="aaa111")
    state, detail = w.classify(w.RECORD)
    assert state == w.VALID, detail
    assert w.EXIT[state] == 0


def test_validate_classifies_an_out_of_window_record_as_stale(at):
    at("present", head="aaa111", recorded="zzz999")
    state, detail = w.classify(w.RECORD)
    assert state == w.STALE
    assert "not HEAD" in detail["why"]
    assert w.EXIT[state] != 0


def test_validate_classifies_a_never_created_record_as_absent(at):
    at("missing", tracked=False)
    state, _ = w.classify(w.RECORD)
    assert state == w.ABSENT


def test_a_record_deleted_from_the_tree_is_not_mistaken_for_a_first_write(at):
    """Removing a stale record must not become a route to a clean creation."""
    at("missing", tracked=True)
    state, detail = w.classify(w.RECORD)
    assert state == w.DELETED
    assert "DELETION, not a first write" in detail["why"]


def test_validate_writes_nothing(at, tmp_path):
    path = at("present", head="aaa111", recorded="zzz999")
    before = path.read_bytes()
    w.cmd_validate(None)
    assert path.read_bytes() == before, "validate must be read-only"


# ------------------------------------------------- 1. first creation, no record

def test_creation_from_no_record_succeeds_on_a_complete_evidence_set(
        at, tmp_path, monkeypatch):
    path = at("missing", tracked=False)
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record",
                        lambda supersedes=None: path.write_text(
                            json.dumps({"source": {"commit": "aaa111"},
                                        "supersedes": supersedes})))
    monkeypatch.setattr(w, "_reverify_or_rollback", lambda prev: True)

    rc = w.cmd_create(_args(_suite_file(tmp_path, 0)))
    assert rc == 0
    assert path.exists()
    assert json.loads(path.read_text())["supersedes"] is None, (
        "a first write supersedes nothing and must not claim to")


def test_creation_is_refused_when_a_record_already_exists(at, tmp_path):
    at("present", head="aaa111", recorded="aaa111")
    rc = w.cmd_create(_args(_suite_file(tmp_path, 0)))
    assert rc == 2, "create must refuse rather than overwrite"


# --------------------------------------------- 2. refresh of a valid record

def test_refresh_of_a_valid_record_succeeds_and_records_what_it_replaced(
        at, tmp_path, monkeypatch):
    path = at("present", head="aaa111", recorded="aaa111")
    seen = {}
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record",
                        lambda supersedes=None: seen.update(s=supersedes))
    monkeypatch.setattr(w, "_reverify_or_rollback", lambda prev: True)

    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0)))
    assert rc == 0
    assert seen["s"]["commit"] == "aaa111"
    assert seen["s"]["sha256"], "the replaced record's digest must be carried"


# --------------------------------------------- 3. a stale record, not silently

def test_a_stale_record_is_never_replaced_silently(at, tmp_path, monkeypatch):
    """Replacement is allowed; doing it without saying so is not."""
    at("present", head="aaa111", recorded="zzz999")
    seen = {}
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record",
                        lambda supersedes=None: seen.update(s=supersedes))
    monkeypatch.setattr(w, "_reverify_or_rollback", lambda prev: True)

    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0, [NODE])))
    assert rc == 0
    s = seen["s"]
    assert s["commit"] == "zzz999", "the superseded commit must be named"
    assert s["sha256"], "the superseded digest must be named"
    assert "window" in s["why"], "the reason must say why it was superseded"


def test_create_will_not_launder_a_stale_record_into_a_creation(at, tmp_path):
    at("present", head="aaa111", recorded="zzz999")
    rc = w.cmd_create(_args(_suite_file(tmp_path, 0, [NODE])))
    assert rc == 2, ("create must refuse a stale record outright; refresh is "
                     "the only path, and it records what it replaced")


def test_refresh_refuses_when_the_record_was_deleted_from_the_tree(
        at, tmp_path):
    at("missing", tracked=True)
    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0)))
    assert rc == 2


# ----------------------------------------------------- 4. a failed suite

def test_a_failed_suite_is_rejected(at, tmp_path, monkeypatch):
    at("present", head="aaa111", recorded="aaa111")
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "_write_record", _must_not_write)
    rc = w.cmd_refresh(_args(_suite_file(
        tmp_path, 1, ["tests/test_something_else.py::test_a_real_failure"])))
    assert rc == 1


def test_a_suite_with_no_recorded_exit_code_is_rejected(tmp_path):
    p = tmp_path / "suite.txt"
    p.write_text("." * 72 + " [100%]\n")
    ok, detail = w.suite_evidence(str(p))
    assert not ok and "PYTEST_EXIT" in detail["why"]


def test_a_suite_that_collected_nothing_is_rejected(tmp_path):
    p = tmp_path / "suite.txt"
    p.write_text("PYTEST_EXIT=0\n")
    ok, detail = w.suite_evidence(str(p))
    assert not ok and "no tests" in detail["why"]


def test_a_nonzero_exit_naming_no_test_is_rejected(tmp_path):
    ok, detail = w.suite_evidence(_suite_file(tmp_path, 2))
    assert not ok, "an unexplained nonzero exit is not evidence of a good tree"


def test_the_self_referential_node_alone_is_accepted(tmp_path):
    ok, detail = w.suite_evidence(_suite_file(tmp_path, 1, [NODE]))
    assert ok
    assert detail["unexplained_failures"] == []


# ---------------------------------------------- 5. failed blocking guards

def test_failed_blocking_guards_are_rejected(at, tmp_path, monkeypatch):
    at("present", head="aaa111", recorded="aaa111")
    monkeypatch.setattr(w, "guards_evidence", _fail)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record", _must_not_write)
    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0)))
    assert rc == 1


# ------------------------------------------------ 6. frozen-core mismatch

def test_a_frozen_core_mismatch_is_rejected(at, tmp_path, monkeypatch):
    at("present", head="aaa111", recorded="aaa111")
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence", lambda: (
        False, {"ok": False, "paths_that_differ": ["csia/evidence/gate.py"],
                "why": "frozen core drifted"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record", _must_not_write)
    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0)))
    assert rc == 1


def test_a_manifest_mismatch_is_rejected(at, tmp_path, monkeypatch):
    at("present", head="aaa111", recorded="aaa111")
    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence", lambda: (
        False, {"ok": False, "why": "a manifest did not verify",
                "manifests": {}}))
    monkeypatch.setattr(w, "_write_record", _must_not_write)
    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0)))
    assert rc == 1


def test_an_empty_manifest_does_not_count_as_verified(tmp_path, monkeypatch):
    """A manifest listing nothing verifies vacuously; that must not pass."""
    empty = tmp_path / "SHA256_EMPTY.json"
    empty.write_text(json.dumps({"files": {}}))
    monkeypatch.setattr(w, "REQUIRED_MANIFESTS", (str(empty),))
    monkeypatch.setattr(w, "ROOT", "/")
    ok, detail = w.manifests_evidence()
    assert not ok


# ------------------------------------------------ 7. an attempted bypass

def test_the_write_commands_expose_no_bypass_option():
    """No --force, --allow-stale, --skip-guards or equivalent."""
    import argparse
    parser_opts = set()

    real = argparse.ArgumentParser.add_argument

    def record(self, *a, **k):
        for name in a:
            if isinstance(name, str) and name.startswith("-"):
                parser_opts.add(name)
        return real(self, *a, **k)

    argparse.ArgumentParser.add_argument = record
    try:
        with pytest.raises(SystemExit):
            w.main(["--help"])
    finally:
        argparse.ArgumentParser.add_argument = real

    forbidden = [o for o in parser_opts
                 if any(k in o.lower() for k in
                        ("force", "skip", "allow", "bypass", "override",
                         "no-verify", "ignore", "yes"))]
    assert not forbidden, f"bypass-shaped options exposed: {forbidden}"


def test_the_workflow_reads_no_environment_variable():
    """An env-var override would be a bypass that leaves no trace in a
    command line, so the source must not consult the environment at all."""
    src = open(os.path.join(ROOT, "tools", "assurance",
                            "provenance_workflow.py"), encoding="utf-8").read()
    for pattern in ("os.environ", "getenv", "os.putenv"):
        assert pattern not in src, (
            f"{pattern} appears in the workflow; an environment override is "
            f"a bypass that a reviewer cannot see in the invocation")


def test_the_allowance_is_exactly_one_node_and_cannot_be_widened(tmp_path):
    """Any second failure, or a different single failure, is refused."""
    ok, _ = w.suite_evidence(_suite_file(tmp_path, 1, [NODE]))
    assert ok, "the one self-referential node is the allowance"

    ok, detail = w.suite_evidence(_suite_file(
        tmp_path, 1, [NODE, "tests/test_other.py::test_x"]))
    assert not ok, "a second failure must not ride along with the allowance"
    assert detail["unexplained_failures"] == ["tests/test_other.py::test_x"]

    ok, _ = w.suite_evidence(_suite_file(
        tmp_path, 1, ["tests/test_other.py::test_x"]))
    assert not ok, "the allowance is for one named node, not for any one node"

    assert isinstance(w.SELF_REFERENTIAL_NODE, str), (
        "the allowance must be a single hard-coded node, not a collection "
        "that could grow")


def test_a_rolled_back_write_does_not_leave_the_new_record_behind(
        at, tmp_path, monkeypatch):
    """If the written record still fails its own check, it must not survive."""
    path = at("present", head="aaa111", recorded="zzz999")
    original = path.read_bytes()

    monkeypatch.setattr(w, "guards_evidence", _pass)
    monkeypatch.setattr(w, "frozen_core_evidence",
                        lambda: (True, {"ok": True, "why": "identical"}))
    monkeypatch.setattr(w, "manifests_evidence",
                        lambda: (True, {"ok": True, "why": "verified"}))
    monkeypatch.setattr(w, "_write_record",
                        lambda supersedes=None: path.write_text("{}"))
    monkeypatch.setattr(subprocess, "run", _pytest_always_fails)

    rc = w.cmd_refresh(_args(_suite_file(tmp_path, 0, [NODE])))
    assert rc == 1, "a record that fails its own check must not be accepted"
    assert path.read_bytes() == original, (
        "the previous record must be restored, not left overwritten")


# -------------------------------------------- the window and the test agree

def test_the_commit_window_matches_the_test_that_enforces_it():
    """If they drift, `validate` says fresh while the suite says stale."""
    src = open(os.path.join(ROOT, "tests",
                            "test_post_e1_hardening_round2.py"),
               encoding="utf-8").read()
    assert f"--max-count={w.COMMIT_WINDOW}" in src, (
        f"the workflow uses a {w.COMMIT_WINDOW}-commit window; the test that "
        f"enforces staleness no longer uses the same one")


def test_the_node_the_allowance_names_actually_exists():
    """An allowance for a test that does not exist is an allowance for
    nothing, and would hide the day the real test is renamed."""
    path, name = w.SELF_REFERENTIAL_NODE.split("::")
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    assert f"def {name}(" in src, (
        f"{w.SELF_REFERENTIAL_NODE} names a test that does not exist")


# -------------------------------------------------------------------- helpers

class _args:
    def __init__(self, suite_output):
        self.suite_output = suite_output


def _must_not_write(supersedes=None):
    raise AssertionError("a refused write must not reach the record")


def _pytest_always_fails(*a, **k):
    class R:
        returncode = 1
        stdout = "1 failed"
        stderr = ""
    return R()


# --------------------------------------- the record's own dirty-path list

def test_the_first_dirty_path_is_not_truncated(monkeypatch):
    """`_git` strips the whole porcelain output, which removes the leading
    space of the FIRST line only. A fixed line[3:] then ate its first
    character: " M Makefile" was recorded as "akefile". Only entry one was
    ever wrong, which is exactly why it went unnoticed."""
    from tools.assurance import build_provenance as bp

    porcelain = "M Makefile\n M docs/X.md\n?? tools/new.py"
    monkeypatch.setattr(bp, "_git", lambda *a: (
        porcelain if a[:2] == ("status", "--porcelain") else "deadbeef"))
    monkeypatch.setattr(bp, "_declared", lambda: {})
    monkeypatch.setattr(bp, "_installed", lambda: {})
    monkeypatch.setattr(bp, "_undeclared_imports", lambda: {})
    monkeypatch.setattr(bp, "_frozen_core_digests", lambda: {})

    paths = bp.provenance()["source"]["dirty_paths"]
    assert "Makefile" in paths, f"first path truncated: {paths}"
    assert "akefile" not in paths
    assert paths == ["Makefile", "docs/X.md", "tools/new.py"]

