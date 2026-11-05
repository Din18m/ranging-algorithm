"""Translate a workload profile into criterion weights."""

from __future__ import annotations

from .models import CriterionWeights, WorkloadProfile


def derive_weights(profile: WorkloadProfile) -> CriterionWeights:
    """Derive normalized weights while retaining every quality dimension."""
    share_total = profile.oltp_share + profile.olap_share
    oltp_fraction = profile.oltp_share / share_total
    olap_fraction = profile.olap_share / share_total

    pressure = min(profile.arrival_rate / 1_000.0, 1.0)
    freshness_pressure = 1.0 / (1.0 + profile.freshness_slo_s / 10.0)
    budget_pressure = 1.0 / (1.0 + profile.budget_per_hour / 10.0)

    raw = (
        0.10 + 0.65 * oltp_fraction + 0.15 * pressure,
        0.10 + 0.65 * olap_fraction + 0.10 * pressure,
        0.10 + 0.25 * olap_fraction + 0.30 * freshness_pressure,
        0.10 + 0.30 * budget_pressure,
    )
    total = sum(raw)
    return CriterionWeights(*(value / total for value in raw))
