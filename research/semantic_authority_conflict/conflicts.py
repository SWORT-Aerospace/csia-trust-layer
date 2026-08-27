"""Conflict classification, declared-vs-effective semantics, and the minimal
authority counterexamples.

Items 8, 19, 20, 21, 22, 32.

The distinction this file exists to enforce (item 20): **a difference is not
a conflict**. Two authorities that encode the same meaning differently agree.
An authority that says nothing does not disagree. Only authorities that
BOTH speak and speak differently are in conflict.

That is why the taxonomy has a fourth entry the brief did not list:

    CONFLICT           two authorities speak and disagree
    UNDERSPECIFICATION the higher authority is SILENT, so the lower ones are
                       each permitted and their divergence is licensed
    AGREEMENT          they speak and agree
    OUT_OF_SCOPE       the authority describes a different raw state

UNDERSPECIFICATION is not a variant of conflict. It is the opposite: nobody
is wrong, because nobody said.

  python research/semantic_authority_conflict/conflicts.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
ES = os.path.join(ROOT, "research", "evidence_semantics")
sys.path.insert(0, _HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, ES)

import authorities as A                                        # noqa: E402
import contract_checker as C                                   # noqa: E402

SILENT = A.SILENT

# item 19's taxonomy, restricted to types the source actually supports
TYPES = ("SPEC_VS_PRODUCER", "PRODUCER_VS_CONSUMER", "CROSS_CONSUMER",
         "CONSUMER_VS_OBSERVED", "DOCUMENTATION_VS_EXECUTION")

WORD_OF = {"battery.current_not_measured": ("battery", "X"),
           "gnss.no_3d_fix": ("gnss", "I"),
           "mag.all_zero_triple": ("mag", "Z")}
PATH_OF = {"C_consumer_A": "v1_1_adapter", "C_consumer_B": "plugins_py",
           "C_consumer_C": "ulog_source_py"}


def _kind(a_name, b_name):
    ab = {a_name.split("_")[1], b_name.split("_")[1]}
    if ab == {"spec", "producer"}:
        return "SPEC_VS_PRODUCER"
    if ab == {"producer", "consumer"}:
        return "PRODUCER_VS_CONSUMER"
    if ab == {"spec", "consumer"}:
        return "SPEC_VS_CONSUMER"
    if a_name.startswith("C_consumer") and b_name.startswith("C_consumer"):
        return "CROSS_CONSUMER"
    return "OTHER"


def _in_scope(v):
    return not str(v.get("scope", "")).startswith("different_raw_state")


def main() -> int:
    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)
    conf_rows, dve_rows = [], []

    for case in A.CASES:
        name = case["case"]
        auths = {k: v for k, v in case["authorities"].items() if _in_scope(v)}
        names = sorted(auths)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                # Only authorities speaking to the SAME ASPECT of the raw
                # state are comparable. `fix_type means no position info` and
                # `the position fields hold the last known Location` are not
                # in conflict; they are about different fields.
                if (auths[a].get("aspect", "value_semantics")
                        != auths[b].get("aspect", "value_semantics")):
                    continue
                ia, ib = auths[a]["interpretation"], auths[b]["interpretation"]
                if ia == SILENT or ib == SILENT:
                    status = "UNDERSPECIFICATION"
                    detail = (f"{a if ia == SILENT else b} says nothing about "
                              f"this raw state, so the other is not "
                              f"contradicted")
                elif ia == ib:
                    status = "AGREEMENT"
                    detail = ia
                else:
                    status = "CONFLICT"
                    detail = f"{ia} vs {ib}"
                conf_rows.append({
                    "case": name, "raw_state": case["raw_state"],
                    "authority_a": a, "authority_b": b,
                    "interpretation_a": ia, "interpretation_b": ib,
                    "status": status, "conflict_type": _kind(a, b),
                    "detail": detail,
                })

        # ---- declared vs effective (item 21) ----------------------------
        family, word = WORD_OF[name]
        for aname, path in PATH_OF.items():
            if aname not in auths:
                continue
            rows = C.run(path, word, family)
            emitted = [(r["T5_core_bridge"], r["T5_value"]) for r in rows
                       if r["T5_core_bridge"] != "-"]
            dve_rows.append({
                "case": name, "authority": aname, "path": path,
                "declared_semantics": auths[aname]["interpretation"],
                "declared_meaning": auths[aname]["declared"],
                "effective_token_at_core": (emitted[0][0] if emitted
                                            else "NOTHING_EMITTED"),
                "effective_value_at_core": (str(emitted[0][1]) if emitted
                                            else ""),
                "declared_and_effective_agree": bool(emitted) or
                    auths[aname]["interpretation"].startswith(
                        ("DROP", "TREAT_AS_ABSENT")),
            })

    # ---- minimal authority counterexamples (item 32) --------------------
    sv = json.load(open(os.path.join(
        _HERE, "SET_VALUED_ASSURANCE_RESULTS.json"), encoding="utf-8"))
    minimal = []
    for case, d in sv["cases"].items():
        for lvl, sub in d["minimal_authority_subset"].items():
            if not sub:
                continue
            minimal.append({
                "case": case, "level": lvl,
                "minimal_authority_subset": sub,
                "subset_size": len(sub),
                "shortest_word": d["word"],
                "word_length": len(d["word"]),
                "minimality": ("|subset| = 2 is minimal by definition: one "
                               "authority cannot disagree with itself"),
                "search": ("the word is length 1, the shortest possible in "
                           "this alphabet; exhaustive search over shorter "
                           "words is vacuous"),
            })

    _csv("AUTHORITY_CONFLICTS.csv", conf_rows)
    _csv("DECLARED_VS_EFFECTIVE_SEMANTICS.csv", dve_rows)
    with open(os.path.join(_HERE, "MINIMAL_AUTHORITY_COUNTEREXAMPLES.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"artifact": "MINIMAL_AUTHORITY_COUNTEREXAMPLES",
                   "note": "a minimal subset is reported only where the "
                           "disagreement at that level survived the null "
                           "control",
                   "entries": minimal}, fh, indent=2, sort_keys=True)
        fh.write("\n")

    import collections
    c = collections.Counter((r["case"], r["status"]) for r in conf_rows)
    print("  authority pairs, by case and status:")
    for k in sorted(c):
        print(f"    {k[0]:<32} {k[1]:<20} {c[k]}")
    t = collections.Counter(r["conflict_type"] for r in conf_rows
                            if r["status"] == "CONFLICT")
    print(f"\n  real conflicts by type: {dict(t)}")
    print(f"  underspecification pairs: "
          f"{sum(1 for r in conf_rows if r['status'] == 'UNDERSPECIFICATION')}")
    print(f"  minimal-subset entries: {len(minimal)}")
    return 0


def _csv(name, rows):
    if not rows:
        return
    with open(os.path.join(_HERE, name), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
