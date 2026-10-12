"""The traceability ledger, and the two-gate freshness finding it exposed.

The ledger resolves every scalar from its artifact at run time instead of
storing it, so an entry whose lookup path breaks is reported UNSUPPORTED rather
than silently serving a stale number. These tests assert that the resolution
actually happened -- "0 unsupported" has to mean the lookups ran, not that the
list was empty.

They also pin the finding the ledger surfaced: evidence availability is gated
TWICE, by the channel's `max_age` (bought by the declared rate) and again by
the node's `STALE_TIMEOUT_S` (a fixed runtime constant no declaration feeds).
For the barometer the node gate is five times stricter, so an account that
mentions only `max_age` predicts ~50 % availability where the measurement shows
under 10 %.

Reads committed artifacts and frozen source.
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(ROOT, "research", "v1_1", "results")
AUDIT = os.path.join(RESULTS, "CURRENT_STACK_EVIDENCE_QUALIFICATION_AUDIT.json")
LEDGER = os.path.join(RESULTS, "EVIDENCE_COVERAGE_LEDGER.json")

KINDS = {"PREREGISTERED_CAMPAIGN", "POST_HOC_ANALYSIS",
         "QUALIFICATION_HARNESS_AUDIT", "MEASURED_CORPUS_PROPERTY"}


@pytest.fixture(scope="module")
def audit():
    if not os.path.exists(AUDIT):
        pytest.skip("run tools/publication/evidence_qualification_audit.py")
    with open(AUDIT, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def ledger():
    if not os.path.exists(LEDGER):
        pytest.skip("run tools/simulation/evidence_coverage_ledger.py")
    with open(LEDGER, encoding="utf-8") as fh:
        return json.load(fh)


def test_every_scalar_resolved(audit):
    bad = [e["claim_id"] for e in audit["entries"]
           if e["status"] != "SUPPORTED"]
    assert not bad, f"unsupported scalars: {bad}"
    assert audit["unsupported_scalars"] == 0


def test_the_ledger_is_not_vacuously_clean(audit):
    """An empty entry list would also report zero unsupported scalars."""
    assert len(audit["entries"]) >= 30, len(audit["entries"])
    assert audit["supported_scalars"] == len(audit["entries"])


def test_every_entry_declares_where_its_value_came_from(audit):
    for e in audit["entries"]:
        assert e["artifact"], e["claim_id"]
        assert e["lookup"], e["claim_id"]
        assert e["analysis_type"] in KINDS, (e["claim_id"], e["analysis_type"])


def test_the_four_analysis_types_are_never_pooled(audit):
    """A post-hoc sweep read as a prediction is how a paper overclaims."""
    by_kind = audit["claims_by_analysis_type"]
    assert "POST_HOC_ANALYSIS" in by_kind
    assert "PREREGISTERED_CAMPAIGN" in by_kind
    overlap = set(by_kind["POST_HOC_ANALYSIS"]) & set(
        by_kind["PREREGISTERED_CAMPAIGN"])
    assert not overlap, overlap
    # the S0 threshold sweep is post-hoc and must never be listed otherwise
    assert all(c.startswith("s0.") for c in by_kind["POST_HOC_ANALYSIS"])


def test_no_entry_claims_to_be_in_a_manuscript(audit):
    """No manuscript here carries the current-stack results; saying so is a lie."""
    assert all(e["in_manuscript"] is False for e in audit["entries"])


# ------------------------------------------------------- the two-gate finding
def test_the_node_gate_is_reported_and_is_the_binding_one_for_baro(ledger):
    """`max_age` alone does not explain the starvation; the node timeout does."""
    for plat in ("px4", "ardupilot"):
        ep = ledger["ledger"][plat]["relations"]["altitude_baro"]["endpoints"]
        baro = ep["baro"]
        assert baro["node_fresh_share"] is not None, plat
        assert baro["node_stale_timeout_s"] == 0.1, baro
        assert baro["derived_max_age_s"] == 0.5, baro
        # the node budget is the stricter of the two, on both platforms
        assert baro["binding_gate"] == "node_stale_timeout", (plat, baro)


def test_on_px4_the_node_gate_costs_far_more_than_the_channel_gate(ledger):
    """The measurement an account mentioning only max_age would get wrong."""
    baro = (ledger["ledger"]["px4"]["relations"]["altitude_baro"]
            ["endpoints"]["baro"])
    usable, fresh = baro["channel_usable_share"], baro["node_fresh_share"]
    assert 0.4 < usable < 0.6, usable          # ~half, from the 0.5 s max_age
    assert fresh < 0.15, fresh                 # ~a tenth, from the 0.1 s node
    assert usable > 3 * fresh, (usable, fresh)


def test_ardupilot_is_starved_at_neither_gate(ledger):
    """The contrast that shows this is a link property, not a design flaw."""
    baro = (ledger["ledger"]["ardupilot"]["relations"]["altitude_baro"]
            ["endpoints"]["baro"])
    assert baro["channel_usable_share"] > 0.99, baro
    assert baro["node_fresh_share"] > 0.99, baro


def test_relation_liveness_tracks_node_freshness_not_channel_usability(ledger):
    """The relation is gated on nodes (online.py:610), so it must follow them."""
    for plat in ("px4", "ardupilot"):
        rel = ledger["ledger"][plat]["relations"]["altitude_baro"]
        ep = rel["endpoints"]
        live = rel["relation_live_share"]
        floor = min(ep[n]["node_fresh_share"] for n in ep)
        assert live <= floor + 0.02, (plat, live, floor)
