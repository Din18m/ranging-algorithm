"""Illustrative in-memory benchmark for SQLite, DuckDB and a split setup."""

from __future__ import annotations

import math
import os
import platform
import random
import sqlite3
import time
from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .models import Measurement


@dataclass(frozen=True, slots=True)
class BenchmarkSettings:
    rows: int = 50_000
    oltp_operations: int = 200
    olap_queries: int = 7
    repetitions: int = 7
    seed: int = 20261103

    def __post_init__(self) -> None:
        for field_name in ("rows", "oltp_operations", "olap_queries", "repetitions"):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")


def nearest_rank_percentile(values: list[float], percentile: float) -> float:
    """Return an observed value using the nearest-rank definition."""
    if not values:
        raise ValueError("sample must not be empty")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    rank = math.ceil(percentile * len(ordered))
    return ordered[rank - 1]


def _load_duckdb() -> Any:
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError(
            "DuckDB is required for the live benchmark; install htap-ranker[benchmark]"
        ) from error
    return duckdb


def benchmark_environment(settings: BenchmarkSettings) -> dict[str, Any]:
    """Describe the runtime used for a saved benchmark result."""
    cpu_model = platform.processor() or "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    memory_bytes = None
    if hasattr(os, "sysconf"):
        try:
            memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (OSError, ValueError):
            memory_bytes = None
    duckdb = _load_duckdb()
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "logical_cpus": os.cpu_count(),
        "memory_bytes": memory_bytes,
        "sqlite_version": sqlite3.sqlite_version,
        "duckdb_version": duckdb.__version__,
        "settings": asdict(settings),
    }


def _create_sqlite(rows: int) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            region INTEGER NOT NULL,
            product INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        WITH RECURSIVE seq(i) AS (
            SELECT 1
            UNION ALL
            SELECT i + 1 FROM seq WHERE i < ?
        )
        INSERT INTO orders
        SELECT i, i % 1000, i % 16, i % 128,
               ((i * 37) % 10000) / 100.0 + 1.0,
               1700000000 + i
        FROM seq
        """,
        (rows,),
    )
    return connection


def _create_duckdb(rows: int) -> Any:
    duckdb = _load_duckdb()
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads = 1")
    connection.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            region INTEGER NOT NULL,
            product INTEGER NOT NULL,
            amount DOUBLE NOT NULL,
            created_at BIGINT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO orders
        SELECT i::INTEGER, (i % 1000)::INTEGER, (i % 16)::INTEGER,
               (i % 128)::INTEGER, ((i * 37) % 10000) / 100.0 + 1.0,
               1700000000 + i
        FROM range(1, {rows + 1}) AS source(i)
        """
    )
    return connection


def _operation_ids(settings: BenchmarkSettings, repetition: int) -> list[int]:
    generator = random.Random(settings.seed + repetition)
    return [generator.randint(1, settings.rows) for _ in range(settings.oltp_operations)]


def _measure_updates(connection: Any, identifiers: list[int]) -> list[float]:
    latencies: list[float] = []
    for identifier in identifiers:
        started = time.perf_counter_ns()
        connection.execute(
            "UPDATE orders SET amount = amount + 0.01 WHERE id = ?",
            (identifier,),
        )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(elapsed_ms)
    return latencies


_ANALYTICAL_QUERY = """
SELECT region, product, SUM(amount) AS revenue, COUNT(*) AS order_count
FROM orders
GROUP BY region, product
ORDER BY revenue DESC
LIMIT 20
"""


def _measure_analytics(connection: Any, queries: int) -> list[float]:
    connection.execute(_ANALYTICAL_QUERY).fetchall()
    latencies: list[float] = []
    for _ in range(queries):
        started = time.perf_counter_ns()
        connection.execute(_ANALYTICAL_QUERY).fetchall()
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(elapsed_ms)
    return latencies


def _measure_single_store(
    name: str,
    factory: Callable[[int], Any],
    settings: BenchmarkSettings,
    repetition: int,
    resource_cost: float,
) -> Measurement:
    connection = factory(settings.rows)
    try:
        identifiers = _operation_ids(settings, repetition)
        oltp = _measure_updates(connection, identifiers)
        visibility_started = time.perf_counter_ns()
        connection.execute(
            "SELECT amount FROM orders WHERE id = ?", (identifiers[-1],)
        ).fetchone()
        freshness_lag_s = (
            time.perf_counter_ns() - visibility_started
        ) / 1_000_000_000
        olap = _measure_analytics(connection, settings.olap_queries)
        return Measurement(
            candidate=name,
            repetition=repetition,
            oltp_p99_ms=nearest_rank_percentile(oltp, 0.99),
            olap_p95_ms=nearest_rank_percentile(olap, 0.95),
            freshness_lag_s=freshness_lag_s,
            hourly_cost=resource_cost,
        )
    finally:
        connection.close()


def _measure_split_store(
    settings: BenchmarkSettings,
    repetition: int,
) -> Measurement:
    transaction_store = _create_sqlite(settings.rows)
    analytical_store = _create_duckdb(settings.rows)
    try:
        identifiers = _operation_ids(settings, repetition)
        oltp = _measure_updates(transaction_store, identifiers)

        sync_started = time.perf_counter_ns()
        unique_ids = sorted(set(identifiers))
        placeholders = ",".join("?" for _ in unique_ids)
        changed_rows = transaction_store.execute(
            f"SELECT id, amount FROM orders WHERE id IN ({placeholders})",
            unique_ids,
        ).fetchall()
        analytical_store.execute("BEGIN TRANSACTION")
        analytical_store.executemany(
            "UPDATE orders SET amount = ? WHERE id = ?",
            [(amount, identifier) for identifier, amount in changed_rows],
        )
        analytical_store.execute("COMMIT")
        analytical_store.execute(
            "SELECT amount FROM orders WHERE id = ?", (identifiers[-1],)
        ).fetchone()
        freshness_lag_s = (time.perf_counter_ns() - sync_started) / 1_000_000_000

        olap = _measure_analytics(analytical_store, settings.olap_queries)
        return Measurement(
            candidate="sqlite_duckdb",
            repetition=repetition,
            oltp_p99_ms=nearest_rank_percentile(oltp, 0.99),
            olap_p95_ms=nearest_rank_percentile(olap, 0.95),
            freshness_lag_s=freshness_lag_s,
            hourly_cost=2.0,
        )
    finally:
        transaction_store.close()
        analytical_store.close()


def run_live_benchmark(settings: BenchmarkSettings) -> list[Measurement]:
    """Measure all three illustrative storage configurations."""
    measurements: list[Measurement] = []
    for repetition in range(settings.repetitions):
        measurements.append(
            _measure_single_store(
                "sqlite", _create_sqlite, settings, repetition, resource_cost=1.0
            )
        )
        measurements.append(
            _measure_single_store(
                "duckdb", _create_duckdb, settings, repetition, resource_cost=1.2
            )
        )
        measurements.append(_measure_split_store(settings, repetition))
    return measurements
