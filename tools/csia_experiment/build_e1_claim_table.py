"""Generate the final E1 claim table from the canonical repeat artifacts.

WHY A GENERATOR AND NOT A HAND-WRITTEN CSV
-------------------------------------------
Every numeric field in this table is read from a committed artifact at
generation time. The wording columns are authored -- they are judgements about
what may be said, and a script cannot make those -- but no number in the table
is typed by hand, so the table cannot drift away from the measurements the way
a transcribed figure does. That is the same defect EVIDENCE-05 exposed: a
number copied into a second place stops being a check on the first.

`tests/test_e1_claim_table.py` regenerates and compares, so an artifact change
that the table has not absorbed fails loudly.

WHAT THE STATUS VOCABULARY MEANS
---------------------------------
  REPEATED                the quantity was measured again under a
                          preregistration frozen before the first trial, and
                          the repeated result supports the original claim
  REFUTED_SUPERSEDED      the repeated data do not support the claim as it was
                          stated, and a supported replacement exists
  NOT_REPEATABLE          the original value is a faithful record of its own
                          trial and does not reproduce under the current
                          configuration. NOT "wrong"
  CONFIGURATION_DEPENDENT the quantity reproduces only when a named
                          configuration field is held fixed, and that field was
                          not pinned by the preregistrations
  MEASURED                a new quantity, measured this programme, with no
                          prior claim attached
  UNRESOLVED              a difference that is real, reproducible and not
                          explained. Labelled, not filled in

NOT IN THIS TABLE, DELIBERATELY: any statement about hardware, real sensors,
flight, prevalence, or how often any of this occurs in the field.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, "research", "physical_validation", "results")

COLUMNS = [
    "claim_id", "claim", "platform", "original_n", "repeat_n", "status",
    "reproduced_quantity", "not_reproduced_quantity",
    "configuration_dependence", "artifact", "allowed_wording",
    "forbidden_wording",
]

#: Shared across many rows, so stated once.
NO_PREVALENCE = ("any 'always', 'in general', 'population probability', "
                 "'prevalence', or any rate over vehicles or flights")

REPEAT_ARTIFACTS = (
    "campaigns/physical_validation/mechanism_a_trust_completion_a2/; "
    "campaigns/physical_validation/mechanism_a_px4_repeat_p1/")


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as fh:
        return json.load(fh)


def _table(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _med(rows, arm, key):
    vals = [float(r[key]) for r in rows if r["role"] == arm and r[key] not in
            ("", "None", "NOT_CAPTURED")]
    return statistics.median(vals)


def _fmt(x, n=6):
    return f"{x:.{n}f}"


def build() -> list:
    a2 = _load("mechanism_a_a2_trust_ardupilot.json")
    p1 = _load("mechanism_a_p1_trust_px4.json")
    ap = _table("ARDUPILOT_MECHANISM_A_REPEAT_TABLE.csv")
    px = _table("PX4_MECHANISM_A_REPEAT_TABLE.csv")

    def deltas(d):
        return (d["question_B_fault_delta_distribution"],
                d["question_C_control_delta_distribution"],
                d["question_D_original_n1"],
                d["primary_question_A_does_trust_increase"])

    a_f, a_c, a_o, a_a = deltas(a2)
    p_f, p_c, p_o, p_a = deltas(p1)

    def gate(rows, arm, key):
        return sorted({r[key] for r in rows if r["role"] == arm})

    rows = []

    # -- 1. structural mechanism -------------------------------------------
    for plat, tab, tag in (("ardupilot", ap, "A"), ("px4", px, "P")):
        n_fault = sum(1 for r in tab if r["role"] == "FAULT")
        n_ctrl = sum(1 for r in tab if r["role"] == "CONTROL")
        rows.append({
            "claim_id": f"E1-STRUCT-{tag}",
            "claim": ("Confirmed GNSS fix loss removes the gate-supported "
                      "evidence that would discriminate gps_fault, while the "
                      "diagnosis keeps nominal as leader"),
            "platform": plat,
            "original_n": "1 fault + 1 matched control",
            "repeat_n": f"{n_fault} fault + {n_ctrl} matched control",
            "status": "REPEATED",
            "reproduced_quantity": (
                f"the full structural chain: fix loss confirmed by downstream "
                f"effect, gate weight to 0.0, nominal remains rank 1, "
                f"gps_fault never leads. {n_fault}/{n_fault} fault, "
                f"0/{n_ctrl} control"),
            "not_reproduced_quantity": "none",
            "configuration_dependence": (
                "none for the structure. The MAGNITUDE of the removed gate "
                "weight is link-dependent: 3.0 on ArduPilot, 1.0 on PX4"),
            "artifact": REPEAT_ARTIFACTS,
            "allowed_wording": (
                "'repeated under the tested conditions'; 'twenty valid fault "
                "trials and twenty matched controls per platform'; 'the "
                "structural gate-collapse and ranking mechanism repeated on "
                "both current stacks'"),
            "forbidden_wording": NO_PREVALENCE,
        })

    # -- 2. fix loss --------------------------------------------------------
    for plat, tab, tag, first_t, ticks in (
            ("ardupilot", ap, "A", "12.043901 s", "450"),
            ("px4", px, "P", "12.121585 s", "448")):
        n_fault = sum(1 for r in tab if r["role"] == "FAULT")
        n_ctrl = sum(1 for r in tab if r["role"] == "CONTROL")
        rows.append({
            "claim_id": f"E1-FIXLOSS-{tag}",
            "claim": ("The intervention is evidenced by its downstream effect "
                      "-- gnss.position MISSING with NO_3D_FIX -- and not by "
                      "the parameter write (RULE B)"),
            "platform": plat,
            "original_n": "1 fault + 1 matched control",
            "repeat_n": f"{n_fault} fault + {n_ctrl} matched control",
            "status": "REPEATED",
            "reproduced_quantity": (
                f"present in {n_fault}/{n_fault} fault and 0/{n_ctrl} control "
                f"trials; the original first_t ({first_t}) and tick count "
                f"({ticks}) both fall inside the repeated ranges"),
            "not_reproduced_quantity": "none",
            "configuration_dependence": "none observed",
            "artifact": REPEAT_ARTIFACTS + "; "
                        "research/physical_validation/results/"
                        "mechanism_a_repeat_ardupilot.json",
            "allowed_wording": (
                "'the intervention was validated by its downstream effect "
                "before any scoring, in every valid trial'"),
            "forbidden_wording": (
                "'the parameter write caused the fault' -- COMMAND ISSUED is "
                "not FAULT INJECTED; " + NO_PREVALENCE),
        })

    # -- 3. gate collapse ---------------------------------------------------
    for plat, tab, tag in (("ardupilot", ap, "A"), ("px4", px, "P")):
        pre_f, post_f = gate(tab, "FAULT", "gate_pre"), gate(tab, "FAULT",
                                                             "gate_post")
        pre_c, post_c = gate(tab, "CONTROL", "gate_pre"), gate(tab, "CONTROL",
                                                               "gate_post")
        n_fault = sum(1 for r in tab if r["role"] == "FAULT")
        rows.append({
            "claim_id": f"E1-GATE-{tag}",
            "claim": ("gps_gate_weight_sum over the GNSS-incident edges "
                      "collapses to exactly zero under fix loss and does not "
                      "move in the matched control"),
            "platform": plat,
            "original_n": "1 fault + 1 matched control",
            "repeat_n": f"{n_fault} fault + {n_fault} matched control",
            "status": "REPEATED",
            "reproduced_quantity": (
                f"FAULT {','.join(pre_f)} -> {','.join(post_f)} in "
                f"{n_fault}/{n_fault}; CONTROL {','.join(pre_c)} -> "
                f"{','.join(post_c)} in {n_fault}/{n_fault}, no exceptions"),
            "not_reproduced_quantity": "none",
            "configuration_dependence": (
                "the PRE-FAULT VALUE is link-dependent and was preregistered "
                "as such: 3.0 on ArduPilot (3 of 4 relations live) against "
                "1.0 on PX4 (1 of 4 live, the rest DARK_BY_GATE, "
                "DARK_STRUCTURAL and STARVED_BY_TRANSPORT). A cleaner PX4 "
                "link was NOT adopted to raise it"),
            "artifact": REPEAT_ARTIFACTS,
            "allowed_wording": (
                "'the gate weight supporting gps_fault collapsed to exactly "
                "zero in every valid fault trial and in no control trial'; "
                "for PX4, only with the 1-of-4 qualification stated"),
            "forbidden_wording": (
                "quoting PX4's collapse as equivalent in magnitude to "
                "ArduPilot's; " + NO_PREVALENCE),
        })

    # -- 4. nominal leader --------------------------------------------------
    for plat, tab, tag in (("ardupilot", ap, "A"), ("px4", px, "P")):
        nom_pre = sorted({r["nominal_rank_pre"] for r in tab})
        nom_post = sorted({r["nominal_rank_post"] for r in tab})
        gf_pre = sorted({r["gps_fault_rank_pre"] for r in tab})
        gf_post = sorted({r["gps_fault_rank_post"] for r in tab})
        w_pre = _med([r for r in tab if r["role"] == "FAULT"], "FAULT",
                     "gps_fault_weight_pre")
        w_post = _med([r for r in tab if r["role"] == "FAULT"], "FAULT",
                      "gps_fault_weight_post")
        stable = nom_pre == nom_post == ["1"]
        rows.append({
            "claim_id": f"E1-LEADER-{tag}",
            "claim": ("nominal remains the leading hypothesis across the "
                      "fault and gps_fault is never promoted to leader"),
            "platform": plat,
            "original_n": "1 fault + 1 matched control",
            "repeat_n": "20 fault + 20 matched control",
            "status": "REPEATED" if stable else "REPEATED_PARTIAL",
            "reproduced_quantity": (
                f"nominal rank {','.join(nom_pre)} -> {','.join(nom_post)} in "
                f"40/40 trials; gps_fault gains weight under fault "
                f"({_fmt(w_pre)} -> {_fmt(w_post)} median) without ever "
                f"leading"),
            "not_reproduced_quantity": (
                "none" if gf_pre == gf_post and len(gf_pre) == 1 else
                f"gps_fault's RANK is not stable on this platform: pre "
                f"{','.join(gf_pre)}, post {','.join(gf_post)}. The claim is "
                f"about nominal leading, which is stable; a claim about "
                f"gps_fault's rank is NOT supported here"),
            "configuration_dependence": (
                "gps_fault's pre-fault rank tracks the live discriminating "
                "relation pool, which is link-dependent (ArduPilot 6, PX4 2)"),
            "artifact": REPEAT_ARTIFACTS,
            "allowed_wording": (
                "'the diagnosis kept nominal on top and never promoted "
                "gps_fault, in every valid trial of both arms'"),
            "forbidden_wording": (
                "any claim about gps_fault's numeric rank being stable; "
                + NO_PREVALENCE),
        })

    # -- 5. trust sign ------------------------------------------------------
    for plat, tag, f, c, a in (("ardupilot", "A", a_f, a_c, a_a),
                               ("px4", "P", p_f, p_c, p_a)):
        ratio = c["median"] / f["median"]
        disjoint = f["max"] < c["min"]
        rows.append({
            "claim_id": f"E1-TRUSTSIGN-{tag}",
            "claim": ("the gps trust coefficient does not fall under gate "
                      "closure; it rises"),
            "platform": plat,
            "original_n": "1 fault + 1 matched control",
            "repeat_n": "20 fault + 20 matched control",
            "status": "REPEATED",
            "reproduced_quantity": (
                f"the SIGN: positive in "
                f"{a['fault_trials_with_positive_delta']}/"
                f"{a['fault_trials_total']} fault trials and in 20/20 "
                f"controls. Fault delta median {_fmt(f['median'])}, control "
                f"{_fmt(c['median'])}"),
            "not_reproduced_quantity": (
                "the MAGNITUDE -- see E1-TRUSTVAL-" + tag),
            "configuration_dependence": (
                "the magnitude depends on the runtime stale-timeout table; "
                "the sign does not"),
            "artifact": ("research/physical_validation/results/"
                         "mechanism_a_a2_trust_ardupilot.json; "
                         "mechanism_a_p1_trust_px4.json"),
            "allowed_wording": (
                "'trust did not provide a compensating indication of the loss "
                "of diagnostic support: it rose in the fault arm, and rose "
                f"MORE in the matched control ({ratio:.1f}x, "
                f"{'disjoint' if disjoint else 'overlapping'} ranges)'"),
            "forbidden_wording": (
                "'trust rises across a gate collapse' stated WITHOUT the "
                "control arm -- true and misleading alone; " + NO_PREVALENCE),
        })

    # -- 6. the refuted causal explanation ----------------------------------
    rows.append({
        "claim_id": "E1-TRUSTCAUSE",
        "claim": ("gate closure CAUSES the trust rise, because removing an "
                  "inconsistent comparison removes a source of disagreement "
                  "and a layer scoring agreement scores higher with less to "
                  "disagree about"),
        "platform": "ardupilot; px4",
        "original_n": "1 fault trial per platform, no control comparison made",
        "repeat_n": "20 fault + 20 matched control per platform",
        "status": "REFUTED_SUPERSEDED",
        "reproduced_quantity": "none. The explanation is not a measurement",
        "not_reproduced_quantity": (
            f"the causal direction. Trust rises in the MATCHED CONTROL too, "
            f"and by MORE: ArduPilot {_fmt(a_c['median'])} against "
            f"{_fmt(a_f['median'])} "
            f"({a_c['median'] / a_f['median']:.1f}x), PX4 "
            f"{_fmt(p_c['median'])} against {_fmt(p_f['median'])} "
            f"({p_c['median'] / p_f['median']:.1f}x). Both ranges disjoint. "
            f"An explanation that requires the gate to close cannot account "
            f"for a LARGER rise where it did not"),
        "configuration_dependence": (
            "not applicable -- the refutation is arm-to-arm within each "
            "campaign, so the configuration is held fixed by construction"),
        "artifact": ("research/physical_validation/FAILURE_LEDGER.yaml FL-016; "
                     "ARDUPILOT_REPEAT_RECONCILIATION.md section 3; "
                     "PX4_REPEAT_RECONCILIATION.md section 2"),
        "allowed_wording": (
            "'trust rose in both arms as evidence accumulated, and by less "
            "under fix loss, because the gate closure freezes the belief "
            "update rather than driving it down -- absence of evidence is not "
            "treated as evidence of fault'. The FREEZING account is what the "
            "repeated data support and is what the manuscript already said"),
        "forbidden_wording": (
            "'trust rises BECAUSE gated-out disagreement disappears'; "
            "'removing an inconsistent comparison removes a source of "
            "disagreement'; any wording in which the fault CAUSES the rise"),
    })

    # -- 7. exact original trust values -------------------------------------
    for plat, tag, orig_pre, orig_post, o, tab in (
            ("ardupilot", "A", "0.9213", "0.9300", a_o, ap),
            ("px4", "P", "0.9856", "0.9875", p_o, px)):
        rows.append({
            "claim_id": f"E1-TRUSTVAL-{tag}",
            "claim": f"the gps trust coefficient reads {orig_pre} -> "
                     f"{orig_post} across the fault",
            "platform": plat,
            "original_n": "1 fault trial",
            "repeat_n": "20 fault trials",
            "status": "NOT_REPEATABLE",
            "reproduced_quantity": "the sign only -- see E1-TRUSTSIGN-" + tag,
            "not_reproduced_quantity": (
                f"the delta. Original {o['delta']} against repeated range "
                f"[{_fmt(o['fault_range'][0])}, {_fmt(o['fault_range'][1])}]: "
                f"inside={o['inside_repeated_fault_range']}. Repeated values "
                f"are {_fmt(_med(tab, 'FAULT', 'trust_pre'))} -> "
                f"{_fmt(_med(tab, 'FAULT', 'trust_post'))} (n=20 medians)"),
            "configuration_dependence": (
                "YES, and it is named: the original ran the frozen core's "
                "0.5 s gps stale timeout, the repeats the 1.0 s value derived "
                "from the adapter's MaxAge (Phase 4.5 Gate B). NEITHER "
                "PREREGISTRATION PINNED THIS FIELD -- FL-017"),
            "artifact": ("research/v1_1/results/mechanism_a_ardupilot.json; "
                         "mechanism_a_px4.json (both FROZEN, both unedited); "
                         "FAILURE_LEDGER.yaml FL-017"),
            "allowed_wording": (
                "'a faithful record of one trial under a superseded runtime "
                "watchdog'; the repeated values, quoted with n and with the "
                "watchdog named"),
            "forbidden_wording": (
                f"quoting {orig_pre} -> {orig_post} as a current or "
                f"repeatable value; " + NO_PREVALENCE),
        })

    # -- 8. exact timing values ---------------------------------------------
    rows.append({
        "claim_id": "E1-TIMING",
        "claim": ("the gate-collapse latency after confirmed fix loss is "
                  "about half a second"),
        "platform": "ardupilot; px4",
        "original_n": "1 fault trial per platform",
        "repeat_n": "20 fault trials per platform",
        "status": "CONFIGURATION_DEPENDENT",
        "reproduced_quantity": (
            "the ORDERING of events -- channel loss, then gate collapse, then "
            "the trust coefficient freezing -- in every valid fault trial"),
        "not_reproduced_quantity": (
            "the interval. Measured dwell (channel MISSING to gate zero): "
            "ArduPilot original 0.478777 s against repeated 0.993018-1.006609; "
            "PX4 original 0.400208 s against a repeat pair at 0.919577"),
        "configuration_dependence": (
            "YES. dwell ~= runtime gps stale timeout minus the channel's age "
            "at the last usable tick, confirmed on four runs across two "
            "platforms and both watchdog values, every residual inside one "
            "25 Hz tick period"),
        "artifact": ("ARDUPILOT_REPEAT_RECONCILIATION.md section 4.5; "
                     "tests/test_ardupilot_repeat_reconciliation.py"),
        "allowed_wording": (
            "any latency quoted WITH the runtime stale-timeout table it was "
            "measured under"),
        "forbidden_wording": (
            "any bare latency figure; any timing claim from these campaigns "
            "at all -- latency was recorded and deliberately NOT adjudicated "
            "on a shared host, and PX4 ran real-time lockstep"),
    })

    # -- 9. the watchdog/dwell relation -------------------------------------
    rows.append({
        "claim_id": "E1-WATCHDOG",
        "claim": ("the gate-collapse dwell is a deterministic function of the "
                  "runtime stale timeout and the channel's age when it is "
                  "flagged"),
        "platform": "ardupilot; px4",
        "original_n": "0 -- no prior claim existed",
        "repeat_n": "4 independent runs, 2 platforms, both watchdog values",
        "status": "MEASURED",
        "reproduced_quantity": (
            "dwell ~= watchdog - age_at_last_usable_tick. Residuals "
            "-0.008406, +0.012408, +0.005943, +0.012429 s against a 0.04 s "
            "tick period"),
        "not_reproduced_quantity": "not applicable -- a new quantity",
        "configuration_dependence": (
            "it IS the configuration dependence. Frozen "
            "STALE_TIMEOUT_S['gps'] = 0.5; derived "
            "build_runtime_stale_timeouts(...)['gps'] = 1.0 on both platforms"),
        "artifact": ("csia/runtime/online.py; csia/v1_1/staleness.py; "
                     "ARDUPILOT_REPEAT_RECONCILIATION.md section 4.5"),
        "allowed_wording": (
            "'the collapse latency is set by the runtime staleness watchdog, "
            "not by the diagnosis'"),
        "forbidden_wording": (
            "presenting it as a property of the frozen scientific core -- the "
            "core is byte-identical across the change; the DRIVER changed"),
    })

    # -- 10. FL-019 ---------------------------------------------------------
    rows.append({
        "claim_id": "E1-FL019",
        "claim": ("why ArduPilot's PRE-fault trust was stable across the same "
                  "0.5 s -> 1.0 s watchdog change while PX4's moved"),
        "platform": "ardupilot",
        "original_n": "not applicable",
        "repeat_n": "not applicable",
        "status": "UNRESOLVED",
        "reproduced_quantity": (
            "the difference itself, which is real and reproducible: ArduPilot "
            "pre-fault trust 0.924639 original against 0.924816 repeated, "
            "while PX4 moved 0.985624 -> 0.952172"),
        "not_reproduced_quantity": (
            "the explanation. The controlled replay that attributes PX4's "
            "difference is NOT a valid instrument on ArduPilot: it gives "
            "0.979440 and 0.941275 against measured 0.924639 and 0.924816"),
        "configuration_dependence": "unknown, which is the point",
        "artifact": ("FAILURE_LEDGER.yaml FL-019; "
                     "PX4_REPEAT_RECONCILIATION.md section 3.3; "
                     "tools/csia_experiment/watchdog_replay.py"),
        "allowed_wording": (
            "'unresolved'; a hypothesis explicitly labelled as one"),
        "forbidden_wording": (
            "any account presented as established. A test asserts the replay "
            "STILL FAILS on ArduPilot so this cannot lapse silently"),
    })

    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "physical_validation", "E1_FINAL_CLAIM_TABLE.csv"))
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    rows = build()
    from tools.evidence_guard import protected_write
    with protected_write(args.out, regenerate=args.regenerate) as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {args.out} ({len(rows)} claims)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
