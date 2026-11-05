import unittest
import math

from htap_ranker.models import Measurement, WorkloadProfile
from htap_ranker.ranking import aggregate_measurements, rank_candidates


def profile() -> WorkloadProfile:
    return WorkloadProfile(
        name="balanced",
        oltp_share=0.5,
        olap_share=0.5,
        arrival_rate=400.0,
        oltp_p99_slo_ms=100.0,
        olap_p95_slo_ms=1_000.0,
        freshness_slo_s=5.0,
        budget_per_hour=4.0,
    )


def measurement(
    candidate: str,
    repetition: int,
    oltp: float,
    olap: float,
    freshness: float,
    cost: float,
) -> Measurement:
    return Measurement(candidate, repetition, oltp, olap, freshness, cost)


class AggregationTests(unittest.TestCase):
    def test_variation_is_zero_for_identical_repetitions(self) -> None:
        aggregated = aggregate_measurements(
            [
                measurement("stable", 0, 80.0, 800.0, 3.0, 3.0),
                measurement("stable", 1, 80.0, 800.0, 3.0, 3.0),
            ]
        )["stable"]

        self.assertEqual(aggregated.repetitions, 2)
        self.assertEqual(aggregated.mean_variation, 0.0)
        self.assertEqual(aggregated.oltp_p99_ms, 80.0)

    def test_rejects_negative_and_non_finite_metrics(self) -> None:
        invalid_rows = [
            measurement("negative", 0, -1.0, 800.0, 3.0, 3.0),
            measurement("nan", 0, 80.0, math.nan, 3.0, 3.0),
            measurement("infinite", 0, 80.0, 800.0, math.inf, 3.0),
        ]

        for row in invalid_rows:
            with self.subTest(candidate=row.candidate):
                with self.assertRaisesRegex(ValueError, row.candidate):
                    aggregate_measurements([row])


class RankingTests(unittest.TestCase):
    def test_feasible_candidate_precedes_slo_violator(self) -> None:
        results = rank_candidates(
            [
                measurement("feasible", 0, 90.0, 900.0, 4.0, 3.5),
                measurement("violator", 0, 101.0, 300.0, 1.0, 1.0),
            ],
            profile(),
        )

        self.assertEqual([item.candidate for item in results], ["feasible", "violator"])
        self.assertTrue(results[0].feasible)
        self.assertFalse(results[1].feasible)
        self.assertGreater(results[1].violation_penalty, 0.0)

    def test_variability_penalty_breaks_equal_mean_in_favor_of_stable_candidate(self) -> None:
        results = rank_candidates(
            [
                measurement("stable", 0, 80.0, 800.0, 3.0, 3.0),
                measurement("stable", 1, 80.0, 800.0, 3.0, 3.0),
                measurement("volatile", 0, 60.0, 600.0, 2.0, 2.0),
                measurement("volatile", 1, 100.0, 1_000.0, 4.0, 4.0),
            ],
            profile(),
        )

        self.assertEqual(results[0].candidate, "stable")
        self.assertGreater(results[1].stability_penalty, results[0].stability_penalty)

    def test_dominated_candidate_is_assigned_to_later_pareto_layer(self) -> None:
        results = rank_candidates(
            [
                measurement("dominant", 0, 50.0, 500.0, 2.0, 2.0),
                measurement("dominated", 0, 75.0, 750.0, 3.0, 3.0),
            ],
            profile(),
        )

        layers = {item.candidate: item.pareto_layer for item in results}
        self.assertEqual(layers, {"dominant": 1, "dominated": 2})

    def test_identical_candidates_are_ordered_by_name(self) -> None:
        results = rank_candidates(
            [
                measurement("zeta", 0, 80.0, 800.0, 3.0, 3.0),
                measurement("alpha", 0, 80.0, 800.0, 3.0, 3.0),
            ],
            profile(),
        )

        self.assertEqual([item.candidate for item in results], ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
