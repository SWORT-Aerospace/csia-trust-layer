"""Guards for publication/evidence_v2/.

Every figure, table and derived data file must carry a complete stamp whose
hash matches the file, and the set must match the committed MANIFEST.sha256
(what `make evidence-v2` regenerates bit-for-bit). The report must keep the
repository's wording rules, keep its blocked items blocked, and not present
the analysis-only trust crossing as detection.
"""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "publication" / "evidence_v2"
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_output_is_stamped_and_matches_the_manifest(capsys):
    check = _load("ev2_check_stamps", PKG / "check_stamps.py")
    assert check.main([]) == 0, capsys.readouterr().out


def test_every_stamp_names_a_commit_a_script_and_its_inputs():
    stamps = sorted(PKG.glob("*/*.stamp.json"))
    assert len(stamps) >= 9
    for p in stamps:
        s = json.loads(p.read_text(encoding="utf-8"))
        assert re.fullmatch(r"[0-9a-f]{40}", s["git_commit"]), p
        assert s["run_timestamp_utc"].endswith("Z"), p
        assert (ROOT / s["script"]).is_file(), p
        assert s["inputs"] or s["configs"], p


def test_the_checkpoints_reproduce():
    d3 = json.loads((PKG / "data" / "d3_mc_runs.json").read_text(encoding="utf-8"))
    assert d3["checkpoint_vs_campaigns_monte_carlo_json"] == "IDENTICAL"
    d2 = json.loads((PKG / "tables" / "d2_alert_episode_rate_checkpoint.csv.stamp.json").read_text(encoding="utf-8"))
    assert "checkpoint REPRODUCED" in d2["notes"]


def test_the_report_keeps_the_wording_rules_and_its_blocked_items():
    text = (PKG / "EVIDENCE_V2_REPORT.md").read_text(encoding="utf-8")
    assert len(text) > 1500 and "%" not in text
    low = text.lower()
    assert not re.search(r"\bnovel\b", low)
    for phrase in BANNED:
        assert phrase not in low, phrase
    for item in ("D1", "D7"):
        assert re.search(rf"\|\s*{item}\b[^\n]*\bBLOCKED\b", text), item
    assert "analysis only" in low and "detection latency" in low
    assert "B2" in text and "interceptor_seeker" in text
