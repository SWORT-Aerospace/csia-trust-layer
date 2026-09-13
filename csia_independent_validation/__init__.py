"""Independent validation of the realized-current excitation certificate.

This package exists because the previous phase conflated three roles in one
module tree: the thing that decides whether to act, the thing that decides
whether the action worked, and the thing that decides whether the experiment
was run honestly. When the same code plays all three parts, "zero false
certificates" can be true and mean nothing.

The separation this package enforces:

``Layer A`` -- the deployable certificate. Lives in :mod:`csia_active_evidence`
    and is *not* changed here. It sees commands, telemetry, declared envelopes
    and hashes. It never sees truth.

``Layer B`` -- the independent outcome evaluator, here. Offline. It may see
    simulator ground truth. It must not import Layer A's resolution-margin
    function, because an evaluator that reuses the certificate's own error
    budget cannot falsify the certificate.

``Layer C`` -- the experimental auditor, here. It checks partitions, streams,
    cost matching, leakage and whether the conclusions follow from the
    preregistered metrics.

NOTHING IN THIS PACKAGE PROMOTES ANYTHING. It is simulator research on a
quarantined branch, post-freeze, and it is not a safety artifact.
"""
from __future__ import annotations

__all__ = ["partitions"]
