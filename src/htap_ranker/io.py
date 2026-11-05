"""JSON and CSV boundaries for the command-line interface."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import Candidate, Measurement, WorkloadProfile
from .ranking import RankedCandidate


def load_profile(path: Path) -> WorkloadProfile:
    return WorkloadProfile(**json.loads(path.read_text(encoding="utf-8")))


def load_candidates(path: Path) -> list[Candidate]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidates file must contain a non-empty JSON array")
    return [Candidate(**row) for row in rows]


def save_measurements(path: Path, measurements: list[Measurement]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(item) for item in measurements]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_measurements(path: Path) -> list[Measurement]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("measurements file must contain a non-empty JSON array")
    return [Measurement(**row) for row in rows]


def save_ranking(path: Path, ranking: list[RankedCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "candidate",
        "feasible",
        "pareto_layer",
        "score",
        "base_score",
        "stability_penalty",
        "violation_penalty",
        "oltp_p99_ms",
        "olap_p95_ms",
        "freshness_lag_s",
        "hourly_cost",
        "repetitions",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in ranking:
            writer.writerow(
                {
                    "rank": item.rank,
                    "candidate": item.candidate,
                    "feasible": str(item.feasible).lower(),
                    "pareto_layer": item.pareto_layer,
                    "score": f"{item.score:.6f}",
                    "base_score": f"{item.base_score:.6f}",
                    "stability_penalty": f"{item.stability_penalty:.6f}",
                    "violation_penalty": f"{item.violation_penalty:.6f}",
                    "oltp_p99_ms": f"{item.metrics.oltp_p99_ms:.3f}",
                    "olap_p95_ms": f"{item.metrics.olap_p95_ms:.3f}",
                    "freshness_lag_s": f"{item.metrics.freshness_lag_s:.3f}",
                    "hourly_cost": f"{item.metrics.hourly_cost:.3f}",
                    "repetitions": item.metrics.repetitions,
                }
            )
