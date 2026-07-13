"""Unit tests: causal diagnosis (phase 3)."""

import numpy as np

from csia.diagnosis import CAUSES


def test_posterior_is_distribution(clean_run):
    _, _, _, _, diag = clean_run
    sums = diag.posterior.sum(axis=1)
    np.testing.assert_allclose(sums, 1.0, atol=1e-9)
    assert (diag.posterior >= 0.0).all()


def test_clean_flight_reads_nominal(clean_run):
    _, _, _, _, diag = clean_run
    nominal = diag.causes.index("nominal")
    assert diag.posterior[250:, nominal].min() > 0.90


def test_cause_table_features_exist(clean_run):
    """Every feature named in CAUSES must actually be produced by the
    comparator — a renamed edge would otherwise silently blind a cause."""
    _, _, td, _, _ = clean_run
    available = set(td.edges) | {f"phys_{n}" for n in td.physics} \
        | {f"temp_{n}" for n in td.hist}
    for cause, feats in CAUSES.items():
        missing = set(feats) - available
        assert not missing, f"{cause} references unknown features {missing}"
