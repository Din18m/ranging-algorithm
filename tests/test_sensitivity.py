import unittest

from htap_ranker.models import Measurement, WorkloadProfile
from htap_ranker.sensitivity import sensitivity_grid


class SensitivityTests(unittest.TestCase):
    def test_grid_records_winner_and_feasibility_for_each_pair(self) -> None:
        profile = WorkloadProfile(
            name="base",
            oltp_share=0.5,
            olap_share=0.5,
            arrival_rate=100.0,
            oltp_p99_slo_ms=10.0,
            olap_p95_slo_ms=10.0,
            freshness_slo_s=1.0,
            budget_per_hour=2.0,
        )
        measurements = [
            Measurement("fast_analytics", 0, 5.0, 2.0, 0.8, 1.5),
            Measurement("cheap", 0, 5.0, 8.0, 0.1, 1.0),
        ]

        rows = sensitivity_grid(
            measurements,
            profile,
            olap_slos_ms=[3.0, 10.0],
            freshness_slos_s=[0.5, 1.0],
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {(row.olap_slo_ms, row.freshness_slo_s) for row in rows},
            {(3.0, 0.5), (3.0, 1.0), (10.0, 0.5), (10.0, 1.0)},
        )
        self.assertTrue(all(row.winner in {"fast_analytics", "cheap"} for row in rows))


if __name__ == "__main__":
    unittest.main()
