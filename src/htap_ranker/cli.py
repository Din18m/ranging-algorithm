"""Command-line entry point for synthetic experiments and re-ranking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import (
    load_candidates,
    load_measurements,
    load_profile,
    save_measurements,
    save_ranking,
)
from .live_benchmark import (
    BenchmarkSettings,
    benchmark_environment,
    run_live_benchmark,
)
from .ranking import rank_candidates
from .simulation import simulate_candidate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htap-ranker",
        description="Benchmark and rank HTAP configurations against a workload profile.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run the simulator and rank candidates")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--candidates", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--repetitions", type=int, default=10)
    run.add_argument("--seed", type=int, default=42)

    rank = subparsers.add_parser("rank", help="rank existing measurements")
    rank.add_argument("--profile", type=Path, required=True)
    rank.add_argument("--measurements", type=Path, required=True)
    rank.add_argument("--output", type=Path, required=True)

    benchmark = subparsers.add_parser(
        "benchmark", help="measure SQLite, DuckDB and a split configuration"
    )
    benchmark.add_argument("--profile", type=Path, required=True)
    benchmark.add_argument("--output-dir", type=Path, required=True)
    benchmark.add_argument("--rows", type=int, default=50_000)
    benchmark.add_argument("--oltp-operations", type=int, default=200)
    benchmark.add_argument("--olap-queries", type=int, default=7)
    benchmark.add_argument("--repetitions", type=int, default=7)
    benchmark.add_argument("--seed", type=int, default=20261103)
    return parser


def _print_summary(ranking_path: Path, ranking: list) -> None:
    best = ranking[0]
    status = "meets all SLO" if best.feasible else "violates at least one SLO"
    print(f"Best configuration: {best.candidate} ({status})")
    print(f"Ranking saved to: {ranking_path}")


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    profile = load_profile(arguments.profile)

    if arguments.command == "run":
        candidates = load_candidates(arguments.candidates)
        measurements = []
        for candidate in candidates:
            measurements.extend(
                simulate_candidate(
                    candidate,
                    profile,
                    arguments.repetitions,
                    arguments.seed,
                )
            )
        measurements_path = arguments.output_dir / "measurements.json"
        ranking_path = arguments.output_dir / "ranking.csv"
        save_measurements(measurements_path, measurements)
    elif arguments.command == "benchmark":
        settings = BenchmarkSettings(
            rows=arguments.rows,
            oltp_operations=arguments.oltp_operations,
            olap_queries=arguments.olap_queries,
            repetitions=arguments.repetitions,
            seed=arguments.seed,
        )
        measurements = run_live_benchmark(settings)
        measurements_path = arguments.output_dir / "measurements.json"
        ranking_path = arguments.output_dir / "ranking.csv"
        save_measurements(measurements_path, measurements)
        environment_path = arguments.output_dir / "environment.json"
        environment_path.write_text(
            json.dumps(
                benchmark_environment(settings),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        measurements = load_measurements(arguments.measurements)
        ranking_path = arguments.output

    ranking = rank_candidates(measurements, profile)
    save_ranking(ranking_path, ranking)
    _print_summary(ranking_path, ranking)
    return 0
