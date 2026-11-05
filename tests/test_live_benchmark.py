import importlib.util
import unittest

from htap_ranker.live_benchmark import (
    BenchmarkSettings,
    nearest_rank_percentile,
    run_live_benchmark,
)


class PercentileTests(unittest.TestCase):
    def test_nearest_rank_uses_observed_value(self) -> None:
        values = [4.0, 1.0, 3.0, 2.0]

        self.assertEqual(nearest_rank_percentile(values, 0.50), 2.0)
        self.assertEqual(nearest_rank_percentile(values, 0.95), 4.0)

    def test_percentile_rejects_empty_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample"):
            nearest_rank_percentile([], 0.99)


@unittest.skipUnless(importlib.util.find_spec("duckdb"), "DuckDB is not installed")
class LiveBenchmarkTests(unittest.TestCase):
    def test_small_run_measures_all_three_configurations(self) -> None:
        measurements = run_live_benchmark(
            BenchmarkSettings(
                rows=500,
                oltp_operations=8,
                olap_queries=2,
                repetitions=2,
                seed=17,
            )
        )

        self.assertEqual(len(measurements), 6)
        self.assertEqual(
            {row.candidate for row in measurements},
            {"sqlite", "duckdb", "sqlite_duckdb"},
        )
        for candidate in ("sqlite", "duckdb", "sqlite_duckdb"):
            rows = [row for row in measurements if row.candidate == candidate]
            self.assertEqual([row.repetition for row in rows], [0, 1])
            self.assertTrue(all(row.oltp_p99_ms > 0 for row in rows))
            self.assertTrue(all(row.olap_p95_ms > 0 for row in rows))

        self.assertTrue(all(row.freshness_lag_s > 0 for row in measurements))


if __name__ == "__main__":
    unittest.main()
