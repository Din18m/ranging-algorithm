import unittest

from htap_ranker.models import WorkloadProfile
from htap_ranker.weights import derive_weights


class WorkloadProfileTests(unittest.TestCase):
    def test_rejects_non_positive_service_level_objective(self) -> None:
        with self.assertRaisesRegex(ValueError, "oltp_p99_slo_ms"):
            WorkloadProfile(
                name="broken",
                oltp_share=0.7,
                olap_share=0.3,
                arrival_rate=100.0,
                oltp_p99_slo_ms=0.0,
                olap_p95_slo_ms=2_000.0,
                freshness_slo_s=5.0,
                budget_per_hour=3.0,
            )

    def test_rejects_profile_without_any_workload(self) -> None:
        with self.assertRaisesRegex(ValueError, "workload share"):
            WorkloadProfile(
                name="empty",
                oltp_share=0.0,
                olap_share=0.0,
                arrival_rate=100.0,
                oltp_p99_slo_ms=100.0,
                olap_p95_slo_ms=2_000.0,
                freshness_slo_s=5.0,
                budget_per_hour=3.0,
            )


class WeightDerivationTests(unittest.TestCase):
    def make_profile(self, oltp_share: float, olap_share: float) -> WorkloadProfile:
        return WorkloadProfile(
            name="profile",
            oltp_share=oltp_share,
            olap_share=olap_share,
            arrival_rate=500.0,
            oltp_p99_slo_ms=100.0,
            olap_p95_slo_ms=2_000.0,
            freshness_slo_s=5.0,
            budget_per_hour=3.0,
        )

    def test_analytical_profile_keeps_all_weights_positive(self) -> None:
        weights = derive_weights(self.make_profile(0.0, 1.0))

        self.assertAlmostEqual(weights.total, 1.0)
        self.assertGreater(weights.oltp, 0.0)
        self.assertGreater(weights.olap, weights.oltp)
        self.assertGreater(weights.freshness, 0.0)
        self.assertGreater(weights.cost, 0.0)

    def test_dominant_workload_receives_greater_performance_weight(self) -> None:
        transactional = derive_weights(self.make_profile(0.9, 0.1))
        analytical = derive_weights(self.make_profile(0.1, 0.9))

        self.assertGreater(transactional.oltp, transactional.olap)
        self.assertGreater(analytical.olap, analytical.oltp)


if __name__ == "__main__":
    unittest.main()
