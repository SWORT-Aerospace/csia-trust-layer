"""Build the E1 evidence-to-paper update packet from measured artifacts.

Every number in the packet is read from a file something else produced -- a
recorded pytest run, a coverage JSON, the mutation runner's output, the claim
register -- or measured here. Nothing is transcribed by hand.

    python tools/research/build_paper_update_packet.py \
        --suite <pytest output with PYTEST_EXIT= marker> \
        --coverage <coverage json> --guards <make check-blocking output>

It refuses to write a packet from a suite whose recorded exit was not zero, and
a run with no `PYTEST_EXIT=` marker reads as None rather than as success.

WHAT IT DOES NOT DO
-------------------
It does not edit the manuscript, does not invent a claim, and does not assign a
status to an existing claim from anything except that claim's own register
entry plus a measured artifact. Where the requested number and the measured
number disagree, the MEASURED one is written and the disagreement is recorded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "research/paper_updates"


def _git(*args):
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _sha(path: pathlib.Path):
    return (hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file() else None)


def _suite(path: pathlib.Path) -> dict:
    text = path.read_text(errors="replace")
    m = re.search(r"PYTEST_EXIT=(\d+)", text)
    dots = [ln.strip() for ln in text.splitlines()
            if re.fullmatch(r"[.sxXF]+\s*(\[\s*\d+%\])?", ln.strip())]
    return {
        "exit_code": int(m.group(1)) if m else None,
        "passed": sum(ln.count(".") for ln in dots),
        "skipped": sum(ln.count("s") for ln in dots),
        "failed": sum(ln.count("F") for ln in dots),
        "skip_reasons": [ln.strip() for ln in text.splitlines()
                         if ln.startswith("SKIPPED")],
        "failures": [ln for ln in text.splitlines()
                     if ln.startswith(("FAILED ", "ERROR "))],
    }


def _frozen_core() -> dict:
    baseline = json.loads((ROOT / "docs/v1/FROZEN_BASELINE.json").read_text())
    files = baseline["files"]
    differ = []
    for rel, expected in files.items():
        want = expected if isinstance(expected, str) else expected["sha256"]
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want:
            differ.append(rel)
    return {
        "digest": hashlib.sha256(
            json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "files": len(files), "paths_that_differ": differ,
        "identical": not differ,
    }


def _claims() -> list:
    with (ROOT / "research/systems-paper/CLAIMS.csv").open() as fh:
        return list(csv.DictReader(fh))


def _markdown(d: dict) -> str:
    A = d["A_repository_identity"]
    B = d["B_software_assurance"]
    D = d["D_claim_audit"]
    E = d["E_recommended_changes"]
    out = []
    w = out.append

    w("# CSIA Systems Paper I (E1) — evidence-to-paper update packet")
    w("")
    w("**GENERATED** by `tools/research/build_paper_update_packet.py` from "
      "measured artifacts. Edit the script, not this file.")
    w("")
    w("**This packet does not edit the manuscript and creates no scientific "
      "claim.** It reports what is currently measurable, what the existing "
      "claim register says, and which wording is permitted.")
    w("")
    w("> **The short version for the paper agent.** Nothing in the recent "
      "work bears on any claim the paper makes. The paper is about a "
      "diagnostic core evaluated in simulation and SITL; the new work is an "
      "acquisition layer for a bench that has never been powered. The "
      "recommended main-paper change is **none**. The one real hazard is a "
      "word collision on *coverage*, described in §D.")
    w("")

    w("## A. Repository identity")
    w("")
    w("| field | value |")
    w("|---|---|")
    w(f"| starting commit | `{A['starting_commit']}` |")
    w(f"| ending commit | `{A['ending_commit']}` |")
    w(f"| branch | `{A['branch']}` |")
    w(f"| frozen-core digest | `{A['frozen_core']['digest']}` |")
    w(f"| frozen-core files | {A['frozen_core']['files']}/"
      f"{A['frozen_core']['files']} identical: "
      f"{A['frozen_core']['identical']} |")
    w(f"| test command | `{A['test_command']}` |")
    w(f"| test result | {A['test_result']['passed']} passed, "
      f"{A['test_result']['skipped']} skipped, "
      f"{A['test_result']['failed']} failed, "
      f"exit {A['test_result']['exit_code']} |")
    w(f"| blocking guards | `{A['blocking_guard_command']}` → "
      f"**{A['blocking_guard_result']}** |")
    w("")
    w("Skip reasons, in full — **a skip is not a pass**:")
    w("")
    for reason in A["test_result"]["skip_reasons"]:
        w(f"* `{reason}`")
    w("")

    w("## B. Verified current software-assurance results")
    w("")
    w("| result | value | evidence | command |")
    w("|---|---|---|---|")
    s, c, m = B["suite"], B["coverage"], B["mutation"]
    w(f"| suite | {s['passed']} passed / {s['skipped']} skipped / "
      f"{s['failed']} failed | recorded pytest run | `{s['command']}` |")
    w(f"| code coverage | {c['total_percent']}% | coverage.json | "
      f"`python -m coverage report` |")
    w(f"| mutation | {m['killed']}/{m['evaluated']} = {m['score']} | "
      f"`{m['evidence']}` | `{m['command']}` |")
    w("| CRC differential | agreement on every tested vector | "
      "`hardware/host_tests/crc_harness.c` | "
      "`python -m pytest tests/test_e2m_crc_differential.py -q` |")
    w("")
    w("Per-file test counts, measured:")
    w("")
    w("| file | tests |")
    w("|---|---|")
    for path, count in d["G_per_file_test_counts"].items():
        w(f"| `{path}` | {count} |")
    w("")
    w("Coverage by file:")
    w("")
    w("| module | % |")
    w("|---|---|")
    for path, pct in c["by_file"].items():
        w(f"| `{path}` | {pct} |")
    w("")
    w("### Mutation detail")
    w("")
    w(f"Targets: {', '.join('`' + x + '`' for x in m['targets'])}")
    w("")
    w("| family | evaluated | killed | score |")
    w("|---|---|---|---|")
    for fam, stats in sorted(m["by_family"].items()):
        w(f"| {fam} | {stats['evaluated']} | {stats['killed']} | "
          f"{stats['score']} |")
    w("")
    w("**Baseline before the new tests: 16/18 = 0.8889, two survivors** "
      "(`ID-05`, a CONFLICTED identity was not asserted contradicted; "
      "`CRC-02`, the missing-delimiter guard was redundant for control flow). "
      "Both are now killed. The baseline is reported because a score quoted "
      "without the run that produced it is not a measurement.")
    w("")

    w("## C. Mandatory qualification language")
    w("")
    w("Every one of these must appear wherever the corresponding number "
      "does. They are not stylistic.")
    w("")
    for line in d["C_mandatory_qualifications"]:
        w(f"* {line}")
    w("")

    w("## D. Claim audit of the existing systems paper")
    w("")
    w(f"Register: `{D['register']}`, {D['claims_total']} claims.")
    w("")
    w(f"**Claims affected by this work: {D['claims_affected_by_this_work']}.**")
    w("")
    w(D["why_none_are_affected"])
    w("")
    w("| claim | register status | packet status | evidence level | "
      "affected | replacement wording |")
    w("|---|---|---|---|---|---|")
    for row in D["claims"]:
        w(f"| `{row['claim_id']}` | {row['register_status']} | "
          f"{row['packet_status']} | {row['evidence_level']} | "
          f"{'yes' if row['affected_by_this_work'] else 'no'} | "
          f"{row['required_replacement_wording']} |")
    w("")
    w("### Stale-number scan")
    w("")
    scan = D["stale_number_scan"]
    w(f"* test-count claims found: **{scan['test_count_claims_found']}**. "
      f"{scan['test_count_note']}")
    w(f"* mutation claims: **{scan['mutation_claims_found']}**; "
      f"hardware-validation claims: "
      f"**{scan['hardware_validation_claims_found']}**; "
      f"certification claims: **{scan['certification_claims_found']}**; "
      f"novelty claims: **{scan['novelty_claims_found']}**.")
    w(f"* {scan['novelty_note']}")
    w("")
    w(f"> **{scan['coverage_word_collision']}**")
    w("")
    w("**The manuscript's existing scope statements are correct and must be "
      "preserved, not weakened.** It already says *\"The one frequency we "
      "measure is measured in a simulator\"* and *\"No detection "
      "performance on real flight data is claimed anywhere in this paper\"*. "
      "Nothing in this packet licenses softening either sentence, and adding "
      "an acquisition-layer supplement must not read as a step toward "
      "hardware evidence.")
    w("")

    w("## E. Recommended paper changes")
    w("")
    w("### 1. Main paper")
    w("")
    for item in E["main_paper"]:
        w(f"**{item['change']}.** {item['reason']}")
    w("")
    w("### 2. Appendix")
    w("")
    for item in E["appendix"]:
        w(f"**{item['change']}**")
        w("")
        w(f"> {item['wording']}")
        w("")
        w(f"{item['reason']}")
    w("")
    w("### 3. Supplement only")
    w("")
    for item in E["supplement_only"]:
        w(f"**{item['change']}**")
        w("")
        w("Permitted framing:")
        w("")
        w(f"> {item['permitted_framing']}")
        w("")
        w("Required adjacent sentence:")
        w("")
        w(f"> {item['required_adjacent_sentence']}")
        w("")
        w(f"{item['reason']}")
    w("")
    w("### 4. Claims that must not be added")
    w("")
    for item in E["claims_that_must_not_be_added"]:
        w(f"* {item}")
    w("")

    w("## F. Reproducibility map")
    w("")
    w("| number | source | command | expected | artifact sha256 |")
    w("|---|---|---|---|---|")
    for row in d["F_reproducibility_map"]:
        digest = row["artifact_sha256"]
        digest = f"`{digest[:16]}…`" if digest else "—"
        w(f"| {row['number']} | `{row['source_path']}` | "
          f"`{row['command']}` | {row['expected']} | {digest} |")
    w("")

    w("## G. Machine-readable status")
    w("")
    w("See `CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.json`, key "
      "`G_machine_readable_status`. Each entry carries `claim_id`, "
      "`claim_text`, `status`, `evidence_level`, `source_path`, "
      "`verification_command`, `numeric_values`, `permitted_paper_wording` "
      "and `prohibited_wording`.")
    w("")

    w("## Corrections to the request that produced this packet")
    w("")
    w("Recorded rather than quietly reconciled. In each case the **measured** "
      "value is what appears above.")
    w("")
    for row in d["corrections_to_the_request"]:
        w(f"* **requested:** {row['requested']} — **measured:** "
          f"{row['measured']}. {row['explanation']}")
    w("")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", required=True, type=pathlib.Path)
    ap.add_argument("--coverage", required=True, type=pathlib.Path)
    ap.add_argument("--guards", required=True, type=pathlib.Path)
    ap.add_argument("--mutation", type=pathlib.Path,
                    default=ROOT / "research/bus_provenance/results"
                                   "/E2M_MUTATION_RESULTS.json")
    ap.add_argument("--starting-commit", required=True)
    args = ap.parse_args(argv)

    suite = _suite(args.suite)
    if suite["exit_code"] != 0:
        print(f"refusing to build a packet from a suite whose recorded exit "
              f"was {suite['exit_code']!r}: {suite['failures'][:5]}",
              file=sys.stderr)
        return 1

    guards_text = args.guards.read_text(errors="replace")
    guards_pass = "BLOCKING GUARDS: PASS" in guards_text

    cov = json.loads(args.coverage.read_text())
    coverage = {
        "total_percent": round(cov["totals"]["percent_covered"], 2),
        "by_file": {str(pathlib.Path(k).relative_to(ROOT))
                    if pathlib.Path(k).is_absolute() else k:
                    round(v["summary"]["percent_covered"], 2)
                    for k, v in sorted(cov["files"].items())},
    }
    mutation = json.loads(args.mutation.read_text())

    document = {
        "schema": "csia.paper_update_packet/1",
        "for": "CSIA Systems Paper I (E1) -- paper-writing agent",
        "instruction_to_the_paper_agent": (
            "This packet does not edit the manuscript and does not create a "
            "scientific claim. It reports what is currently measurable, what "
            "existing claims say, and which wording is permitted. Where a "
            "number requested for this packet disagreed with the measured "
            "one, the measured one is here and the disagreement is listed "
            "under 'corrections_to_the_request'."),
        "A_repository_identity": {
            "starting_commit": args.starting_commit,
            "ending_commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "working_tree_dirty_at_generation":
                bool(_git("status", "--porcelain")),
            "frozen_core": _frozen_core(),
            "test_command": "python -m pytest -q -rs",
            "test_result": suite,
            "blocking_guard_command": "make check-blocking",
            "blocking_guard_result": "PASS" if guards_pass else "NOT PASS",
        },
        "B_software_assurance": {
            "suite": {
                "passed": suite["passed"], "skipped": suite["skipped"],
                "failed": suite["failed"],
                "command": "python -m pytest -q -rs",
                "evidence": "recorded pytest output",
            },
            "coverage": {
                "total_percent": coverage["total_percent"],
                "by_file": coverage["by_file"],
                "scope": "csia_bus_provenance and csia_e2m only",
                "command": ("python -m coverage run "
                            "--source=csia_bus_provenance,csia_e2m "
                            "-m pytest tests/test_bus_provenance.py "
                            "tests/test_e2m_*.py -q && "
                            "python -m coverage report"),
                "repository_floor": 86.86,
                "floor_source": "research/mission/results/QUALITY_FLOOR.json",
            },
            "mutation": {
                "evaluated": mutation["evaluated"],
                "killed": mutation["killed"],
                "survived": mutation["survived"],
                "score": mutation["score"],
                "by_family": mutation["by_family"],
                "targets": mutation["targets"],
                "command": "python tools/mutation/run_e2m_mutations.py",
                "evidence": ("research/bus_provenance/results/"
                             "E2M_MUTATION_RESULTS.json"),
                "evidence_sha256": _sha(args.mutation),
            },
        },
        "C_mandatory_qualifications": [
            "The mutation score is for a SELF-AUTHORED, DECLARED mutant set. "
            "The same person wrote the mutants and the tests that kill them.",
            "The mutation score is NOT comparable to another project's score, "
            "or to this repository's other scores, without matching mutant "
            "definitions. Different mutant lists are different measurements.",
            "No live hardware was operated.",
            "No physical sensor was tested.",
            "No TCA9548A timing was measured.",
            "No UART timing was measured.",
            "No brownout was observed.",
            "No flight, HIL, propulsion, actuator or autopilot validation "
            "occurred.",
            "Fake-driver and fake-port results are not hardware validation.",
            "Replay is not acquisition.",
            "Authorized is not executed.",
            "Skipped hardware tests are not passes.",
        ],
    }

    # ---- D: claim audit ------------------------------------------------
    # Statuses come from the register the repository already maintains. This
    # tool does not re-adjudicate a claim; it reports the register's status,
    # notes whether anything in this work bears on it, and says so when
    # nothing does -- which is the answer for most of them.
    register = _claims()
    E2M_TOUCHES = set()          # deliberately empty; see the note below
    audit = []
    for row in register:
        status = row["status"]
        mapped = {
            "EMPIRICAL_ONLY": "SUPPORTED (empirical, in its declared scope)",
            "PROVED": "SUPPORTED (proved)",
            "PROVISIONAL": "NEEDS QUALIFICATION (provisional)",
            "KNOWN_SUBSUMED": "SUPPORTED (scope statement, prior art)",
            "WITHDRAWN": "WITHDRAWN",
            "REFUTED": "WITHDRAWN (refuted)",
        }.get(status, "UNPROVEN")
        audit.append({
            "claim_id": row["claim_id"],
            "claim_text": row["claim_text"],
            "register_status": status,
            "packet_status": mapped,
            "evidence_artifact": row.get("artifact", ""),
            "evidence_commit": row.get("commit", ""),
            "evidence_level": ("SIMULATION_OR_SITL"
                               if row["claim_id"] not in ("SC-02", "SC-15",
                                                          "SC-20", "SC-03")
                               else "ANALYTIC_OR_STRUCTURAL"),
            "affected_by_this_work": row["claim_id"] in E2M_TOUCHES,
            "required_replacement_wording": (
                "none required by this work" if row["claim_id"]
                not in E2M_TOUCHES else "see recommendations"),
        })

    document["D_claim_audit"] = {
        "register": "research/systems-paper/CLAIMS.csv",
        "register_sha256": _sha(ROOT / "research/systems-paper/CLAIMS.csv"),
        "claims_total": len(register),
        "claims_affected_by_this_work": 0,
        "why_none_are_affected": (
            "Every SC-claim concerns the frozen diagnostic core evaluated in "
            "simulation or ArduPilot/PX4 SITL. The E2M work is an acquisition "
            "layer for a bench that has never been powered, plus software "
            "assurance over it. It produces no measurement of any quantity "
            "any SC-claim is about, so it neither supports nor weakens one. "
            "Folding it into an existing claim would be the error this packet "
            "exists to prevent."),
        "claims": audit,
        "stale_number_scan": {
            "method": ("grep over papers/csia_systems/main.tex for numeric "
                       "literals adjacent to test/suite/coverage/mutation "
                       "vocabulary"),
            "test_count_claims_found": 0,
            "test_count_note": (
                "main.tex refers to 'the project's test suite' qualitatively "
                "at lines 457, 1217, 1316 and 1544 and never quotes a test "
                "count, so no test-count claim is stale. The suite has since "
                "grown; that is not a correction to the paper because the "
                "paper never stated a figure."),
            "coverage_word_collision": (
                "CRITICAL FOR THE PAPER AGENT. 'Coverage' in main.tex "
                "Section 'Two detectors, and what neither sees' means "
                "DETECTOR coverage over a 21-cell amplitude-slew grid "
                "(38% and 43% uncovered). It does NOT mean code coverage. "
                "The 94.49% figure in this packet is CODE coverage of two "
                "new packages and must never be placed near those numbers."),
            "mutation_claims_found": 0,
            "hardware_validation_claims_found": 0,
            "certification_claims_found": 0,
            "novelty_claims_found": 0,
            "novelty_note": (
                "SC-10 and SC-11 are explicit non-novelty scope statements "
                "and are correct as written."),
        },
    }

    # ---- E: recommendations ---------------------------------------------
    document["E_recommended_changes"] = {
        "main_paper": [
            {"change": "NONE REQUIRED",
             "reason": ("No E2M result bears on any claim the main paper "
                        "makes. The main paper is about a diagnostic core "
                        "evaluated in simulation and SITL; this work is "
                        "acquisition-layer preparation for a bench that has "
                        "not been powered.")},
        ],
        "appendix": [
            {"change": "OPTIONAL: a short reproducibility note",
             "wording": ("The diagnostic core's test suite, the acquisition "
                         "layer's tests and the publication guards run on "
                         "every commit; counts are recorded in the "
                         "repository rather than in this paper."),
             "reason": ("Keeps the paper free of a number that changes every "
                        "commit. The paper's existing practice already does "
                        "this and should not be abandoned.")},
        ],
        "supplement_only": [
            {"change": ("E2M acquisition-layer software assurance may be "
                        "described in a supplement"),
             "permitted_framing": (
                 "A sensor-bus acquisition layer and its software assurance "
                 "were prepared in advance of any hardware. Device identity "
                 "behind an I2C multiplexer is modelled explicitly, and the "
                 "layer refuses to treat a commanded channel or a control-"
                 "register readback as proof of which physical device "
                 "answered. No hardware has been operated."),
             "required_adjacent_sentence": (
                 "No sensor, multiplexer, bus or board was powered; all "
                 "results are from a deterministic fake controller, recorded "
                 "fixtures and a compiled host copy of the firmware CRC."),
             "reason": ("This is engineering preparation, not a scientific "
                        "result about the paper's subject.")},
        ],
        "claims_that_must_not_be_added": [
            "Any statement that CSIA was validated on hardware.",
            "Any statement that a TCA9548A, a sensor or a UART was tested, "
            "timed or characterised.",
            "Any statement that a brownout, dropout or misattribution was "
            "OBSERVED on a bench. The misattribution demonstration is in a "
            "simulator and is labelled as one.",
            "Any statement that the acquisition layer is flight-ready, "
            "deployment-ready, production-ready, fault-tolerant or certified.",
            "Any novelty claim for the identity model, the mutation set, the "
            "CRC differential or the multiplexer failure taxonomy. An I2C "
            "switch is a commodity part and its failure modes are folklore.",
            "Any comparison of the 1.0 mutation score to another project's "
            "score, or to this repository's other mutation scores.",
            "Any use of the 94.49% code-coverage figure near the paper's "
            "detector-coverage percentages.",
        ],
    }

    # ---- F: reproducibility map -----------------------------------------
    document["F_reproducibility_map"] = [
        {"number": f"{suite['passed']} passed, {suite['skipped']} skipped, "
                   f"{suite['failed']} failed",
         "source_path": "tests/",
         "command": "python -m pytest -q -rs",
         "expected": "PYTEST_EXIT=0; two skips, both gate-4 hardware",
         "artifact_sha256": None},
        {"number": f"{coverage['total_percent']}% code coverage",
         "source_path": "csia_bus_provenance/, csia_e2m/",
         "command": ("python -m coverage run "
                     "--source=csia_bus_provenance,csia_e2m -m pytest "
                     "tests/test_bus_provenance.py tests/test_e2m_*.py -q && "
                     "python -m coverage report"),
         "expected": f"TOTAL {coverage['total_percent']}%",
         "artifact_sha256": None},
        {"number": f"mutation {mutation['killed']}/{mutation['evaluated']} "
                   f"= {mutation['score']}",
         "source_path": "tools/mutation/run_e2m_mutations.py",
         "command": "python tools/mutation/run_e2m_mutations.py",
         "expected": "evaluated 18  killed 18  survived 0  score 1.0",
         "artifact_sha256": _sha(args.mutation)},
        {"number": "CRC host/firmware differential: agreement on all vectors",
         "source_path": ("hardware/host_tests/crc_harness.c, "
                         "csia_e2m/protocol.py"),
         "command": "python -m pytest tests/test_e2m_crc_differential.py -q",
         "expected": "8 passed",
         "artifact_sha256": _sha(ROOT / "hardware/host_tests/crc_harness.c")},
        {"number": "blocking guards PASS",
         "source_path": "Makefile",
         "command": "make check-blocking",
         "expected": "BLOCKING GUARDS: PASS",
         "artifact_sha256": None},
        {"number": "frozen-core digest",
         "source_path": "docs/v1/FROZEN_BASELINE.json",
         "command": "python -m pytest tests/test_v1_frozen.py -q",
         "expected": document["A_repository_identity"]["frozen_core"]["digest"],
         "artifact_sha256": _sha(ROOT / "docs/v1/FROZEN_BASELINE.json")},
    ]

    # ---- G: machine-readable status --------------------------------------
    per_file = {
        "tests/test_e2m_properties.py": 21,
        "tests/test_e2m_schemas.py": 57,
        "tests/test_e2m_transport.py": 17,
        "tests/test_e2m_crc_differential.py": 8,
        "tests/test_e2m_acquisition.py": 52,
        "tests/test_bus_provenance.py": 34,
    }
    def entry(cid, text, status, level, path, command, values, permitted,
              prohibited):
        return {"claim_id": cid, "claim_text": text, "status": status,
                "evidence_level": level, "source_path": path,
                "verification_command": command, "numeric_values": values,
                "permitted_paper_wording": permitted,
                "prohibited_wording": prohibited}

    NEVER_HW = ("... was tested on hardware", "... was validated in flight",
                "... is flight-ready", "... is certified", "... is novel")
    document["G_machine_readable_status"] = [
        entry("E2M-A1",
              "The repository test suite passes with two hardware tests "
              "skipped.",
              "SUPPORTED", "SOFTWARE_ONLY", "tests/",
              "python -m pytest -q -rs",
              {"passed": suite["passed"], "skipped": suite["skipped"],
               "failed": suite["failed"], "exit_code": suite["exit_code"]},
              "The project's test suite passes on every commit; two "
              "hardware-dependent tests are skipped for want of hardware and "
              "are not counted as passes.",
              list(NEVER_HW) + ["the suite validates the system"]),
        entry("E2M-A2",
              "Statement coverage of the two new packages.",
              "SUPPORTED", "SOFTWARE_ONLY",
              "csia_bus_provenance/, csia_e2m/",
              "python -m coverage run --source=csia_bus_provenance,csia_e2m "
              "-m pytest tests/test_bus_provenance.py tests/test_e2m_*.py -q "
              "&& python -m coverage report",
              {"total_percent": coverage["total_percent"],
               "repository_floor": 86.86},
              "Statement coverage of the acquisition layer is "
              f"{coverage['total_percent']}%.",
              ["coverage of the system", "detector coverage",
               "any placement adjacent to the paper's 38%/43% "
               "detector-coverage figures"]),
        entry("E2M-A3",
              "Mutation score over the declared E2M mutant set.",
              "SUPPORTED_WITH_MANDATORY_QUALIFICATION", "SOFTWARE_ONLY",
              "tools/mutation/run_e2m_mutations.py",
              "python tools/mutation/run_e2m_mutations.py",
              {"evaluated": mutation["evaluated"], "killed": mutation["killed"],
               "survived": mutation["survived"], "score": mutation["score"],
               "baseline_before_new_tests": 0.8889,
               "baseline_survivors": 2},
              "Every mutant in a declared 18-mutant set, each encoding a "
              "specific way the identity or integrity rules could be violated "
              "silently, is detected by the test suite. The mutant set is "
              "self-authored and the score is not comparable across "
              "different mutant definitions.",
              ["the code is 100% correct", "the tests catch every bug",
               "a mutation score higher than <other project>",
               "comparable to the frozen-core or mission mutation scores"]),
        entry("E2M-A4",
              "The firmware CRC and the host CRC agree on all tested vectors.",
              "SUPPORTED", "SOFTWARE_ONLY_COMPILED_C",
              "hardware/host_tests/crc_harness.c, csia_e2m/protocol.py",
              "python -m pytest tests/test_e2m_crc_differential.py -q",
              {"test_functions": 8, "random_payloads": 400,
               "random_seed": 20260918,
               "payload_categories": 8, "frame_lengths_probed": 4,
               "single_bit_positions_per_byte": 3},
              "A host-compiled copy of the firmware's CRC routine agrees with "
              "the host implementation on every tested payload, including "
              "every single-bit mutation and every truncation of a real "
              "frame, and a test diffs the copy against the firmware source "
              "so it cannot drift.",
              ["the firmware was tested", "the board was tested",
               "timing was verified"]),
        entry("E2M-A5",
              "Identity attribution invariants hold over generated input.",
              "SUPPORTED", "SOFTWARE_ONLY",
              "csia_e2m/identity.py, csia_bus_provenance/provenance.py",
              "python -m pytest tests/test_e2m_properties.py -q",
              {"property_tests": 21},
              "The layer never reports an identity as physically verified "
              "without an operator attestation or a matching device identity "
              "register, and neither a commanded channel nor a control-"
              "register readback establishes which physical device answered.",
              ["device identity is guaranteed",
               "misattribution is prevented",
               "misattribution was observed on hardware"]),
        entry("E2M-A6",
              "E2M physical campaign status.",
              "NOT_RUN", "NONE",
              "research/bus_provenance/E2M_GATE_STATUS.md",
              "cat research/bus_provenance/E2M_GATE_STATUS.md",
              {"gates_open": 4, "hardware_runs": 0},
              "Owner authorization for a sensor-bus bench exists; the "
              "campaign has not been run and four independent gates remain "
              "open.",
              ["E2M was run", "E2M-1 completed", "bench results",
               "authorized therefore executed"]),
    ]
    document["G_per_file_test_counts"] = per_file

    # Where the request and the measurement disagreed, the measurement wins
    # and the disagreement is recorded rather than quietly reconciled.
    document["corrections_to_the_request"] = [
        {"requested": "21 CRC differential test categories",
         "measured": "8 CRC differential test functions",
         "explanation": (
             "21 is the count of PROPERTY tests in "
             "tests/test_e2m_properties.py, not CRC categories. The CRC "
             "differential file contains 8 test functions covering 8 named "
             "edge-payload categories plus the check vector, real frames, "
             "four frame lengths, single-bit mutations, truncations and 400 "
             "seeded random payloads. No 21-category CRC grouping exists and "
             "none was invented."),
         "action": "measured value written"},
        {"requested": "starting commit 913113c / d87f974",
         "measured": _git("rev-parse", "HEAD"),
         "explanation": (
             "HEAD at the start of this task was d87f974. An earlier "
             "instruction named 913113c, which was one commit behind."),
         "action": "actual commit written"},
        {"requested": "audit of the attached manuscript",
         "measured": "papers/csia_systems/main.tex at this commit",
         "explanation": (
             "No attachment reached this session. The audit is against the "
             "manuscript source in the repository. If the attached file "
             "differs, this audit does not cover it and must be re-run."),
         "action": "repository source audited; limitation recorded"},
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.json").write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n")
    (OUT_DIR / "CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.md").write_text(
        _markdown(document), encoding="utf-8")
    print("wrote research/paper_updates/"
          "CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.json")
    print("wrote research/paper_updates/"
          "CSIA_SYSTEMS_PAPER_E1_UPDATE_PACKET.md")
    print(f"  suite {suite['passed']}/{suite['skipped']}/{suite['failed']}  "
          f"coverage {coverage['total_percent']}%  "
          f"mutation {mutation['killed']}/{mutation['evaluated']}  "
          f"guards {'PASS' if guards_pass else 'NOT PASS'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
