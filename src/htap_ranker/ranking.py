"""Requirement-aware and stability-aware ranking of measured candidates."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from itertools import groupby

from .models import CriterionWeights, Measurement, WorkloadProfile
from .weights import derive_weights


@dataclass(frozen=True, slots=True)
class AggregatedMeasurement:
    candidate: str
    repetitions: int
    oltp_p99_ms: float
    olap_p95_ms: float
    freshness_lag_s: float
    hourly_cost: float
    mean_variation: float

    @property
    def criteria(self) -> tuple[float, float, float, float]:
        return (
            self.oltp_p99_ms,
            self.olap_p95_ms,
            self.freshness_lag_s,
            self.hourly_cost,
        )


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    rank: int
    candidate: str
    feasible: bool
    pareto_layer: int
    score: float
    base_score: float
    stability_penalty: float
    violation_penalty: float
    metrics: AggregatedMeasurement


def _coefficient_of_variation(values: list[float]) -> float:
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0 if all(value == 0 for value in values) else math.inf
    return statistics.pstdev(values) / abs(mean)


def aggregate_measurements(
    measurements: list[Measurement],
) -> dict[str, AggregatedMeasurement]:
    """Aggregate repeated measurements and estimate their relative spread."""
    if not measurements:
        raise ValueError("at least one measurement is required")
    metric_names = (
        "oltp_p99_ms",
        "olap_p95_ms",
        "freshness_lag_s",
        "hourly_cost",
    )
    for row in measurements:
        for metric_name in metric_names:
            value = getattr(row, metric_name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(
                    f"measurement for {row.candidate}: {metric_name} must be finite and non-negative"
                )

    grouped: dict[str, AggregatedMeasurement] = {}
    ordered = sorted(measurements, key=lambda item: item.candidate)
    for candidate, rows_iter in groupby(ordered, key=lambda item: item.candidate):
        rows = list(rows_iter)
        series = [
            [row.oltp_p99_ms for row in rows],
            [row.olap_p95_ms for row in rows],
            [row.freshness_lag_s for row in rows],
            [row.hourly_cost for row in rows],
        ]
        means = [statistics.fmean(values) for values in series]
        variations = [_coefficient_of_variation(values) for values in series]
        grouped[candidate] = AggregatedMeasurement(
            candidate=candidate,
            repetitions=len(rows),
            oltp_p99_ms=means[0],
            olap_p95_ms=means[1],
            freshness_lag_s=means[2],
            hourly_cost=means[3],
            mean_variation=statistics.fmean(variations),
        )
    return grouped


def _dominates(left: AggregatedMeasurement, right: AggregatedMeasurement) -> bool:
    pairs = tuple(zip(left.criteria, right.criteria, strict=True))
    return all(a <= b for a, b in pairs) and any(a < b for a, b in pairs)


def _pareto_layers(items: list[AggregatedMeasurement]) -> dict[str, int]:
    remaining = list(items)
    result: dict[str, int] = {}
    layer = 1
    while remaining:
        frontier = [
            item
            for item in remaining
            if not any(_dominates(other, item) for other in remaining if other != item)
        ]
        for item in frontier:
            result[item.candidate] = layer
        frontier_names = {item.candidate for item in frontier}
        remaining = [item for item in remaining if item.candidate not in frontier_names]
        layer += 1
    return result


def _score(
    metrics: AggregatedMeasurement,
    profile: WorkloadProfile,
    weights: CriterionWeights,
) -> tuple[bool, float, float, float]:
    ratios = (
        metrics.oltp_p99_ms / profile.oltp_p99_slo_ms,
        metrics.olap_p95_ms / profile.olap_p95_slo_ms,
        metrics.freshness_lag_s / profile.freshness_slo_s,
        metrics.hourly_cost / profile.budget_per_hour,
    )
    weight_values = (weights.oltp, weights.olap, weights.freshness, weights.cost)
    feasible = all(ratio <= 1.0 for ratio in ratios)
    base_score = math.exp(
        sum(weight * math.log(max(ratio, 1e-12)) for weight, ratio in zip(weight_values, ratios, strict=True))
    )
    stability_penalty = 0.25 * metrics.mean_variation
    violation_penalty = 10.0 * sum(
        weight * max(0.0, ratio - 1.0) ** 2
        for weight, ratio in zip(weight_values, ratios, strict=True)
    )
    return feasible, base_score, stability_penalty, violation_penalty


def rank_candidates(
    measurements: list[Measurement],
    profile: WorkloadProfile,
) -> list[RankedCandidate]:
    """Rank measured candidates using SLO, Pareto dominance and stability."""
    aggregated = aggregate_measurements(measurements)
    weights = derive_weights(profile)
    layers = _pareto_layers(list(aggregated.values()))

    rows: list[RankedCandidate] = []
    for candidate, metrics in aggregated.items():
        feasible, base_score, stability_penalty, violation_penalty = _score(
            metrics, profile, weights
        )
        rows.append(
            RankedCandidate(
                rank=0,
                candidate=candidate,
                feasible=feasible,
                pareto_layer=layers[candidate],
                score=base_score + stability_penalty + violation_penalty,
                base_score=base_score,
                stability_penalty=stability_penalty,
                violation_penalty=violation_penalty,
                metrics=metrics,
            )
        )

    rows.sort(
        key=lambda item: (
            not item.feasible,
            item.pareto_layer,
            item.score,
            item.candidate,
        )
    )
    return [
        RankedCandidate(
            rank=index,
            candidate=item.candidate,
            feasible=item.feasible,
            pareto_layer=item.pareto_layer,
            score=item.score,
            base_score=item.base_score,
            stability_penalty=item.stability_penalty,
            violation_penalty=item.violation_penalty,
            metrics=item.metrics,
        )
        for index, item in enumerate(rows, start=1)
    ]
