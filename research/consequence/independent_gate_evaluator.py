"""INDEPENDENT structural evaluator for the gate inventory.

WHAT INDEPENDENCE MEANS HERE, EXACTLY
--------------------------------------
This module imports the standard library only. It imports

    NOT  csia_consequence.gates   (the hand-written inventory)
    NOT  csia.runtime.online      (the implementation)
    NOT  csia anything at all

and a test asserts it by running it in a fresh interpreter and inspecting
`sys.modules`. It reads ONE input: the text of `csia/runtime/online.py`.

If it agreed with the inventory because it imported the inventory, the
agreement would prove nothing. That is the failure
`research/systems-paper/independent_checker.py` was written to avoid, and this
follows its precedent.

THE ARGUMENT IT IMPLEMENTS
--------------------------
`online.py` builds every evidence term as a `(lambda, gate)` pair and then
multiplies the gate by freshness:

    E = {key: (lam, gate * fresh[a] * fresh[b]) ...}
    P = {n:   (lam, gate * fresh[n]) ...}

So a gate closing is only *covered* by the freshness path when the gate
expression is itself a function of the same sensor's validity. This evaluator
parses the pre-freshness gate expression of each term and classifies it by
which symbols it mentions:

    mentions only literals (1.0, 0.2)     -> ALWAYS_OPEN or constant
    mentions gvalid                       -> coupled to GPS validity
    mentions armed_gate / speed_gate /
    tau / mag_ref_ready / fresh[other]    -> INDEPENDENT of its own freshness

It does not read the inventory's conclusions, and it reaches its own.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ONLINE = (pathlib.Path(__file__).resolve().parents[2]
          / "csia/runtime/online.py")

#: Symbols that make a gate a function of something OTHER than the protected
#: sensor's own freshness.
INDEPENDENT_SYMBOLS = ("armed_gate", "speed_gate", "tau >", "mag_ref_ready",
                       'fresh["motor_esc"]', "adapt_level")

#: Symbols that couple the gate to a sensor-validity signal the freshness path
#: also watches.
COUPLED_SYMBOLS = ("gvalid",)


def _tail_gate(text: str, start: int) -> str:
    """The last top-level element of the tuple beginning at `start`.

    Scans forward tracking bracket depth, so a comma inside a nested call is
    not mistaken for the separator before the gate. The first version split on
    the last comma in a regex slice, which mis-parsed every term whose value
    spanned lines and silently produced four UNPARSED verdicts. Depth tracking
    removes the guess.
    """
    # A right-hand side wrapped in parentheses -- `P["gps"] = (lam, gate)` --
    # puts its separators one level down. Descend into that wrapper first,
    # otherwise no top-level comma is ever seen and the term parses as empty.
    i = start
    while i < len(text) and text[i] in " \t":
        i += 1
    wrapped = i < len(text) and text[i] == "("
    if wrapped:
        i += 1
    depth = 0
    last_comma = None
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                break
        elif ch == "," and depth == 0:
            last_comma = i
        elif ch == ")" and depth < 0:
            break
        elif ch == "\n" and depth == 0 and not wrapped:
            break
        i += 1
    if last_comma is None:
        return ""
    return text[last_comma + 1:i].strip().rstrip(")").strip()


def _gate_expressions(text: str) -> dict:
    """Pull the trailing gate expression of every E[...] and P[...] term."""
    out = {}
    for prefix, rename in (("E", lambda k: k), ("P", lambda k: "phys_" + k)):
        pattern = re.compile(
            r'^\s*' + prefix + r'\["([a-z0-9_]+)"\]\s*=\s*', re.M)
        for match in pattern.finditer(text):
            key = match.group(1)
            expression = _tail_gate(text, match.end())
            if expression:
                out[rename(key)] = expression
    return out


def classify(expression: str) -> str:
    if any(sym in expression for sym in INDEPENDENT_SYMBOLS):
        return "FRESHNESS_INDEPENDENT"
    if any(sym in expression for sym in COUPLED_SYMBOLS):
        return "FRESHNESS_COUPLED"
    try:
        value = float(expression)
    except ValueError:
        return "UNPARSED"
    return "ALWAYS_OPEN" if value == 1.0 else "FRESHNESS_INDEPENDENT"


def evaluate() -> dict:
    text = ONLINE.read_text(encoding="utf-8")
    expressions = _gate_expressions(text)
    verdicts = {k: classify(v) for k, v in expressions.items()}

    # The withdrawal path is not an E/P gate; it is found by its own shape.
    withdrawal = bool(re.search(r"adapt_level\s*>\s*25", text))

    independent = sorted(k for k, v in verdicts.items()
                         if v == "FRESHNESS_INDEPENDENT")
    return {
        "schema": "csia.consequence.independent_gate_evaluation/1",
        "evidence_level": "SOURCE_ANALYSIS",
        "source": "csia/runtime/online.py",
        "imports": ["json", "pathlib", "re", "sys"],
        "terms_found": len(expressions),
        "expressions": expressions,
        "verdicts": verdicts,
        "freshness_independent": independent,
        "freshness_independent_count": len(independent),
        "withdrawal_path_present": withdrawal,
        "count_with_withdrawal": len(independent) + (1 if withdrawal else 0),
        "known_limitations": [
            "Two edge terms are assigned through a loop variable "
            "(`E[key] = ...` for velocity_gps_doppler_0 and _1) and are NOT "
            "matched by a literal-key pattern. They are absent from this "
            "evaluation rather than silently defaulted, and the inventory "
            "records them as gvalid-gated. An evaluator that guessed at them "
            "would be inventing evidence.",
            "This evaluator classifies gate EXPRESSIONS. It does not model "
            "control flow, so a gate that is unreachable in practice would "
            "still be classified by what it depends on.",
        ],
        "what_this_does_not_do": (
            "It does not decide whether a closure matters, or whether a fault "
            "can cause one. It classifies what each gate expression depends "
            "on. Consequence is a separate question at a higher evidence "
            "level."),
    }


if __name__ == "__main__":
    report = evaluate()
    json.dump(report, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
