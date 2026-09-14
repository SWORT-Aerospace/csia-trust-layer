"""Render the follow-up campaign's markdown report from its JSON artifact.

Every number in ``PAIRED_DESIGN_FOLLOWUP.md`` is printed by this script from
``FOLLOWUP_<PARTITION>.json``. None is typed by a person reading a table, which
is the failure mode this phase already has four entries for in
``COUNTEREXAMPLE_LOG.md``.

    python tools/research/iv_followup_report.py --partition final

The script renders whatever the artifact says, including a rejection. It has no
branch that suppresses an unwelcome verdict, and the verdict strings it prints
are the ones the campaign computed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"

SOURCES = ("paired_crn", "independent_seed", "independent_window")


def _fmt(value, spec: str = ".4e") -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return f"`{value}`"
    return format(value, spec)


def _arms_in(block: Dict) -> List[str]:
    seen: List[str] = []
    for key in block["by_arm_and_drift"]:
        arm = key.rsplit("/", 1)[0]
        if arm not in seen:
            seen.append(arm)
    return seen


def render(document: Dict) -> str:
    reduction = document["reduction"]
    out: List[str] = []
    w = out.append

    w("# The paired design, broken on purpose")
    w("")
    w("**GENERATED** by `tools/research/iv_followup_report.py` from")
    w(f"`results/FOLLOWUP_{document['partition'].upper()}.json`. Edit the")
    w("script, not this file.")
    w("")
    w("Preregistered in `PREREGISTRATION_AMENDMENT_4.md`, written and")
    w("committed before the first follow-up seed was drawn. This campaign")
    w("does not touch the sealed phase-one result, which stands as it is.")
    w("")

    w("## What ran")
    w("")
    w("| field | value |")
    w("|---|---|")
    w(f"| partition | `{document['partition']}`, "
      f"{len(document['seeds'])} seeds |")
    w(f"| partition manifest | `{document['partition_manifest_sha256']}` |")
    w(f"| phase-one manifest (untouched) | "
      f"`{document['phase_one_partition_manifest_sha256']}` |")
    w(f"| arms | {len(document['arms'])} deployable "
      f"({', '.join('`' + a + '`' for a in document['arms'])}) |")
    w(f"| arms omitted | "
      f"{', '.join('`' + a + '`' for a in document['arms_omitted'])} |")
    w(f"| reference probe | `{document['reference_action']}` |")
    w(f"| rows | {document['n_rows']} |")
    w(f"| plant runs | {document['plant_simulations']} |")
    w(f"| wall clock | {document['elapsed_s']:.0f} s |")
    w("")
    w(f"{document['what_this_is_not']}")
    w("")
    w(f"**Regret.** {reduction['regret']}")
    w("")

    inv = reduction["point_metric_invariance"]
    w("## The factor moves one thing")
    w("")
    w("`AE_R` scores the fault window alone and never reads the baseline, so")
    w("the three levels must agree on it exactly. If they did not, the factor")
    w("would be contaminating something it was not supposed to touch and")
    w("every verdict below would be void.")
    w("")
    w(f"* matched groups compared: **{inv['matched_groups_compared']}**")
    w(f"* worst `AE_R` spread across levels: "
      f"**{_fmt(inv['max_ae_r_spread_across_levels'])}**")
    w(f"* identical everywhere: **{_fmt(inv['identical_everywhere'])}**")
    if inv["first_offenders"]:
        w("")
        w("Offending cells (first five):")
        w("")
        for offender in inv["first_offenders"]:
            w(f"* `{offender['cell']}` → {offender['ae_r']}")
    w("")

    w("## The cancellation, level by level")
    w("")
    w("| nominal source | rows | median &#124;e_ΔR&#124; | resolved "
      "(change) | false certs (change) | false certs (point) |")
    w("|---|---|---|---|---|---|")
    for source in SOURCES:
        block = reduction["by_nominal_source"][source]
        w(f"| `{source}` | {block['n']} | "
          f"{_fmt(block['median_abs_e_delta_r'])} | "
          f"{_fmt(block['resolved_fraction_change'], '.4f')} | "
          f"{len(block['false_certificates_change_metric'])} | "
          f"{len(block['false_certificates_point_metric'])} |")
    w("")

    paired = reduction["by_nominal_source"]["paired_crn"][
        "median_abs_e_delta_r"]
    window = reduction["by_nominal_source"]["independent_window"][
        "median_abs_e_delta_r"]
    if paired and window:
        w(f"The deployment-faithful level is **{window / paired:.1f}×** the")
        w("paired control on median |e_ΔR|. The paired figure is not a")
        w("measurement of the estimator; it is the residual of an identity")
        w("that holds because the two windows share a noise draw.")
        w("")

    for name, key in (
            ("H8 — the saturation is a design artifact",
             "H8_saturation_is_a_design_artifact"),
            ("H9 — the change metric recovers plant structure",
             "H9_change_metric_recovers_plant_structure"),
            ("H10 — ordering is preserved", "H10_ordering_is_preserved")):
        block = reduction[key]
        w(f"## {name}")
        w("")
        w(f"> {block['statement']}")
        w("")
        w(f"**Verdict: {block['verdict']}.**")
        w("")
        w(f"Predeclared falsifier: {block['falsifier']}.")
        w("")
        if key.startswith("H8"):
            w("| nominal source | A_s spread across arms | exceeds "
              f"{block['threshold']} |")
            w("|---|---|---|")
            for source in SOURCES:
                cut = block["by_source"][source]
                w(f"| `{source}` | {_fmt(cut['spread'], '.4f')} | "
                  f"{_fmt(cut['exceeds_threshold'])} |")
            w("")
            w("Per-arm `A_s` on the change metric:")
            w("")
            arms = list(block["by_source"]["paired_crn"]["A_s_by_arm"])
            w("| arm | " + " | ".join(f"`{s}`" for s in SOURCES) + " |")
            w("|---|" + "---|" * len(SOURCES))
            for arm in arms:
                cells = " | ".join(
                    _fmt(block["by_source"][s]["A_s_by_arm"][arm], ".4f")
                    for s in SOURCES)
                w(f"| `{arm}` | {cells} |")
            w("")
        if key.startswith("H9"):
            w("| nominal source | Q0 | Q1 | Q2 | max/min |")
            w("|---|---|---|---|---|")
            for source in SOURCES:
                cut = block["by_source"][source]
                medians = cut["median_abs_e_delta_r"]
                w(f"| `{source}` | " + " | ".join(
                    _fmt(medians[p]) for p in ("Q0", "Q1", "Q2"))
                  + f" | {_fmt(cut['ratio'], '.2f')} |")
            w("")
            w(f"Control precondition (paired plants agree to within "
              f"{block['control_tolerance']:.0%}): "
              f"**{_fmt(block['control_precondition_holds'])}**.")
            w("")
        if key.startswith("H10"):
            rho = block["spearman_rho"]
            w(f"Spearman ρ = **{_fmt(rho, '.4f')}** against a floor of "
              f"{block['rho_threshold']}.")
            w("")
            w("| arm | A_s change, `independent_window` | A_s point, "
              "`paired_crn` |")
            w("|---|---|---|")
            for arm in block["arms"]:
                w(f"| `{arm}` | "
                  f"{_fmt(block['A_s_change_independent_window'][arm], '.4f')}"
                  f" | {_fmt(block['A_s_point_paired_crn'][arm], '.4f')} |")
            w("")
            w(f"If rejected: {block['if_rejected']}.")
            w("")

    w("## What this does not establish")
    w("")
    w("* Nothing here is a novelty claim. The construction being measured is")
    w("  an experimental-design property, and finding it is not a")
    w("  contribution to anybody's literature.")
    w("* Nothing here revises a phase-one conclusion. H1–H7 and the two-gate")
    w("  claim were settled on the sealed partition and are not reopened.")
    w("* No regret, no ceiling, no comparison to a sealed-campaign regret")
    w("  figure. The ceilings did not run.")
    w("* Simulator only. Synthetic pack, no chemistry, no hardware")
    w("  representativeness, no certified safety artifact, no promotion.")
    w("")
    return "\n".join(out) + "\n"


def main(partition: str, out_name: Optional[str]) -> int:
    path = RESULTS / f"FOLLOWUP_{partition.upper()}.json"
    if not path.is_file():
        print(f"no artifact at {path.relative_to(ROOT)}; run the campaign "
              f"first", file=sys.stderr)
        return 1
    document = json.loads(path.read_text())
    target = BASE / (out_name or "PAIRED_DESIGN_FOLLOWUP.md")
    target.write_text(render(document), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    raise SystemExit(main(args.partition, args.out))
