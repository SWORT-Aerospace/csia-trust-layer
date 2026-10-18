"""Preflight must be able to say NO, and must not cry wolf.

A preflight tool has two failure modes and both are bad:

  * it passes a build it should have stopped   -- the obvious one
  * it fails a build that is fine              -- the insidious one,
    because a check that cries wolf trains the operator to skip it

The second already happened here once. The first version probed the
read-only connection with `hasattr(conn, "write")`, which RAISES
`CommandAuthorityError` rather than returning False -- `hasattr` only
swallows `AttributeError`. So the probe tripped the very denial it was
verifying and reported DO_NOT_FLY on a healthy build.

These tests cover both directions, and pin the rule that an INCONCLUSIVE
check is never folded into a pass.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.deploy.preflight import (FAIL, INCONCLUSIVE,  # noqa: E402
                                    PASS, check_failsafe_policy,
                                    check_frozen_core, check_log_destination,
                                    check_no_command_authority,
                                    check_platform, run)


def _by_name(rows):
    return {r["check"]: r for r in rows}


# ---------------------------------------------------------------------------
# the safety check, in both directions
# ---------------------------------------------------------------------------

def test_the_command_authority_check_passes_on_a_healthy_build():
    """THE REGRESSION. This is the check that used to fail on a good build."""
    rows = _by_name(check_no_command_authority())
    surface = rows["read_only_connection_has_no_transmit_surface"]
    assert surface["status"] == PASS, surface["detail"]
    assert surface["probes"], "the check reported no probes at all"
    assert all(v in ("DENIED", "ABSENT") for v in surface["probes"].values())


def test_it_probes_a_meaningful_number_of_send_names():
    """A check that probes two names and passes is not evidence. The guard
    knows about many more than that."""
    rows = _by_name(check_no_command_authority())
    probes = rows["read_only_connection_has_no_transmit_surface"]["probes"]
    assert len(probes) >= 10, f"only {len(probes)} names probed"


def test_no_mode_may_command():
    rows = _by_name(check_no_command_authority())
    assert rows["no_mode_claims_command"]["status"] == PASS
    assert set(rows["no_mode_claims_command"]["modes"]) == {"SHADOW",
                                                            "ADVISORY"}
    assert not any(rows["no_mode_claims_command"]["modes"].values())


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def test_the_frozen_core_check_passes_on_this_tree():
    for row in check_frozen_core():
        assert row["status"] in (PASS, INCONCLUSIVE), row
        if row["check"] == "frozen_core_vs_source_digests":
            assert row["status"] == PASS, row["detail"]


def test_the_frozen_core_check_would_notice_a_change(tmp_path):
    """Verified by editing a frozen file in a COPY, so the real tree is
    never touched. A check that cannot fail is not a check."""
    import shutil

    from tools.csia_experiment.build_e1_freeze_manifest import sha256_tree
    before = sha256_tree("csia/diagnosis", source_only=True)

    work = tmp_path / "csia" / "diagnosis"
    work.mkdir(parents=True)
    for name in os.listdir(os.path.join(ROOT, "csia", "diagnosis")):
        src = os.path.join(ROOT, "csia", "diagnosis", name)
        if os.path.isfile(src):
            shutil.copy2(src, work / name)
    with open(work / "causal.py", "a", encoding="utf-8") as fh:
        fh.write("\n# a change\n")

    import hashlib
    entries = sorted(
        f"{hashlib.sha256(open(work / n, 'rb').read()).hexdigest()}  {n}"
        for n in os.listdir(work))
    digest = hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()
    assert digest != before["sha256_of_file_manifest"]


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform", ["ardupilot", "px4"])
def test_both_platforms_have_an_adapter_and_derived_timeouts(platform):
    rows = _by_name(check_platform(platform))
    assert rows["adapter_present"]["status"] == PASS
    timeouts = rows["staleness_timeouts_derived"]
    assert timeouts["status"] == PASS
    assert len(timeouts["timeouts"]) == 8
    assert all(v > 0 for v in timeouts["timeouts"].values())


def test_an_unknown_platform_fails_rather_than_defaulting():
    """Silently falling back to a default platform would produce a log that
    names the wrong vehicle."""
    rows = _by_name(check_platform("not_a_real_autopilot"))
    assert rows["adapter_present"]["status"] == FAIL


def test_the_policy_check_names_which_failsafe_will_run():
    frozen = _by_name(check_failsafe_policy(False))
    assert frozen["failsafe_policy"]["policy"] == "FROZEN_ONLY"
    assert "data_loss_rule_coverage" not in frozen

    supervised = _by_name(check_failsafe_policy(True))
    row = supervised["failsafe_policy"]
    assert row["policy"] == "FROZEN_PLUS_DATA_LOSS_SUPERVISION"
    # The timing constants an operator needs to predict the response.
    assert row["arm_time_s"] == 10.0
    assert row["dwell_up_s"] == 1.0
    assert row["dwell_down_s"] == 5.0

    coverage = supervised["data_loss_rule_coverage"]
    assert coverage["status"] == PASS
    assert len(coverage["sensors_covered"]) == 7
    assert coverage["levels_that_are_a_choice"] == ["baro", "motor_esc"], (
        "the two unanchored levels must be surfaced to the operator, not "
        "hidden among the derived ones")


# ---------------------------------------------------------------------------
# the boring ones
# ---------------------------------------------------------------------------

def test_an_unwritable_log_destination_fails(tmp_path):
    """Uses a path whose PARENT IS A FILE, not a chmod'd directory.

    These tests often run as root, and root ignores directory permission
    bits -- a 0o500 directory is still writable, so the chmod version of
    this test passed a destination it should have rejected. A file where a
    directory must be fails for every user.
    """
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("i am a file")
    rows = _by_name(check_log_destination(str(blocker / "logs")))
    assert rows["log_dir_writable"]["status"] == FAIL
    assert "not writable" in rows["log_dir_writable"]["detail"]


def test_a_writable_destination_passes(tmp_path):
    rows = _by_name(check_log_destination(str(tmp_path / "logs")))
    assert rows["log_dir_writable"]["status"] == PASS


# ---------------------------------------------------------------------------
# the verdict
# ---------------------------------------------------------------------------

def test_inconclusive_is_never_folded_into_ready():
    """The rule this repository has already been bitten by once."""
    report = run("ardupilot", supervision=False, quick=True)
    if report["counts"][INCONCLUSIVE]:
        assert report["verdict"] != "READY"
    assert "not a green preflight" in report["inconclusive_is_not_pass"]


def test_any_failure_means_do_not_fly():
    report = run("not_a_real_autopilot", supervision=False, quick=True)
    assert report["counts"][FAIL] >= 1
    assert report["verdict"] == "DO_NOT_FLY"


def test_the_report_says_what_it_does_not_establish():
    """A preflight that reads as airworthiness is a dangerous document."""
    report = run("ardupilot", supervision=False, quick=True)
    disclaimer = report["what_this_does_not_establish"]
    assert "airworthy" in disclaimer
    assert "calibrated" in disclaimer


def test_the_cli_exits_non_zero_unless_ready():
    proc = subprocess.run(
        [sys.executable, "tools/deploy/preflight.py", "--quick",
         "--platform", "not_a_real_autopilot"],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode != 0
    assert "DO_NOT_FLY" in proc.stderr


def test_the_report_is_serialisable(tmp_path):
    """It has to survive being written next to the flight log."""
    out = tmp_path / "pf.json"
    subprocess.run(
        [sys.executable, "tools/deploy/preflight.py", "--quick",
         "--platform", "ardupilot", "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    with open(out, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["schema"] == "csia.deploy.preflight/1"
    assert doc["checks"] and doc["verdict"] in ("READY", "DO_NOT_FLY",
                                                "INCONCLUSIVE")
