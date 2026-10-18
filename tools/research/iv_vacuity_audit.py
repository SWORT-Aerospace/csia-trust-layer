"""Audit every declared check in this phase for vacuity.

Answers, for each check, the question that three separate defects in this line
of work turned on: when this check reports a constant, is that a result or a
bug? See ``csia_independent_validation/vacuity.py`` for the taxonomy.

Run over the sealed campaign and its gate table. Reports, never passes or
fails; the accompanying test is what fails.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import evaluator as ev              # noqa: E402
from csia_independent_validation import gates                        # noqa: E402
from csia_independent_validation import strategies as st             # noqa: E402
from csia_independent_validation.vacuity import Check, audit         # noqa: E402

RESULTS = ROOT / "research/active_evidence/independent_validation/results"


def _resolved_point(row: Dict) -> bool:
    if row.get("ae_r") is None or row.get("magnitude") is None:
        return False
    return row["ae_r"] < ev.TAU_R_RELATIVE * row["magnitude"]


def state_checks() -> List[Check]:
    """One check per certificate state, plus the two false-certificate checks."""
    def is_state(name):
        return lambda row, n=name: (None if row.get("state") is None
                                    else row["state"] == n)

    checks = [
        Check(name=f"certificate_state::{name}", predicate=is_state(name),
              positive={"state": name}, negative={"state": "SOMETHING_ELSE"})
        for name in ("CERTIFIED_IN_MODEL", "MODEL_MISMATCH_LIMITED",
                     "INSUFFICIENT_EXCITATION", "DRIFT_COUPLED",
                     "UNKNOWN_OR_MODEL_MISMATCH",
                     "CLIPPED_CERTIFICATE_INVALID", "ABORTED_INCOMPLETE")
    ]

    def false_certificate_point(row):
        if row.get("state") is None:
            return None
        return (row["state"] == "CERTIFIED_IN_MODEL"
                and not _resolved_point(row))

    def false_certificate_change(row):
        if row.get("state") is None:
            return None
        return row["state"] == "CERTIFIED_IN_MODEL" and not row.get("resolved")

    checks.append(Check(
        name="false_certificate::point",
        predicate=false_certificate_point,
        # A certified cell whose point error exceeds its own tolerance.
        positive={"state": "CERTIFIED_IN_MODEL", "ae_r": 0.05,
                  "magnitude": 0.010},
        negative={"state": "CERTIFIED_IN_MODEL", "ae_r": 1e-5,
                  "magnitude": 0.010},
        note=("the check the prior phase could not make fire. A zero here is "
              "the headline result, and only because the controls show it is "
              "reachable.")))
    checks.append(Check(
        name="false_certificate::change",
        predicate=false_certificate_change,
        positive={"state": "CERTIFIED_IN_MODEL", "resolved": False},
        negative={"state": "CERTIFIED_IN_MODEL", "resolved": True}))
    checks.append(Check(
        name="outcome::resolved_point",
        predicate=lambda row: (None if row.get("ae_r") is None
                               else _resolved_point(row)),
        positive={"ae_r": 1e-5, "magnitude": 0.010},
        negative={"ae_r": 0.05, "magnitude": 0.010}))
    checks.append(Check(
        name="outcome::resolved_change",
        predicate=lambda row: (None if row.get("resolved") is None
                               else bool(row["resolved"])),
        positive={"resolved": True}, negative={"resolved": False}))
    checks.append(Check(
        name="selector::abstained",
        predicate=lambda row: row.get("abstention") is not None,
        positive={"abstention": st.NO_SAFE_INFORMATIVE_ACTION},
        negative={"abstention": None},
        note=("all three abstention paths are reachable and tested; whether "
              "any was reached in the campaign is what this measures.")))
    return checks


def gate_checks() -> List[Check]:
    return [
        Check(name="gate::post_pass",
              predicate=lambda row: bool(row["post_pass"]),
              positive={"post_pass": True}, negative={"post_pass": False}),
        Check(name="gate::pre_separates",
              predicate=lambda row: bool(row["pre_separates"]),
              positive={"pre_separates": True},
              negative={"pre_separates": False}),
        Check(name="gate::pre_safe",
              predicate=lambda row: bool(row["pre_safe"]),
              positive={"pre_safe": True}, negative={"pre_safe": False},
              vacuous_over_domain=True,
              why_vacuous=(
                  "every admissible action peaks at 34 A against a declared "
                  "56 A limit, so no admissible action can fail this. It "
                  "fails only for an abstention, where there is no action. "
                  "The check itself works -- a 45 A hold fails it -- and the "
                  "action space, not the check, is why it is constant. "
                  "COUNTEREXAMPLE_LOG.md IV-19."),
              note="declared vacuous BEFORE the audit ran, not after"),
        Check(name="gate::pre_touching",
              predicate=lambda row: bool(row["pre_touching"]),
              positive={"pre_touching": True},
              negative={"pre_touching": False},
              note=("zero overlap volume with a non-empty intersection. The "
                    "surrogate's blind spot.")),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", default="final")
    args = parser.parse_args()

    campaign_path = RESULTS / f"CAMPAIGN_{args.partition.upper()}.json"
    gate_path = RESULTS / f"GATE_TABLE_{args.partition.upper()}.json"
    if not campaign_path.is_file():
        print(f"no campaign artifact at {campaign_path.relative_to(ROOT)}")
        return 1

    campaign = json.loads(campaign_path.read_text())
    rows = campaign["rows"]
    report = audit(state_checks(), rows)

    if gate_path.is_file():
        gate = json.loads(gate_path.read_text())
        gate_report = audit(gate_checks(), gate["rows"])
        report["checks"].update(gate_report["checks"])
        for key, value in gate_report["verdict_counts"].items():
            report["verdict_counts"][key] += value
        report["vacuous"] = sorted(set(report["vacuous"])
                                   | set(gate_report["vacuous"]))
        report["unverified"] = sorted(set(report["unverified"])
                                      | set(gate_report["unverified"]))
    else:
        report["gate_table"] = "not present; gate checks not audited"

    document = {
        "schema": "csia.independent_validation.vacuity_audit/1",
        "partition": args.partition,
        "source_campaign": str(campaign_path.relative_to(ROOT)),
        "n_rows": len(rows),
        **report,
    }
    out = RESULTS / f"VACUITY_AUDIT_{args.partition.upper()}.json"
    out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    print(f"wrote {out.relative_to(ROOT)}")
    width = max(len(name) for name in document["checks"])
    for name, entry in sorted(document["checks"].items()):
        rate = "n/a" if entry["rate"] is None else f"{entry['rate']:.4f}"
        print(f"  {name:<{width}}  {entry['verdict']:<22s} "
              f"fired {entry['fired']:>6d}/{entry['n']:<6d} rate {rate}")
    print()
    print("verdict counts:", json.dumps(document["verdict_counts"]))
    if document["vacuous"]:
        print("VACUOUS IN THIS ENVELOPE:", document["vacuous"])
    if document["unverified"]:
        print("UNVERIFIED (neither good nor bad zero):",
              document["unverified"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
