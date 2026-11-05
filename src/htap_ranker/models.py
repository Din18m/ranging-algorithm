"""Domain models shared by the simulator and ranking algorithm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkloadProfile:
    name: str
    oltp_share: float
    olap_share: float
    arrival_rate: float
    oltp_p99_slo_ms: float
    olap_p95_slo_ms: float
    freshness_slo_s: float
    budget_per_hour: float

    def __post_init__(self) -> None:
        for field_name in (
            "oltp_p99_slo_ms",
            "olap_p95_slo_ms",
            "freshness_slo_s",
            "budget_per_hour",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.arrival_rate <= 0:
            raise ValueError("arrival_rate must be positive")
        if self.oltp_share < 0 or self.olap_share < 0:
            raise ValueError("workload shares cannot be negative")
        if self.oltp_share + self.olap_share <= 0:
            raise ValueError("at least one workload share must be positive")


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    architecture: str
    cpu_cores: int
    memory_gb: float
    oltp_efficiency: float
    olap_efficiency: float
    isolation: float
    sync_interval_s: float
    hourly_cost: float


@dataclass(frozen=True, slots=True)
class Measurement:
    candidate: str
    repetition: int
    oltp_p99_ms: float
    olap_p95_ms: float
    freshness_lag_s: float
    hourly_cost: float


@dataclass(frozen=True, slots=True)
class CriterionWeights:
    oltp: float
    olap: float
    freshness: float
    cost: float

    @property
    def total(self) -> float:
        return self.oltp + self.olap + self.freshness + self.cost
