"""Baseline benchmark integrity (slice 3D). Evaluation-only.

These pin the BENCHMARK, not the model: that baselines behave as
pre-registered, that the campaign is unchanged, and that the honest
result (a simple rule matches CSIA) cannot be silently reversed.
"""
import json
import os

import pytest

from csia.diagnosis.baselines import (D_MIN_SOURCES, D_WINDOW_S, DWELL_TICKS,
                                      RESOURCE, VOTE_C, LEGACY_CAUSE_SOURCE,
                                      observability_qualified,
                                      system_b_majority_vote,
                                      system_c_per_source,
                                      system_d_shared_rule)
from csia.diagnosis.causal import SOURCE_DEGRADED

ROOT = os.path.join(os.path.dirname(__file__), "..")
CAMPAIGN = os.path.join(ROOT, "campaigns", "shared_power_generalization_v1.json")
RESULT = os.path.join(ROOT, "campaigns", "results",
                      "shared_power_baseline_v1.json")
FROZEN_HASH = ("10f4fe6b7245a657321c4021e9802fe407f8c421159a62716d34a4278"
               "f1ce922")


# --- pre-registered constants must not drift ----------------------------------

def test_baseline_constants_match_protocol():
    assert VOTE_C == 0.70
    assert DWELL_TICKS == 25
    assert D_WINDOW_S == 9.0
    assert D_MIN_SOURCES == 2
    assert RESOURCE == "MAIN_POWER_PACK"


def test_baselines_share_csia_severity_threshold():
    """C and D are deliberately given CSIA's own normalization so a CSIA
    margin cannot be attributed to a handicapped baseline."""
    assert SOURCE_DEGRADED == 0.45


def test_legacy_cannot_express_a_shared_resource():
    assert None in set(LEGACY_CAUSE_SOURCE.values())
    assert all(v is None or isinstance(v, str)
               for v in LEGACY_CAUSE_SOURCE.values())
    assert RESOURCE not in LEGACY_CAUSE_SOURCE.values()


# --- campaign integrity --------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(CAMPAIGN), reason="campaign absent")
def test_campaign_hash_unchanged():
    with open(CAMPAIGN) as fh:
        c = json.load(fh)
    assert c["campaign_aggregate_hash"] == FROZEN_HASH
    assert c["total"] == 110


@pytest.mark.skipif(not os.path.exists(RESULT), reason="benchmark not run")
class TestBenchmarkResult:
    def load(self):
        with open(RESULT) as fh:
            return json.load(fh)["payload"]

    def test_result_references_the_frozen_campaign(self):
        assert self.load()["campaign_aggregate_hash"] == FROZEN_HASH

    def test_all_five_systems_evaluated(self):
        assert len(self.load()["systems"]) == 5

    def test_every_scenario_scored_none_excluded(self):
        d = self.load()
        assert d["stratum_sizes"]["ALL"] == 110
        assert len(d["scenarios"]) == 110

    def test_no_system_falsely_claims_shared_on_clean(self):
        s = self.load()["summary"]["NEGATIVE_HEALTHY"]
        for sysname, m in s.items():
            assert m["clean_shared_activations"] == 0, sysname

    def test_csia_and_rule_never_blame_wrongly(self):
        s = self.load()["summary"]["ALL"]
        assert s["D_SHARED_RESOURCE_RULE"]["incorrect_source_blame"]["rate"] == 0.0
        assert s["E_CSIA"]["incorrect_source_blame"]["rate"] == 0.0

    def test_naive_per_source_thresholding_does_blame_wrongly(self):
        """The reason a per-source baseline is not sufficient."""
        s = self.load()["summary"]["NEGATIVE_HEALTHY"]
        assert s["C_PER_SOURCE_THRESHOLD"]["incorrect_source_blame"]["rate"] > 0

    def test_structurally_incapable_systems_score_zero_root_cause(self):
        s = self.load()["summary"]["OBSERVABLE_POSITIVE"]
        for sysname in ("A_LEGACY_SINGLE_SOURCE", "B_MAJORITY_VOTE",
                        "C_PER_SOURCE_THRESHOLD"):
            assert s[sysname]["root_cause_correct"]["rate"] == 0.0

    def test_HONEST_the_simple_rule_is_not_beaten_by_csia(self):
        """PINS THE UNFAVOURABLE RESULT.

        System D matches or exceeds CSIA on shared-power root cause. The
        pre-registered comparative-value criterion (+10 pp) is NOT met. If a
        future change reverses this, it must be a deliberate, measured
        improvement -- not a silent drift in the benchmark.
        """
        b = self.load()["summary"]["BLIND_SYNTHETIC"]
        d = b["D_SHARED_RESOURCE_RULE"]["root_cause_correct"]["rate"]
        e = b["E_CSIA"]["root_cause_correct"]["rate"]
        assert d >= e, "benchmark reversed without a recorded model change"
        assert (e - d) < 0.10, "comparative-value criterion was NOT met"

    def test_csia_leads_on_coverage_not_accuracy(self):
        a = self.load()["summary"]["ALL"]
        assert (a["E_CSIA"]["abstention"]["rate"]
                < a["D_SHARED_RESOURCE_RULE"]["abstention"]["rate"])
        assert (a["E_CSIA"]["source_f1_mean"]
                > a["D_SHARED_RESOURCE_RULE"]["source_f1_mean"])

    def test_detectability_floor_defeats_every_system(self):
        s = self.load()["summary"]["DETECTABILITY_FLOOR"]
        for sysname, m in s.items():
            assert m["root_cause_correct"]["rate"] in (0.0, None), sysname

    def test_rates_carry_confidence_intervals(self):
        b = self.load()["summary"]["BLIND_SYNTHETIC"]["E_CSIA"]
        r = b["root_cause_correct"]
        assert set(("num", "den", "rate", "ci95")) <= set(r)
        assert r["ci95"][0] <= r["rate"] <= r["ci95"][1]

    def test_manifest_is_complete(self):
        with open(RESULT) as fh:
            m = json.load(fh)["experiment_manifest"]
        for f in ("git_commit", "dataset_aggregate_hash", "csia_config_hash",
                  "trust_graph_config_hash", "threshold_config_hash"):
            assert m[f], f
        assert m["dataset_aggregate_hash"] == FROZEN_HASH
