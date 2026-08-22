"""WP-C4 Part 2.5 — did the promotion trade one order-one exposure for another?

WP-C3 made `mag` the highest-Birnbaum component by routing IMU discrimination
through it. Birnbaum rank is suggestive; the test is the cut sets. Direct
question: is there NOW an order-one cut set at `channel:mag` that was not
there before?

Computes minimal cut sets for every critical pair under the PRE-promotion and
POST-promotion signature matrices and diffs them.

Run:  PYTHONPATH=. python research/wp_c4/cutsets_post_promotion.py
Out:  research/wp_c4/results/cutsets_post_promotion.json
"""

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_c1.lattice import load_signatures              # noqa: E402
from research.wp_c3.reliability_structure import (              # noqa: E402
    COMPONENTS, all_states, phi)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
REPAIR_FEATURE = "attitude_gravity_mag"
REPAIR_TARGET = "imu0_bias_drift"


def minimal_cut_sets(low, pair, states):
    failing = [s for s in states if phi(low, pair, s) == 1]
    fs = set(failing)
    return sorted((sorted(s) for s in failing
                   if not any(t < s for t in fs)),
                  key=lambda x: (len(x), x))


def main() -> int:
    post = load_signatures()
    pre = {h: sorted(set(v) - {REPAIR_FEATURE}) if h == REPAIR_TARGET
           else sorted(v) for h, v in post.items()}
    assert REPAIR_FEATURE in post[REPAIR_TARGET], (
        "expected the post-promotion matrix to carry the repair")
    assert REPAIR_FEATURE not in pre[REPAIR_TARGET]

    hyps = sorted(post)
    crit, _ = d_critical(hyps)
    states = list(all_states())

    rows, order1_pre, order1_post = [], {}, {}
    for pair in sorted(crit):
        cs_pre = minimal_cut_sets(pre, pair, states)
        cs_post = minimal_cut_sets(post, pair, states)
        o1_pre = [c[0] for c in cs_pre if len(c) == 1]
        o1_post = [c[0] for c in cs_post if len(c) == 1]
        if o1_pre:
            order1_pre["+".join(pair)] = o1_pre
        if o1_post:
            order1_post["+".join(pair)] = o1_post
        if cs_pre != cs_post:
            rows.append({
                "pair": "+".join(pair),
                "min_cut_size_pre": min(len(c) for c in cs_pre),
                "min_cut_size_post": min(len(c) for c in cs_post),
                "order_one_pre": o1_pre,
                "order_one_post": o1_post,
                "cut_sets_pre": cs_pre[:8],
                "cut_sets_post": cs_post[:8],
            })

    all_o1_pre = {c for v in order1_pre.values() for c in v}
    all_o1_post = {c for v in order1_post.values() for c in v}

    mag_o1_pairs = [p for p, v in order1_post.items()
                    if "channel:mag" in v]
    mag_o1_pairs_pre = [p for p, v in order1_pre.items()
                        if "channel:mag" in v]

    report = {
        "purpose": "did promoting the IMU repair create a new order-one cut "
                   "set at channel:mag?",
        "question_answered": "NO" if set(mag_o1_pairs) <= set(mag_o1_pairs_pre)
                             else "YES",
        "channel_mag_order_one_pairs_pre": mag_o1_pairs_pre,
        "channel_mag_order_one_pairs_post": mag_o1_pairs,
        "new_mag_order_one_pairs": sorted(set(mag_o1_pairs)
                                          - set(mag_o1_pairs_pre)),
        "n_pairs_with_order_one_cut_pre": len(order1_pre),
        "n_pairs_with_order_one_cut_post": len(order1_post),
        "order_one_cut_sets_pre": order1_pre,
        "order_one_cut_sets_post": order1_post,
        "components_appearing_in_any_order_one_pre": sorted(all_o1_pre),
        "components_appearing_in_any_order_one_post": sorted(all_o1_post),
        "pairs_whose_cut_sets_changed": rows,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "cutsets_post_promotion.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"pairs with an order-one cut set: "
          f"{len(order1_pre)} pre -> {len(order1_post)} post")
    print(f"channel:mag order-one for (pre) : {mag_o1_pairs_pre or 'nothing'}")
    print(f"channel:mag order-one for (post): {mag_o1_pairs or 'nothing'}")
    print(f"NEW mag order-one exposures: "
          f"{report['new_mag_order_one_pairs'] or 'NONE'}\n")
    print("pairs whose cut sets changed:")
    for r in rows:
        print(f"  {r['pair']}")
        print(f"    min cut size {r['min_cut_size_pre']} -> "
              f"{r['min_cut_size_post']}")
        print(f"    order-one    {r['order_one_pre'] or '-'} -> "
              f"{r['order_one_post'] or '-'}")
        print(f"    post cut sets: {r['cut_sets_post'][:4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
