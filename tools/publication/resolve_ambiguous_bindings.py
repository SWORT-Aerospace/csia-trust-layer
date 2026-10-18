"""Narrow the AMBIGUOUS prose literals using the section they appear in.

THE PROBLEM
-----------
`propose_prose_bindings.py` searches every artifact for a value matching a
printed literal, and reports AMBIGUOUS when several carry it. Twenty-seven
literals land there. A value alone cannot say which artifact it came from.

THE SECTION CAN, SOMETIMES
--------------------------
Each literal sits in a section of `main.tex` that is about one experiment,
and each experiment's artifacts live under a path that names it. Filtering
candidates to the section's own work-package narrows some of them to one.

WHAT THIS TOOL WILL NOT DO
--------------------------
It will not pick a winner because a winner is wanted. Three verdicts:

  RESOLVED_CANDIDATE   exactly one candidate survives the section filter,
                       and it is a PROPOSAL for a human to confirm
  STILL_AMBIGUOUS      several survive; the section does not decide it
  SPURIOUS_MATCH       the candidates share a NUMBER with the prose and
                       nothing else -- the token they matched on means
                       something different in the artifact

SPURIOUS_MATCH IS THE IMPORTANT ONE. `kappa(S) = 0.000` over eight
HYPOTHESIS classes matches `V2_COMPLEXITY.json` `/*/classes` = 0, which is
the number of PYTHON CLASSES in a source file. Both are "classes" and both
are 0.000. Binding them would be MX-013 again: that entry records two
tool-proposed bindings that were wrong, one binding a tick distance and one
the lower bound of a wider population.

NOTHING IS APPLIED. These bind into PAPER1_ARTIFACT_MAP.yaml, which the E1
freeze manifest hashes; applying them would break the freeze they are
recorded in. Every verdict below is a proposal for a deliberate re-freeze,
and each is hand-adjudicated in ADJUDICATION.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PAPER = os.path.join(ROOT, "papers", "csia_systems", "main.tex")

#: section title fragment -> the artifact path fragments that section's
#: numbers may legitimately come from. Written from the section headings,
#: not fitted to the candidates.
SECTION_SCOPE = {
    "self-occlusion": ("dual_admissibility", "self_occlusion", "maer"),
    "Gate closure frequency": ("wp_c6", "wp_c7", "physical_validation"),
    "glitch non-alarm": ("wp_c7", "wp_c8"),
    "Two detectors": ("wp_c8", "wp_c9"),
    "False-healthy exposure": ("wp_c9", "wp_c10", "false_healthy"),
    "Chatter resonance": ("wp_c10", "chatter"),
    "design rule": ("wp_c11", "design_rule"),
    "repair, measured": ("wp_c11", "repair"),
    "System under measurement": ("v1_1", "engineering", "physical_validation"),
    "Containment": ("physical_validation", "dual_admissibility"),
}

#: Tokens whose meaning in an artifact is unrelated to their meaning in the
#: prose. A candidate matched ONLY on one of these is a coincidence.
FALSE_FRIENDS = {
    "classes": ("V2_COMPLEXITY", "complexity"),
    "count": ("V2_COMPLEXITY", "complexity"),
    "lines": ("V2_COMPLEXITY", "complexity"),
}

#: HAND-ADJUDICATED. Every entry below was read against the prose and the
#: artifact by a person. `verdict` is the human's, not the tool's.
ADJUDICATION = {
    "0.678": {
        "verdict": "CONFIRMED",
        "binding": ("research/wp_c8/results/response_surface.json"
                    "#/evidence_floor_confirmation/observed_range/0"),
        "why": ("prose: 'the measured floor ranges 0.678 to 0.700'. The "
                "artifact's observed_range[0] is 0.6785, under a key named "
                "evidence_floor_confirmation, in the section that derives "
                "the evidence floor. The lower end matches exactly.")},
    "0.700": {
        "verdict": "REVIEW_PROSE_AND_ARTIFACT_DISAGREE",
        "why": ("THE UPPER END DOES NOT COME FROM THE SAME RANGE. The prose "
                "says the measured floor ranges 0.678 TO 0.700, but the "
                "artifact's observed_range is [0.6785, 0.9422] -- its upper "
                "end is 0.9422, not 0.700. 0.700 is the SATURATION value: "
                "`predicted_e_f` = 0.7 algebraically, and the 8 of 21 cells "
                "whose residual saturates land on 0.7000. So the sentence "
                "pairs a measured minimum with a saturation value and calls "
                "the pair a measured range. "
                "This is not obviously wrong -- 0.7000 IS measured in the "
                "saturated cells, and the paper states that separately -- "
                "but the artifact stores no scalar for 'measured floor "
                "upper end', so there is nothing to bind to. FLAGGED FOR A "
                "HUMAN, NOT BOUND. Binding the lower bound of a wider "
                "population is exactly the error MX-013 records.")},
    "0.717": {
        "verdict": "CONFIRMED",
        "binding": ("research/wp_c7/results/glitch_mechanism.json"
                    "#/ramp_versus_step/1/min_trust"),
        "why": ("prose: 'a 5, 20 or 60 s ramp ... minimum trust 0.717 to "
                "0.723 and 104 to 168 ticks at the floor'. ramp_versus_step "
                "holds exactly those three ramps with min_trust 0.71813, "
                "0.71686, 0.72273 and floor_ticks 104, 168, 139. 0.71686 "
                "is the minimum, which rounds to 0.717. The TICK range "
                "corroborates it independently: 104 and 168 are the same "
                "three entries' min and max.")},
    "0.723": {
        "verdict": "CONFIRMED",
        "binding": ("research/wp_c7/results/glitch_mechanism.json"
                    "#/ramp_versus_step/2/min_trust"),
        "why": ("the maximum of the same three ramps, 0.72273 -> 0.723. The "
                "competing candidate /per_run/9/layer/... carries the same "
                "value but is one run rather than the ramp comparison the "
                "sentence is about.")},
    "0.735": {
        "verdict": "DUPLICATE_POINTER",
        "why": ("both surviving candidates are 0.735263 in the SAME "
                "artifact for the SAME grid cell 16 -- "
                "/escalation_boundary/grid_classification/16/min_trust and "
                "/per_run/grid/16/layer/min_trust. This is not two possible "
                "sources, it is one quantity recorded twice. A binding "
                "should cite the primary record; which of the two is "
                "primary is a question for whoever wrote the artifact.")},
    "0.000": {
        "verdict": "SPURIOUS_MATCH",
        "why": ("kappa(S) over EIGHT HYPOTHESIS CLASSES. Every candidate is "
                "V2_COMPLEXITY.json '/*/classes' -- the number of PYTHON "
                "CLASSES defined in a source file, which is 0 for an "
                "__init__.py. Same word, unrelated quantity, and the value "
                "0.000 is a coincidence of an exactly-zero kappa meeting an "
                "empty module.")},
    "0.143": {
        "verdict": "SPURIOUS_MATCH",
        "why": ("kappa(S_eff) over seven classes, same false friend as "
                "0.000. The prose itself says this one is ALREADY BOUND in "
                "the map as S09, so no new binding is needed.")},
    "1.000": {
        "verdict": "STILL_AMBIGUOUS",
        "why": ("1.000 is the most common value in this repository -- a "
                "saturated probability, a full gate weight, a unit "
                "coefficient. Section context does not narrow it and a "
                "value this common should probably never be auto-bound.")},
    "3.0": {
        "verdict": "ALREADY_STATED",
        "why": ("the pre-fault gate weight sum on ArduPilot. The prose says "
                "it is stated in the claim table, which is where it is "
                "sourced; a second binding would create two records of one "
                "number that can disagree.")},
}


def _sections() -> list:
    with open(PAPER, encoding="utf-8") as fh:
        text = fh.read()
    out = []
    for m in re.finditer(r"\\section\{([^}]*)\}", text):
        out.append((m.start(), m.group(1)))
    return out


def _section_for(context: str) -> str | None:
    """Which section a context snippet falls in."""
    with open(PAPER, encoding="utf-8") as fh:
        text = fh.read()
    probe = context.strip()[:40]
    if not probe:
        return None
    idx = text.find(probe)
    if idx < 0:
        # LaTeX escaping differs between the proposer's context and the
        # source; fall back to the longest run of plain words.
        words = [w for w in re.findall(r"[A-Za-z]{5,}", context)][:4]
        if not words:
            return None
        idx = text.find(" ".join(words))
        if idx < 0:
            for w in words:
                idx = text.find(w)
                if idx >= 0:
                    break
    if idx < 0:
        return None
    current = None
    for pos, title in _sections():
        if pos <= idx:
            current = title
        else:
            break
    return current


def _scope_for(section: str | None) -> tuple:
    if not section:
        return ()
    for fragment, scope in SECTION_SCOPE.items():
        if fragment.lower() in section.lower():
            return scope
    return ()


def _is_false_friend(candidate: dict) -> bool:
    shared = set(candidate.get("shared_tokens") or ())
    artifact = candidate.get("artifact", "")
    for token, markers in FALSE_FRIENDS.items():
        if shared == {token} and any(m in artifact for m in markers):
            return True
    return False


def resolve(proposal_report: dict) -> dict:
    rows = []
    for item in proposal_report.get("ambiguous", []):
        literal = item["literal"]
        section = _section_for(item.get("context", ""))
        scope = _scope_for(section)
        candidates = item.get("candidates") or []

        spurious = [c for c in candidates if _is_false_friend(c)]
        real = [c for c in candidates if not _is_false_friend(c)]
        in_scope = [c for c in real
                    if scope and any(s in c.get("artifact", "")
                                     for s in scope)]

        if not real:
            verdict = "SPURIOUS_MATCH"
            surviving = []
        elif scope and len(in_scope) == 1:
            verdict = "RESOLVED_CANDIDATE"
            surviving = in_scope
        elif scope and in_scope:
            verdict = "STILL_AMBIGUOUS"
            surviving = in_scope
        else:
            verdict = "STILL_AMBIGUOUS"
            surviving = real

        row = {
            "literal": literal,
            "why": item.get("why"),
            "section": section,
            "section_scope": list(scope),
            "candidates_before": len(candidates),
            "candidates_after_section_filter": len(surviving),
            "spurious_candidates_dropped": len(spurious),
            "tool_verdict": verdict,
            "surviving": surviving[:4],
        }
        human = ADJUDICATION.get(literal)
        if human:
            row["human_verdict"] = human["verdict"]
            row["human_why"] = human["why"]
        rows.append(row)

    counts: dict = {}
    for row in rows:
        key = row.get("human_verdict") or row["tool_verdict"]
        counts[key] = counts.get(key, 0) + 1

    return {
        "schema": "csia.publication.ambiguous_resolution/1",
        "literals": rows,
        "counts": counts,
        "nothing_is_applied": (
            "these bind into papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml, "
            "which the E1 freeze manifest hashes. Applying them would break "
            "the freeze they are recorded in. Merge at a deliberate "
            "re-freeze."),
        "a_resolved_candidate_is_a_proposal": (
            "RESOLVED_CANDIDATE means the section filter left exactly one "
            "candidate. It is a PROPOSAL for a human to confirm, not a "
            "binding. MX-013 records that of five earlier tool proposals, "
            "TWO were wrong."),
        "spurious_is_a_real_answer": (
            "SPURIOUS_MATCH means the candidates share a number with the "
            "prose and nothing else. Reporting that is more useful than "
            "picking the least implausible one."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    proc = subprocess.run(
        [sys.executable,
         os.path.join(ROOT, "tools", "publication",
                      "propose_prose_bindings.py")],
        capture_output=True, text=True, cwd=ROOT, timeout=1800)
    text = proc.stdout
    report = json.loads(text[text.index("{"):text.rindex("}") + 1])

    resolved = resolve(report)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(resolved, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"wrote {args.out}")

    print(json.dumps(resolved["counts"], indent=2, sort_keys=True))
    for row in resolved["literals"]:
        verdict = row.get("human_verdict") or row["tool_verdict"]
        print(f"  {row['literal']:>8}  {verdict:20} "
              f"{row['candidates_before']:>2} -> "
              f"{row['candidates_after_section_filter']:<2} "
              f"[{(row['section'] or '?')[:34]}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
