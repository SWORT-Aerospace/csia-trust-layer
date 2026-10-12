"""Perform the external-access check and record what actually happened.

WHY THIS IS A TOOL AND NOT A FILE I WROTE
------------------------------------------
The first version of ``results/EXTERNAL_ACCESS_CHECK.json`` was authored by
hand. Its HTTP codes were real -- I had just run the requests -- but its
``retrieval_attempt_utc`` was **typed**, not captured. A timestamp I typed into
an evidence artifact is an invented number in the one place the standing rules
say numbers may not be invented, however nearly right it was.

So the artifact is generated now. Every field in it is measured at run time:
the timestamp, the HTTP status, the curl exit code, the elapsed time and the
proxy's own report. Re-running it re-measures rather than re-asserts, and if
access is ever restored the artifact will say so on its own.

It records no content hash unless content was actually retrieved. A hash of a
document never fetched is a fabrication and the field says that instead.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / ("research/active_evidence/independent_validation/results/"
              "EXTERNAL_ACCESS_CHECK.json")

TARGET = {
    "citation": ("X. Ni, M. Ornik, G. Chou, S. Coogan, Safe, Real-Time Active "
                 "Model Discrimination and Fault Diagnosis for Nonlinear "
                 "Systems via Differentiable Reachability, arXiv:2606.19590v1, "
                 "17 June 2026"),
    "doi": "10.48550/arXiv.2606.19590",
    "arxiv_id": "2606.19590v1",
}

ENDPOINTS = (
    "https://arxiv.org/abs/2606.19590",
    "https://arxiv.org/abs/2606.19590v1",
    "https://arxiv.org/html/2606.19590v1",
    "https://export.arxiv.org/abs/2606.19590",
    "http://export.arxiv.org/api/query?id_list=2606.19590",
    "https://doi.org/10.48550/arXiv.2606.19590",
    "https://api.semanticscholar.org/graph/v1/paper/arXiv:2606.19590",
    "https://api.openalex.org/works/doi:10.48550/arXiv.2606.19590",
)

SECTIONS_REQUIRED = ("III", "V-A", "V-B", "V-C", "V-D", "V-E", "VI-B", "VI-D",
                     "VII")


def probe(url: str, *, timeout: int = 20) -> Dict:
    """One request. Records the answer, whatever it is."""
    result = subprocess.run(
        ("curl", "-sS", "-o", "/dev/null", "-w",
         "%{http_code} %{time_total} %{size_download}", "--max-time",
         str(timeout), url),
        capture_output=True, text=True)
    fields = result.stdout.split()
    return {
        "url": url,
        "curl_exit": result.returncode,
        "http_code": fields[0] if fields else None,
        "time_total_s": float(fields[1]) if len(fields) > 1 else None,
        "bytes_downloaded": int(fields[2]) if len(fields) > 2 else 0,
        "stderr": result.stderr.strip()[:400],
    }


def proxy_report() -> Dict:
    proxy = os.environ.get("HTTPS_PROXY")
    if not proxy:
        return {"available": False}
    result = subprocess.run(
        ("curl", "-sS", "--max-time", "10",
         f"{proxy}/__agentproxy/status"), capture_output=True, text=True)
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"available": False, "raw": result.stdout[:400]}
    return {
        "available": True,
        "enabled": status.get("enabled"),
        "recent_relay_failures": status.get("recentRelayFailures", [])[:3],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="overwrite the committed artifact")
    args = parser.parse_args()

    attempts: List[Dict] = [probe(url) for url in ENDPOINTS]
    retrieved = [a for a in attempts
                 if a["http_code"] == "200" and a["bytes_downloaded"] > 0]

    document = {
        "schema": "csia.independent_validation.access_check/2",
        "generated_by": "tools/research/iv_access_check.py",
        "retrieval_attempt_utc": datetime.datetime.now(
            datetime.timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"),
        "target": TARGET,
        "endpoints": attempts,
        "proxy_report": proxy_report(),
        "outcome": ("PRIMARY_TEXT_RETRIEVED" if retrieved
                    else "PRIMARY_TEXT_NOT_RETRIEVED"),
        "content_hash_of_primary_text": None,
        "content_hash_note": (
            "No hash is recorded because no primary text was retrieved. "
            "Recording a hash of a document never fetched would be a "
            "fabrication." if not retrieved else
            "Content was retrieved; hash it deliberately and record which "
            "endpoint served it."),
        "sections_required_by_the_task": list(SECTIONS_REQUIRED),
        "sections_read": [],
        "what_is_used_instead": (
            "Three user-supplied secondary characterisations: sections "
            "13.1-13.4 of the task brief, "
            "RCEC_RELATED_WORK_AND_NOVELTY_BOUNDARY.md, and section 15 of "
            "XR_AHE_CSIA_FORGE_MODEL_SPECIFIC_ROADMAP_V0_3_1.md, the last of "
            "which states the primary HTML text was accessible during that "
            "document's revision. All three are secondary FROM HERE. A report "
            "that somebody read a paper is not a claim-element comparison "
            "performed against it."),
        "consequence": (
            "Novelty status NOVELTY_UNRESOLVED. The matrix rows for the Ni et "
            "al. column are marked FROM_BRIEF_NOT_PRIMARY_TEXT."),
        "corroboration": (
            "All three secondary sources agree that the objective is "
            "volumetric and that zero volume is not empty intersection. That "
            "agreement is why the touching-set distinction was built into "
            "discrimination.py rather than assumed away, and it occurred in "
            "48 of 12960 validation cells."),
    }

    print(f"attempt at {document['retrieval_attempt_utc']}")
    for attempt in attempts:
        print(f"  {attempt['url']:<62s} http={attempt['http_code']} "
              f"curl_exit={attempt['curl_exit']} "
              f"bytes={attempt['bytes_downloaded']}")
    print(f"outcome: {document['outcome']}")

    if args.write:
        OUT.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        print("(dry run; pass --write to overwrite the committed artifact)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
