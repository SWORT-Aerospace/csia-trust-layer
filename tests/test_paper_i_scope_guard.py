"""Paper I's scientific scope must not acquire the mission extension.

A scope guard that exists only as prose is a guard nobody runs. These tests
are what make `PAPER_I_SCOPE_GUARD.md` enforceable.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MANUSCRIPT = os.path.join(ROOT, "papers", "csia_systems", "main.tex")
ARTIFACT_MAP = os.path.join(ROOT, "papers", "csia_systems",
                            "PAPER1_ARTIFACT_MAP.yaml")
GUARD = os.path.join(ROOT, "PAPER_I_SCOPE_GUARD.md")

#: Vocabulary that belongs to the mission layer and to nothing in Paper I.
MISSION_VOCABULARY = (
    "capability support certificate",
    "mission product certificate",
    "mission-product assurance",
    "forge-seed",
    "forge seed",
    "disaster corridor",
    "csia_mission",
    "assured mission yield",
    "product coverage",
    "self-occluding reconfiguration",
    "planner gate",
    "XR-1",
    "XR1",
)


def test_the_scope_guard_document_exists_and_names_paper_i_subjects():
    text = open(GUARD, encoding="utf-8").read()
    for subject in ("support / ranking distinction",
                    "current-stack",
                    "negative controls",
                    "Mechanism B"):
        assert subject in text, f"the guard no longer names {subject!r}"
    assert "scientific scope changed | **NO**" in text.replace("  ", " ") \
        or "scientific scope changed" in text


def test_the_manuscript_contains_no_mission_layer_vocabulary():
    if not os.path.exists(MANUSCRIPT):
        pytest.skip("manuscript not present")
    flat = " ".join(open(MANUSCRIPT, encoding="utf-8").read().split()).lower()
    found = [v for v in MISSION_VOCABULARY if v.lower() in flat]
    assert not found, (
        f"Paper I now mentions {found}. The mission extension may appear "
        f"there only as FUTURE WORK, never as a result, and this guard fires "
        f"on the vocabulary rather than trusting the framing. If a future-work "
        f"paragraph is genuinely being added, narrow this list deliberately "
        f"in the same commit and record why.")


def test_the_artifact_map_names_no_mission_artifact():
    if not os.path.exists(ARTIFACT_MAP):
        pytest.skip("artifact map not present")
    raw = open(ARTIFACT_MAP, encoding="utf-8").read()
    for prefix in ("csia_mission/", "research/mission/", "hardware/xr1/"):
        assert prefix not in raw, (
            f"PAPER1_ARTIFACT_MAP.yaml references {prefix}. The mission "
            f"layer consumes E1's semantics; it does not evidence them, and "
            f"an artifact map entry would make it look as though it does.")
    doc = yaml.safe_load(raw)
    assert doc, "the artifact map did not parse"


def test_the_e1_freeze_manifest_is_byte_unchanged():
    proc = subprocess.run(
        ["git", "diff", "--stat", "--",
         "research/physical_validation/E1_FREEZE_MANIFEST.yaml"],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.stdout.strip() == "", (
        "E1_FREEZE_MANIFEST.yaml has been modified. It is immutable by "
        "instruction:\n" + proc.stdout)


def test_the_frozen_core_diff_against_the_tag_is_empty():
    tags = subprocess.run(["git", "tag", "--list", "csia-v1.0-research-final"],
                          cwd=ROOT, capture_output=True, text=True).stdout
    if "csia-v1.0-research-final" not in tags:
        pytest.skip("the freeze tag is local-only and is absent from this "
                    "clone; see the E1 freeze manifest")
    proc = subprocess.run(
        ["git", "diff", "--stat", "csia-v1.0-research-final", "--",
         "csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
         "csia/runtime/failsafe.py", "csia/scenarios.py", "csia/profiles.py"],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.stdout.strip() == "", (
        "THE FROZEN SCIENTIFIC CORE HAS CHANGED:\n" + proc.stdout)


def test_the_e1_claim_table_is_byte_unchanged():
    proc = subprocess.run(
        ["git", "diff", "--stat", "--",
         "research/physical_validation/E1_FINAL_CLAIM_TABLE.csv"],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.stdout.strip() == "", (
        "E1_FINAL_CLAIM_TABLE.csv has been modified:\n" + proc.stdout)


def test_no_mission_module_claims_novelty():
    """Every mission artifact must carry NOVELTY_NOT_ESTABLISHED where it
    makes a claim-shaped statement at all."""
    banned = re.compile(
        r"\b(?:novel|first to|we introduce|our contribution|state of the art)"
        r"\b", re.IGNORECASE)
    offenders = []
    for sub in ("csia_mission",):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, sub)):
            if "__pycache__" in dirpath:
                continue
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                for i, line in enumerate(
                        open(path, encoding="utf-8"), start=1):
                    if banned.search(line) and "NOVELTY_NOT_ESTABLISHED" \
                            not in line and "not novel" not in line.lower():
                        offenders.append(
                            f"{os.path.relpath(path, ROOT)}:{i}: "
                            f"{line.strip()[:90]}")
    assert not offenders, (
        "novelty-claiming language in the mission layer:\n  "
        + "\n  ".join(offenders))


def test_the_novelty_classification_document_classifies_everything():
    path = os.path.join(ROOT, "docs", "mission", "NOVELTY_CLASSIFICATION.md")
    text = open(path, encoding="utf-8").read()
    for idea in ("evidence-preserving reconfiguration",
                 "mission-product assurance",
                 "capability support certificates",
                 "compute-aware product qualification"):
        assert idea in text, f"{idea!r} is no longer classified"
    assert "NOVELTY_NOT_ESTABLISHED" in text
    assert "No manuscript priority claim" in text
