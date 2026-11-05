"""Sensitivity analysis over selected service-level objectives."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path

from .models import Measurement, WorkloadProfile
from .ranking import rank_candidates


@dataclass(frozen=True, slots=True)
class SensitivityRow:
    olap_slo_ms: float
    freshness_slo_s: float
    winner: str
    winner_feasible: bool
    feasible_candidates: int
    winner_score: float


def sensitivity_grid(
    measurements: list[Measurement],
    profile: WorkloadProfile,
    olap_slos_ms: list[float],
    freshness_slos_s: list[float],
) -> list[SensitivityRow]:
    """Re-rank the same measurements over a rectangular SLO grid."""
    if not olap_slos_ms or not freshness_slos_s:
        raise ValueError("sensitivity axes must not be empty")
    if any(value <= 0 for value in (*olap_slos_ms, *freshness_slos_s)):
        raise ValueError("sensitivity SLO values must be positive")

    rows: list[SensitivityRow] = []
    for olap_slo in olap_slos_ms:
        for freshness_slo in freshness_slos_s:
            varied = replace(
                profile,
                olap_p95_slo_ms=olap_slo,
                freshness_slo_s=freshness_slo,
            )
            ranking = rank_candidates(measurements, varied)
            winner = ranking[0]
            rows.append(
                SensitivityRow(
                    olap_slo_ms=olap_slo,
                    freshness_slo_s=freshness_slo,
                    winner=winner.candidate,
                    winner_feasible=winner.feasible,
                    feasible_candidates=sum(item.feasible for item in ranking),
                    winner_score=winner.score,
                )
            )
    return rows


def save_sensitivity(path: Path, rows: list[SensitivityRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "olap_slo_ms",
                "freshness_slo_s",
                "winner",
                "winner_feasible",
                "feasible_candidates",
                "winner_score",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    f"{row.olap_slo_ms:.3f}",
                    f"{row.freshness_slo_s:.3f}",
                    row.winner,
                    str(row.winner_feasible).lower(),
                    row.feasible_candidates,
                    f"{row.winner_score:.6f}",
                ]
            )
