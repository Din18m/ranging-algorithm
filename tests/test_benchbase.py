import json
import tempfile
import unittest
from pathlib import Path
from statistics import median

from htap_ranker.benchbase import summarize_benchbase_run


class BenchBaseParserTests(unittest.TestCase):
    def test_summarizes_tpcc_and_chbenchmark_latencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "run.raw.csv"
            summary_path = root / "run.summary.json"
            raw_path.write_text(
                "Transaction Type Index,Transaction Name,Start Time (microseconds),"
                "Latency (microseconds),Worker Id (start number),Phase Id (index in config file)\n"
                "1,NewOrder,1000000,1000,0,0\n"
                "2,Payment,1100000,3000,0,0\n"
                "3,Q1,1200000,10000,1,0\n"
                "4,Q6,1300000,20000,1,0\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "DBMS Type": "POSTGRES",
                        "DBMS Version": "17.6",
                        "Elapsed Time (nanoseconds)": 2_000_000_000,
                        "Throughput (requests/second)": 2.0,
                        "Final State": "EXIT",
                    }
                ),
                encoding="utf-8",
            )

            result = summarize_benchbase_run(raw_path, summary_path)

        self.assertEqual(result["dbms_type"], "POSTGRES")
        self.assertEqual(result["dbms_version"], "17.6")
        self.assertEqual(result["oltp_requests"], 2)
        self.assertEqual(result["olap_requests"], 2)
        self.assertEqual(result["oltp_p99_ms"], 3.0)
        self.assertEqual(result["olap_p95_ms"], 20.0)
        self.assertEqual(result["elapsed_s"], 2.0)
        self.assertEqual(result["throughput_rps"], 2.0)

    def test_rejects_run_without_both_workload_classes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "run.raw.csv"
            summary_path = root / "run.summary.json"
            raw_path.write_text(
                "Transaction Type Index,Transaction Name,Start Time (microseconds),"
                "Latency (microseconds),Worker Id (start number),Phase Id (index in config file)\n"
                "1,NewOrder,1000000,1000,0,0\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "DBMS Type": "POSTGRES",
                        "DBMS Version": "17.6",
                        "Elapsed Time (nanoseconds)": 1_000_000_000,
                        "Throughput (requests/second)": 1.0,
                        "Final State": "ENDED",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "OLTP and OLAP"):
                summarize_benchbase_run(raw_path, summary_path)

    def test_rejects_failed_benchbase_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "run.raw.csv"
            summary_path = root / "run.summary.json"
            raw_path.write_text(
                "Transaction Type Index,Transaction Name,Start Time (microseconds),"
                "Latency (microseconds),Worker Id (start number),Phase Id (index in config file)\n"
                "1,NewOrder,1000000,1000,0,0\n"
                "2,Q1,1100000,2000,1,0\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "DBMS Type": "POSTGRES",
                        "DBMS Version": "17.6",
                        "Elapsed Time (nanoseconds)": 1_000_000_000,
                        "Throughput (requests/second)": 2.0,
                        "Final State": "ERROR",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "finish successfully"):
                summarize_benchbase_run(raw_path, summary_path)

    def test_rejects_unknown_transaction_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "run.raw.csv"
            summary_path = root / "run.summary.json"
            raw_path.write_text(
                "Transaction Type Index,Transaction Name,Start Time (microseconds),"
                "Latency (microseconds),Worker Id (start number),Phase Id (index in config file)\n"
                "1,NewOrder,1000000,1000,0,0\n"
                "2,Q1,1100000,2000,1,0\n"
                "3,UnknownQuery,1200000,3000,1,0\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "DBMS Type": "POSTGRES",
                        "DBMS Version": "17.6",
                        "Elapsed Time (nanoseconds)": 1_000_000_000,
                        "Throughput (requests/second)": 3.0,
                        "Final State": "EXIT",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "UnknownQuery"):
                summarize_benchbase_run(raw_path, summary_path)

    def test_checked_in_summary_matches_raw_runs(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result_root = project_root / "results" / "benchbase"
        expected = json.loads(
            (result_root / "summary.json").read_text(encoding="utf-8")
        )
        runs = []
        for repetition in range(1, 4):
            raw_path = result_root / "raw" / f"run-{repetition}.raw.csv"
            summary_path = result_root / "raw" / f"run-{repetition}.summary.json"
            runs.append(summarize_benchbase_run(raw_path, summary_path))

        self.assertEqual(expected["repetition_count"], 3)
        for actual, saved in zip(runs, expected["runs"], strict=True):
            for field in (
                "elapsed_s",
                "throughput_rps",
                "oltp_requests",
                "olap_requests",
                "oltp_p99_ms",
                "olap_p95_ms",
            ):
                self.assertEqual(actual[field], saved[field])
        self.assertEqual(
            expected["metrics"]["median_oltp_p99_ms"],
            median(row["oltp_p99_ms"] for row in runs),
        )
        self.assertEqual(
            expected["metrics"]["median_olap_p95_ms"],
            median(row["olap_p95_ms"] for row in runs),
        )
        self.assertEqual(
            expected["metrics"]["median_throughput_rps"],
            median(row["throughput_rps"] for row in runs),
        )


if __name__ == "__main__":
    unittest.main()
