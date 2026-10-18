"""Guards for publication/system_paper_i/provenance_assessment/.

The assessment makes three kinds of statement about campaigns A1, A2 and P1
and the Mechanism B GNSS-glitch campaign: counts read from the committed trial
manifests, reconstructions from git objects, and a classification of each
claim as verified, recorded or unrecoverable. These tests hold the counts to
the manifests directly, hold the whole of assessment.json to a fresh rebuild
from git, and keep the README inside the repository's wording rules.
"""

import glob
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "publication" / "system_paper_i" / "provenance_assessment"
CAMPAIGNS = {
    "A1": ("campaigns/physical_validation/mechanism_a_repeat_ap", "MECHA-*.json", 39),
    "A2": ("campaigns/physical_validation/mechanism_a_trust_completion_a2", "MECHA2-*.json", 36),
    "P1": ("campaigns/physical_validation/mechanism_a_px4_repeat_p1", "MECHP1-*.json", 39),
}
#: commits the rebuild reads; a clone without them cannot rebuild, and says so
NEEDED = ("33d3d61", "bfc16f5", "ceeaf4a", "ba9a8f4", "c5ea4d2", "4c213d6",
          "ec5acd189295dab9259d4989657d42184d6142a3", "9f39474", "670aa7a", "b8dcdc8")
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")


@pytest.fixture(scope="module")
def assessment():
    return json.loads((PKG / "assessment.json").read_text(encoding="utf-8"))


def test_the_dirty_counts_are_the_manifests_own(assessment):
    total = 0
    for key, (base, pat, want) in CAMPAIGNS.items():
        flags = [json.loads(Path(f).read_text(encoding="utf-8"))["provenance"]["dirty"]
                 for f in glob.glob(str(ROOT / base / pat))]
        assert len(flags) == 40 and sum(flags) == want
        assert assessment["dirty"][key]["recorded_dirty"] == want
        total += sum(flags)
    assert total == 114


def test_the_reconstruction_explains_every_flag_and_nothing_else(assessment):
    for key in CAMPAIGNS:
        d = assessment["dirty"][key]
        assert d["predicted_equals_recorded"] == 40
        assert d["dirty_without_any_runner_output_absent"] == []
        assert d["clean_with_runner_output_absent"] == []
        assert d["manifest_sha256_recomputes"] == 40
        assert d["adjudication_reproduced_by_committed_adjudicator"] == 40
        assert d["recorded_frozen_core_diff_empty"] == 40


def test_frozen_core_identity_and_the_onset_fix_scope(assessment):
    f = assessment["frozen_core"]
    assert f["recorded_tag_commit"] == "ec5acd189295dab9259d4989657d42184d6142a3"
    assert f["all_head_checks_pass"] and f["heads_checked"] == 15 and len(f["clean_instants"]) == 6
    o = assessment["injection_onset_fix"]
    assert o["every_flight_before_fix"] and o["analysis_onset_equals_recorded_write_in_every_faulted_trial"]
    assert o["a1_a2_p1"]["driver_blob_is_post_fix"]
    assert o["ramp_20s_0_full_trace"]["at_commanded_onset"]["gps_trust"] == 0.954125


def test_the_assessment_rebuilds_from_git():
    missing = [c for c in NEEDED
               if subprocess.run(["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT).returncode]
    if missing:
        pytest.skip(f"history not present in this clone: {missing}; the rebuild needs full history")
    spec = importlib.util.spec_from_file_location("build_assessment", PKG / "build_assessment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--check"]) == 0


def test_the_readme_classifies_and_keeps_the_wording_rules():
    text = (PKG / "README.md").read_text(encoding="utf-8")
    assert len(text) > 1500 and "%" not in text
    low = text.lower()
    assert not re.search(r"\bnovel\b", low)
    for phrase in BANNED:
        assert phrase not in low, phrase
    for label in ("**VERIFIED**", "**RECORDED**", "**UNRECOVERABLE**"):
        assert label in text
    assert "114 of 120" in text and "Do not write \"uncommitted code changes\" for all 114" in text
    assert "not to A1, A2 or P1" in text
