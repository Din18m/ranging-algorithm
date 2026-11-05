import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "htap_ranker", *arguments],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_run_writes_measurements_and_ranking_reproducibly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            common = (
                "run",
                "--profile",
                "examples/profiles/balanced.json",
                "--candidates",
                "examples/candidates.json",
                "--repetitions",
                "3",
                "--seed",
                "11",
            )

            first_run = self.run_cli(*common, "--output-dir", str(first))
            second_run = self.run_cli(*common, "--output-dir", str(second))

            self.assertEqual(first_run.returncode, 0, first_run.stderr)
            self.assertEqual(second_run.returncode, 0, second_run.stderr)
            self.assertIn("Best configuration:", first_run.stdout)
            self.assertEqual(
                (first / "measurements.json").read_bytes(),
                (second / "measurements.json").read_bytes(),
            )
            self.assertEqual(
                (first / "ranking.csv").read_bytes(),
                (second / "ranking.csv").read_bytes(),
            )

            measurements = json.loads(
                (first / "measurements.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(measurements), 12)
            with (first / "ranking.csv").open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["rank"], "1")
            self.assertIn("stability_penalty", rows[0])

    def test_rank_reuses_saved_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            run_result = self.run_cli(
                "run",
                "--profile",
                "examples/profiles/balanced.json",
                "--candidates",
                "examples/candidates.json",
                "--output-dir",
                str(output),
                "--repetitions",
                "2",
                "--seed",
                "5",
            )
            reranked = output / "reranked.csv"
            rank_result = self.run_cli(
                "rank",
                "--profile",
                "examples/profiles/balanced.json",
                "--measurements",
                str(output / "measurements.json"),
                "--output",
                str(reranked),
            )

            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertEqual(rank_result.returncode, 0, rank_result.stderr)
            self.assertEqual(
                (output / "ranking.csv").read_bytes(), reranked.read_bytes()
            )

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "DuckDB is not installed")
    def test_benchmark_writes_live_measurements_and_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = self.run_cli(
                "benchmark",
                "--profile",
                "examples/profiles/balanced.json",
                "--output-dir",
                str(output),
                "--rows",
                "500",
                "--oltp-operations",
                "8",
                "--olap-queries",
                "2",
                "--repetitions",
                "1",
                "--seed",
                "19",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            measurements = json.loads(
                (output / "measurements.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(measurements), 3)
            self.assertTrue((output / "ranking.csv").is_file())
            environment = json.loads(
                (output / "environment.json").read_text(encoding="utf-8")
            )
            self.assertEqual(environment["settings"]["rows"], 500)
            self.assertIn("duckdb_version", environment)
            self.assertIn("sqlite_version", environment)


if __name__ == "__main__":
    unittest.main()
