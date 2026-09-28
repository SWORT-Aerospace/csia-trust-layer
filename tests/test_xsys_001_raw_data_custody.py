"""XSYS-001 raw-data custody record agrees with the sealed campaign record.

research/xsys_001_raw_data_custody/DURABLE_STORAGE_RECORD.json says where the
durable copy of the raw data lives. This checks that every flight's raw and
xz hashes in it equal those of the sealed CAMPAIGN_COMPLETION.json, and that
the record binds the frozen result manifest. Standard library only.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "research" / "xsys_001_raw_data_custody" / "DURABLE_STORAGE_RECORD.json"
CAMP = ROOT / "research" / "xsys_001_confirmatory_campaign"


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_custody_matches_the_sealed_completion_record():
    rec = json.loads(REC.read_text())
    comp = json.loads((CAMP / "CAMPAIGN_COMPLETION.json").read_text())
    assert rec["status"] == "DURABLE_STORAGE_COMPLETE"
    assert rec["store"]["remote_head_equals_commit"] is True
    by_id = {f["flight_id"]: f for f in comp["flights"]}
    assert len(rec["flights"]) == len(by_id) == 66
    for f in rec["flights"]:
        c = by_id[f["flight_id"]]
        assert f["raw_ulog_sha256"] == c["ulog_sha256"]
        assert f["xz_sha256"] == c["ulog_xz_sha256"]
        assert f["xz_sha256_on_branch_matches"] is True


def test_custody_binds_the_frozen_records():
    b = json.loads(REC.read_text())["binds"]
    assert b["CAMPAIGN_COMPLETION.json"] == _sha(CAMP / "CAMPAIGN_COMPLETION.json")
    assert b["RAW_DATA_MANIFEST.json"] == _sha(CAMP / "RAW_DATA_MANIFEST.json")
    assert b["CONFIRMATORY_RESULT_MANIFEST.json"] == _sha(CAMP / "CONFIRMATORY_RESULT_MANIFEST.json")
