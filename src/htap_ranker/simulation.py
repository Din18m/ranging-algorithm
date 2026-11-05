"""Small deterministic simulator for mixed HTAP workloads."""

from __future__ import annotations

import random

from .models import Candidate, Measurement, WorkloadProfile


def simulate_candidate(
    candidate: Candidate,
    profile: WorkloadProfile,
    repetitions: int,
    seed: int,
) -> list[Measurement]:
    """Produce repeatable synthetic metrics for one configuration."""
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    if candidate.cpu_cores <= 0 or candidate.memory_gb <= 0:
        raise ValueError("candidate resources must be positive")
    if candidate.oltp_efficiency <= 0 or candidate.olap_efficiency <= 0:
        raise ValueError("candidate efficiencies must be positive")
    if not 0.0 <= candidate.isolation <= 1.0:
        raise ValueError("candidate isolation must be between 0 and 1")

    share_total = profile.oltp_share + profile.olap_share
    oltp_fraction = profile.oltp_share / share_total
    olap_fraction = profile.olap_share / share_total
    memory_factor = 0.60 + 0.40 * min(candidate.memory_gb / 64.0, 1.0)
    capacity = candidate.cpu_cores * memory_factor

    oltp_pressure = (
        profile.arrival_rate * oltp_fraction
        / (capacity * candidate.oltp_efficiency)
    )
    olap_pressure = (
        profile.arrival_rate * olap_fraction
        / (capacity * candidate.olap_efficiency)
    )
    oltp_base = 15.0 + 1.60 * oltp_pressure * (
        1.0 + 1.20 * olap_fraction * (1.0 - candidate.isolation)
    )
    olap_base = 180.0 + 16.0 * olap_pressure * (
        1.0 + 1.50 * oltp_fraction * (1.0 - candidate.isolation)
    )
    freshness_base = candidate.sync_interval_s + (
        0.01 * oltp_pressure * (1.0 - candidate.isolation)
    )

    rng = random.Random(f"{seed}:{candidate.name}:{profile.name}")
    performance_sigma = 0.03 + 0.08 * (1.0 - candidate.isolation)
    measurements: list[Measurement] = []
    for repetition in range(repetitions):
        oltp_noise = max(0.65, rng.gauss(1.0, performance_sigma))
        olap_noise = max(0.65, rng.gauss(1.0, performance_sigma * 1.15))
        freshness_noise = max(0.75, rng.gauss(1.0, 0.04))
        measurements.append(
            Measurement(
                candidate=candidate.name,
                repetition=repetition,
                oltp_p99_ms=oltp_base * oltp_noise,
                olap_p95_ms=olap_base * olap_noise,
                freshness_lag_s=freshness_base * freshness_noise,
                hourly_cost=candidate.hourly_cost,
            )
        )
    return measurements
