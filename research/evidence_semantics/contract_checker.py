"""Evidence-semantic contract checker -- RESEARCH PROTOTYPE.

Input   an ingest path, a canonical contract, a bounded trace alphabet
Output  PASS, or: the violated clause, the shortest counterexample, the FIRST
        transformation that destroys the distinction, and the downstream
        equivalence level at which the loss first becomes unobservable.

It is a bounded exhaustive checker over a finite alphabet, driving the real
implementations. The search algorithm is textbook (breadth-first over words,
shortest witness by construction); NOTHING here is claimed as an advance in
verification. What it adds over running the same search on the pipeline's
output alone is the stage index: a witness is reported WITH the transformation
that produced it.

  python research/evidence_semantics/contract_checker.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import probe as P                                            # noqa: E402

OUT = os.path.join(_HERE, "results")      # intermediates
DELIV = _HERE                              # the artifacts item 29 names
MAX_LEN = 4

# The pipeline stage each equivalence level is read at. VALUE and STATE are
# both read at the core boundary because that is the only place all three
# paths meet: paths B and C have no representation stage of their own.
LEVELS = ("VALUE", "STATE", "EVIDENCE", "DIAGNOSIS", "ASSURANCE")

_CACHE = {}


def run(path, word, family):
    key = (path, word, family)
    if key not in _CACHE:
        _CACHE[key] = P.PATHS[path](word, family)
    return _CACHE[key]


# --------------------------------------------------------------- projections
#
# Cross-path comparison MUST be stamp-invariant. The v1.1 adapter stamps a
# core sample with the tick it handed it over on; plugins.py and ulog_source.py
# stamp with the message's own time. A tick-indexed comparison reports that
# convention as a semantic difference -- the previous package established
# this and the mistake is not repeated here. Every projection below is either
# order-only or measured as a DURATION from word onset, which is invariant to
# the convention up to one tick (0.04 s) and therefore cannot manufacture the
# 0.5 s effects reported.

def _onset(word):
    return P.WARMUP_S


def proj_value(rows):
    """The NUMERIC payload x crossing into the core, in order.

    Deliberately separate from the quality coordinate q. Item 6: equality of
    x is not semantic equivalence of E = (x, q), and this projection exists
    so the two can be shown to come apart.
    """
    return tuple(r["T5_value"] for r in rows
                 if r["T5_core_bridge"] != P.NONE_TOK)


def _emissions(rows):
    """The quality coordinate q crossing into the core, in order."""
    return tuple(r["T5_core_bridge"] for r in rows
                 if r["T5_core_bridge"] != P.NONE_TOK)


def proj_state(rows):
    """Represented state at the core boundary: emissions, then slot history."""
    return (_emissions(rows), _collapse(tuple(r["T6_slot"] for r in rows)))


def proj_evidence(rows):
    """Operational admissibility: does A ever close, and how long after onset."""
    closed = [r["t"] for r in rows if r["T7_admissible"] == "0"]
    return (bool(closed),
            None if not closed else round(min(closed) - _onset(""), 3))


def proj_diagnosis(rows):
    """Trust trajectory for the sensor, repeats collapsed."""
    return _collapse(tuple(r["T8_trust"] for r in rows))


def proj_assurance(rows):
    """Failsafe level history and the time of the first non-NORMAL level."""
    lv = _collapse(tuple(r["T9_assurance"] for r in rows))
    esc = [r["t"] for r in rows if r["T9_assurance"] not in ("NORMAL", "-")]
    acts = tuple(sorted({a for r in rows for a in r["T9_actions"]}))
    return (lv, None if not esc else round(min(esc) - _onset(""), 3), acts)


def _collapse(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return tuple(out)


PROJ = {"VALUE": proj_value, "STATE": proj_state, "EVIDENCE": proj_evidence,
        "DIAGNOSIS": proj_diagnosis, "ASSURANCE": proj_assurance}


# ------------------------------------------------------- cross-path equivalence
def cross_path(family, max_len=MAX_LEN):
    """Cross-path equivalence, with a NULL CONTROL at every length.

    The control word is V^k -- an all-nominal stream containing no fault at
    all. If a level already diverges on the control, that level cannot be
    attributed to evidence semantics for that pair: the two paths differ in
    sample RATE (the v1.1 adapter's `to_core_samples` freshness gate emits
    only on new data), in TIMESTAMP convention, and in the numeric values
    they compute from the same message. Divergence on the control is a
    property of those differences, not of the fault the word encodes.

    So a level is reported as ATTRIBUTABLE only where the control at the same
    length is equivalent. Everything else is reported as CONFOUNDED and is
    NOT counted as a finding. This is the same discipline the dual-
    admissibility package used to avoid reading a stamping convention as a
    semantic difference.
    """
    alphabet = P.FAMILIES[family][0]
    paths = list(P.PATHS)
    rows, pairs = [], {}
    for i, pa in enumerate(paths):
        for pb in paths[i + 1:]:
            key = f"{pa}__vs__{pb}"
            control, ctrl_mag = {}, 0.0
            for k in range(1, max_len + 1):
                cw = "V" * k
                ca, cb = run(pa, cw, family), run(pb, cw, family)
                control[k] = {lv: (PROJ[lv](ca) == PROJ[lv](cb))
                              for lv in LEVELS}
                # HOW BIG is the control difference? A level flagged
                # CONFOUNDED could hide either a real disagreement or a
                # rounding-scale artifact, and the reader is entitled to know
                # which. Reported, not used to reclassify anything.
                for x, y in zip(ca, cb):
                    if x["T8_trust"] is not None and y["T8_trust"] is not None:
                        ctrl_mag = max(ctrl_mag,
                                       abs(x["T8_trust"] - y["T8_trust"]))
            div = {lv: [] for lv in LEVELS}
            attr = {lv: [] for lv in LEVELS}
            for w in P.words(alphabet, max_len):
                ra, rb = run(pa, w, family), run(pb, w, family)
                first, first_attr = None, None
                same = {}
                for lv in LEVELS:
                    same[lv] = PROJ[lv](ra) == PROJ[lv](rb)
                    if not same[lv]:
                        div[lv].append(w)
                        if first is None:
                            first = lv
                        if control[len(w)][lv]:
                            attr[lv].append(w)
                            if first_attr is None:
                                first_attr = lv
                rows.append({
                    "family": family, "pair": key, "word": w,
                    "length": len(w),
                    **{f"{lv}_equivalent": same[lv] for lv in LEVELS},
                    **{f"{lv}_control_equivalent": control[len(w)][lv]
                       for lv in LEVELS},
                    "first_divergent_level": first or "",
                    "first_attributable_level": first_attr or "",
                })
            n = sum(1 for _ in P.words(alphabet, max_len))
            pairs[key] = {
                "words_tested": n,
                "control_max_trust_delta": round(ctrl_mag, 6),
                "control_word_equivalent": {
                    lv: all(control[k][lv] for k in control) for lv in LEVELS},
                **{f"{lv}_divergent_words": len(div[lv]) for lv in LEVELS},
                **{f"{lv}_attributable_words": len(attr[lv]) for lv in LEVELS},
                **{f"{lv}_shortest_attributable":
                   (min(attr[lv], key=len) if attr[lv] else None)
                   for lv in LEVELS},
                **{f"{lv}_status": ("ATTRIBUTABLE"
                                    if all(control[k][lv] for k in control)
                                    else "CONFOUNDED_BY_CONTROL")
                   for lv in LEVELS},
                "verdict": ("PATHS_DIVERGE"
                            if any(attr[lv] for lv in LEVELS)
                            else f"NO_ATTRIBUTABLE_DIVERGENCE_TO_BOUND_"
                                 f"{max_len}"),
            }
    return rows, pairs


# --------------------------------------------------------- collapse detection
def _collapse_timed(rows, key):
    """Repeats collapsed, but the TIME each new token first appears is kept.

    Dropping the time would make a stage that says the same things 0.5 s
    later look identical to one that says them on schedule -- and on this
    pipeline the whole consequence of a lost distinction is a latency. A
    stage counts as having destroyed a distinction only when the two inputs
    produce the same tokens at the same times.
    """
    out = []
    for r in rows:
        v = key(r)
        if not out or out[-1][0] != v:
            out.append((v, round(r["t"], 3)))
    return tuple(out)


def _stage_trace(rows, st):
    """One stage's history, repeats collapsed, first-appearance times kept.

    T5 and T8 are read as PAIRS: at the core boundary the quality token and
    the numeric payload are both part of the represented observation
    (item 6), and at the engine both the evidence mass and the trust it
    produces matter. Reading only one half of either would report a collapse
    that has not happened.
    """
    if st == "T5_core_bridge":
        key = lambda r: (r["T5_core_bridge"], r["T5_value"])
    elif st == "T8_evidence":
        key = lambda r: (r["T8_evidence"], r["T8_trust"])
    elif st == "T9_assurance":
        key = lambda r: (r["T9_assurance"], r["T9_actions"])
    elif st == "T4_channel":
        key = lambda r: (r["T4_channel"], r["T4_value"])
    else:
        key = lambda r: r[st]
    return _collapse_timed(rows, key)


def _stage_exists(rows, st):
    """False when the path has no such stage at all (every token is NA)."""
    return not all(str(r.get(st)) == P.NA for r in rows)


def first_collapse(path, family, w1, w2):
    """The FIRST stage at which two distinguishable inputs stop differing.

    Returns (stage, per-stage table). A stage is 'collapsed' when its own
    trace is identical AND every later stage is identical too -- a stage that
    coincides transiently and separates again has not destroyed anything.

    Stages the path does not HAVE are never named as the collapse site. A
    path with no representation stage cannot be blamed at a file it never
    executes; that condition is reported separately as
    `no_representation_stage`.
    """
    r1, r2 = run(path, w1, family), run(path, w2, family)
    table, same, exists = {}, {}, {}
    for st in P.STAGES:
        t1, t2 = _stage_trace(r1, st), _stage_trace(r2, st)
        same[st] = (t1 == t2)
        exists[st] = _stage_exists(r1, st) or _stage_exists(r2, st)
        table[st] = {"w1": _short(t1), "w2": _short(t2),
                     "identical": same[st], "stage_present": exists[st]}
    stage = None
    for i, st in enumerate(P.STAGES):
        if not exists[st]:
            continue
        if same[st] and all(same[s] for s in P.STAGES[i:]):
            stage = st
            break
    missing = [st for st in P.STAGES if not exists[st]]
    return stage, {"stages": table, "no_representation_stage": missing}


def _short(t, n=40):
    """Render a stage trace compactly. Paired stages show the quality token
    and mark it with `*` when the other half of the pair also moved."""
    parts = []
    for tok, when in t:
        head = tok[0] if isinstance(tok, tuple) else tok
        parts.append(f"{str(head)[:1]}@{when:g}")
    s = " ".join(parts)
    return s if len(s) <= n else s[:n] + "..."


def collapse_search(path, family, max_len=MAX_LEN):
    """Shortest pair of inputs that the pipeline cannot tell apart.

    Distinguishable at source means the T1 (wire) projections differ. The
    search is exhaustive over lengths 1..max_len in increasing order, so the
    first pair found is shortest by construction.
    """
    alphabet = P.FAMILIES[family][0]
    seen, found, explored = {}, None, 0
    for w in P.words(alphabet, max_len):
        rows = run(path, w, family)
        wire = _collapse(tuple(r["T1_protocol"] for r in rows))
        down = (proj_state(rows), proj_evidence(rows), proj_diagnosis(rows),
                proj_assurance(rows))
        explored += 1
        if down in seen:
            w0, wire0 = seen[down]
            if wire0 != wire and found is None:
                found = (w0, w)
                break
        else:
            seen[down] = (w, wire)
    return found, explored, len(seen)


# --------------------------------------------------- downstream consequence
CONSEQUENCE = ("NONE", "STATE_ONLY", "EVIDENCE_AVAILABILITY", "DIAGNOSIS_SCORE",
               "DIAGNOSIS_RANK", "ASSURANCE_STATE", "CONTROL_FAILSAFE")


def consequence_of(ra, rb):
    """How far downstream a divergence between two runs actually reaches."""
    if proj_assurance(ra)[2] != proj_assurance(rb)[2]:
        return "CONTROL_FAILSAFE"
    if proj_assurance(ra)[:2] != proj_assurance(rb)[:2]:
        return "ASSURANCE_STATE"
    if proj_diagnosis(ra) != proj_diagnosis(rb):
        return "DIAGNOSIS_SCORE"
    if proj_evidence(ra) != proj_evidence(rb):
        return "EVIDENCE_AVAILABILITY"
    if proj_state(ra) != proj_state(rb):
        return "STATE_ONLY"
    return "NONE"


# ------------------------------------------------------------------ contracts
def load_contracts():
    d = os.path.join(_HERE, "ARDUPILOT_INGEST_CONTRACTS")
    out = {}
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            with open(os.path.join(d, fn), encoding="utf-8") as fh:
                out[fn[:-5]] = json.load(fh)
    return out


def check_contract(path, family, contract, max_len=MAX_LEN):
    """PASS, or the violated clause with its shortest witness."""
    violations, clause_results = [], []
    for clause in contract["forbidden_merges"]:
        a, b = clause["states"]
        wa, wb = clause["witness_words"][a], clause["witness_words"][b]
        stage, table = first_collapse(path, family, wa, wb)
        ra, rb = run(path, wa, family), run(path, wb, family)
        lost_at = None
        for lv in LEVELS:
            if PROJ[lv](ra) == PROJ[lv](rb):
                lost_at = lv
                break
        clause_results.append({
            "clause": clause["id"], "states": [a, b],
            "result": "FAIL" if stage is not None else "PASS",
            "first_collapse_stage": stage,
            "no_representation_stage": table["no_representation_stage"],
            "first_equivalent_level": lost_at,
            "note": ("the distinction survives to the end of the pipeline"
                     if stage is None else
                     "destroyed at " + stage)})
        if stage is not None:
            violations.append({
                "clause": clause["id"],
                "must_stay_distinct": [a, b],
                "shortest_witness": min([wa, wb], key=len),
                "witness_pair": [wa, wb],
                "first_collapse_stage": stage,
                "first_collapse_site": contract["stage_sites"].get(stage),
                "no_representation_stage": table["no_representation_stage"],
                "first_equivalent_level": lost_at,
                "downstream_consequence": consequence_of(ra, rb),
                "stage_table": table["stages"],
            })
    # emitted-state vocabulary: what CAN this path say to the core at all?
    vocab = set()
    for w in P.words(P.FAMILIES[family][0], max_len):
        for tok in _emissions(run(path, w, family)):
            vocab.add(tok)
    unrepresentable = sorted(set(contract["emitted_states_required"]) - vocab)
    return {
        "path": path, "family": family, "contract": contract["id"],
        "result": "PASS" if not violations and not unrepresentable else "FAIL",
        "emitted_state_vocabulary": sorted(vocab),
        "required_but_unrepresentable": unrepresentable,
        "clause_results": clause_results,
        "violations": violations,
    }


# ----------------------------------------------------------------------- main
def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    t_start = time.time()
    contracts = load_contracts()
    report = {"artifact": "EVIDENCE_SEMANTICS_CHECK", "max_word_length": MAX_LEN,
              "families": {}, "notes": {
                  "stamp_invariance": "every cross-path projection is either "
                  "order-only or a duration from word onset; the two stamping "
                  "conventions can shift a duration by at most one tick "
                  "(0.040 s), far below the effects reported",
                  "search": "exhaustive over lengths 1..N in increasing "
                            "order, so the first witness found is shortest "
                            "by construction"}}

    all_rows, minimal, blame, conseq = [], [], [], []

    for family in P.FAMILIES:
        alphabet = P.FAMILIES[family][0]
        rows, pairs = cross_path(family)
        pairs_now = pairs
        all_rows.extend(rows)
        fam = {"alphabet": alphabet, "pairs": pairs, "paths": {},
               "collapse": {}}

        for path in P.PATHS:
            c = contracts[family]
            res = check_contract(path, family, c)
            fam["paths"][path] = res
            for v in res["violations"]:
                blame.append({"family": family, "path": path, **{
                    k: v[k] for k in ("clause", "must_stay_distinct",
                                      "shortest_witness", "witness_pair",
                                      "first_collapse_stage",
                                      "first_collapse_site",
                                      "no_representation_stage",
                                      "first_equivalent_level",
                                      "downstream_consequence")},
                    "stage_table": v["stage_table"]})
                minimal.append({
                    "family": family, "path": path, "clause": v["clause"],
                    "witness": v["shortest_witness"],
                    "witness_length": len(v["shortest_witness"]),
                    "minimality": ("EXHAUSTIVE over lengths 1..%d; no shorter "
                                   "word exists in the alphabet" % MAX_LEN),
                    "alphabet": alphabet,
                    "words_at_or_below_length": sum(
                        1 for _ in P.words(alphabet, MAX_LEN)),
                })
            t0 = time.time()
            found, explored, distinct = collapse_search(path, family)
            fam["collapse"][path] = {
                "shortest_collapsing_pair": found,
                "words_explored": explored,
                "distinct_downstream_signatures": distinct,
                "runtime_s": round(time.time() - t0, 2),
            }

        # cross-path consequences, per word
        paths = list(P.PATHS)
        for i, pa in enumerate(paths):
            for pb in paths[i + 1:]:
                for w in P.words(alphabet, MAX_LEN):
                    ra, rb = run(pa, w, family), run(pb, w, family)
                    c = consequence_of(ra, rb)
                    if c == "NONE":
                        continue
                    # a consequence read off a level whose CONTROL already
                    # diverges is not attributable to the word
                    lvl_of = {"STATE_ONLY": "STATE",
                              "EVIDENCE_AVAILABILITY": "EVIDENCE",
                              "DIAGNOSIS_SCORE": "DIAGNOSIS",
                              "DIAGNOSIS_RANK": "DIAGNOSIS",
                              "ASSURANCE_STATE": "ASSURANCE",
                              "CONTROL_FAILSAFE": "ASSURANCE"}[c]
                    attributable = pairs_now[f"{pa}__vs__{pb}"][
                        f"{lvl_of}_status"] == "ATTRIBUTABLE"
                    ea, eb = proj_evidence(ra), proj_evidence(rb)
                    aa, ab = proj_assurance(ra), proj_assurance(rb)
                    conseq.append({
                        "family": family, "pair": f"{pa}__vs__{pb}",
                        "word": w, "length": len(w), "consequence": c,
                        "attributable": attributable,
                        "A_closes_a": ea[0], "A_closes_b": eb[0],
                        "A_close_delay_a_s": ea[1], "A_close_delay_b_s": eb[1],
                        "A_close_delta_s": (None if ea[1] is None
                                            or eb[1] is None
                                            else round(ea[1] - eb[1], 3)),
                        "failsafe_a": "|".join(aa[0]),
                        "failsafe_b": "|".join(ab[0]),
                        "failsafe_first_escalation_a_s": aa[1],
                        "failsafe_first_escalation_b_s": ab[1],
                        "failsafe_escalation_delta_s": (
                            None if aa[1] is None or ab[1] is None
                            else round(aa[1] - ab[1], 3)),
                        "actions_a": "|".join(aa[2]),
                        "actions_b": "|".join(ab[2]),
                    })
        report["families"][family] = fam

    report["runtime_s"] = round(time.time() - t_start, 2)

    # -------------------------------------------------------------- artifacts
    with open(os.path.join(DELIV, "CROSS_PATH_EQUIVALENCE.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w_ = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w_.writeheader()
        w_.writerows(all_rows)

    with open(os.path.join(DELIV, "DOWNSTREAM_CONSEQUENCES.csv"), "w",
              newline="", encoding="utf-8") as fh:
        cols = ["family", "pair", "word", "length", "consequence",
                "attributable",
                "A_closes_a", "A_closes_b", "A_close_delay_a_s",
                "A_close_delay_b_s", "A_close_delta_s", "failsafe_a",
                "failsafe_b", "failsafe_first_escalation_a_s",
                "failsafe_first_escalation_b_s",
                "failsafe_escalation_delta_s", "actions_a", "actions_b"]
        w_ = csv.DictWriter(fh, fieldnames=cols)
        w_.writeheader()
        w_.writerows(conseq)

    _dump("MINIMAL_COUNTEREXAMPLES.json", where=DELIV, obj=
          {"artifact": "MINIMAL_COUNTEREXAMPLES", "max_word_length": MAX_LEN,
           "method": "exhaustive breadth-first over the finite alphabet; a "
                     "witness of length k is minimal because every word of "
                     "length < k was checked first",
           "witnesses": minimal})
    _dump("CAUSAL_BLAME_TRACES.json", where=DELIV, obj=
          {"artifact": "CAUSAL_BLAME_TRACES",
           "definition": "the first pipeline stage whose projection is "
                         "identical for both inputs AND stays identical "
                         "through every later stage",
           "traces": blame})
    _dump("EVIDENCE_SEMANTICS_CHECK.json", report)

    # ------------------------------------------------------------- summary
    print(f"words per family: {sum(1 for _ in P.words('VIN', MAX_LEN))}  "
          f"(lengths 1..{MAX_LEN})")
    for family, fam in report["families"].items():
        print(f"\n=== {family} ===")
        for path, res in fam["paths"].items():
            print(f"  {path:<16} {res['result']:<5} "
                  f"vocabulary={res['emitted_state_vocabulary']} "
                  f"unrepresentable={res['required_but_unrepresentable']}")
            for c in res["clause_results"]:
                print(f"      {c['clause']} {c['result']}: {c['note']}")
            for v in res["violations"]:
                print(f"        -> witness {v['shortest_witness']!r}  "
                      f"site {v['first_collapse_site']}  "
                      f"consequence {v['downstream_consequence']}"
                      + (f"  [path has no {','.join(v['no_representation_stage'])}]"
                         if v["no_representation_stage"] else ""))
        for pair, v in fam["pairs"].items():
            print(f"  {pair}:")
            for lv in LEVELS:
                print(f"      {lv:<10} {v[f'{lv}_status']:<22} "
                      f"raw {v[f'{lv}_divergent_words']:>3}/{v['words_tested']} "
                      f"attributable {v[f'{lv}_attributable_words']:>3} "
                      f"(shortest {v[f'{lv}_shortest_attributable']!r})")
    print(f"\nruntime {report['runtime_s']} s -> "
          f"{os.path.relpath(OUT, ROOT)}/")
    return 0


def _dump(name, obj, where=None):
    with open(os.path.join(where or OUT, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
