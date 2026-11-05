"""Conversion helpers for BenchBase CH-benCHmark result files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .live_benchmark import nearest_rank_percentile

OLTP_TRANSACTION_NAMES = {
    "NewOrder",
    "Payment",
    "OrderStatus",
    "Delivery",
    "StockLevel",
}
OLAP_TRANSACTION_NAMES = {f"Q{number}" for number in range(1, 23)}


def summarize_benchbase_run(raw_path: Path, summary_path: Path) -> dict[str, Any]:
    """Return the mixed-workload metrics used in the article.

    BenchBase stores raw latency values in microseconds. Transaction names
    Q1 through Q22 belong to the analytical CH-benCHmark workload; the other
    names in a composite TPCC/CH-benCHmark run belong to TPC-C.
    """

    oltp_latencies_ms: list[float] = []
    olap_latencies_ms: list[float] = []
    with raw_path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            name = row["Transaction Name"].strip()
            latency_ms = float(row["Latency (microseconds)"]) / 1000.0
            if name in OLAP_TRANSACTION_NAMES:
                olap_latencies_ms.append(latency_ms)
            elif name in OLTP_TRANSACTION_NAMES:
                oltp_latencies_ms.append(latency_ms)
            else:
                raise ValueError(f"unknown BenchBase transaction name: {name}")

    if not oltp_latencies_ms or not olap_latencies_ms:
        raise ValueError("BenchBase run must contain both OLTP and OLAP requests")

    metadata = json.loads(summary_path.read_text(encoding="utf-8"))
    if metadata.get("Final State") != "EXIT":
        raise ValueError("BenchBase run did not finish successfully")

    return {
        "dbms_type": metadata["DBMS Type"],
        "dbms_version": metadata["DBMS Version"],
        "elapsed_s": metadata["Elapsed Time (nanoseconds)"] / 1_000_000_000,
        "throughput_rps": float(metadata["Throughput (requests/second)"]),
        "oltp_requests": len(oltp_latencies_ms),
        "olap_requests": len(olap_latencies_ms),
        "oltp_p99_ms": nearest_rank_percentile(oltp_latencies_ms, 0.99),
        "olap_p95_ms": nearest_rank_percentile(olap_latencies_ms, 0.95),
    }
