import unittest

from htap_ranker.models import Candidate, WorkloadProfile
from htap_ranker.simulation import simulate_candidate


def candidate() -> Candidate:
    return Candidate(
        name="hybrid",
        architecture="hybrid_store",
        cpu_cores=8,
        memory_gb=32.0,
        oltp_efficiency=1.0,
        olap_efficiency=1.0,
        isolation=0.7,
        sync_interval_s=0.5,
        hourly_cost=5.0,
    )


def workload(name: str, oltp: float, olap: float) -> WorkloadProfile:
    return WorkloadProfile(
        name=name,
        oltp_share=oltp,
        olap_share=olap,
        arrival_rate=500.0,
        oltp_p99_slo_ms=150.0,
        olap_p95_slo_ms=2_000.0,
        freshness_slo_s=5.0,
        budget_per_hour=8.0,
    )


class SimulationTests(unittest.TestCase):
    def test_same_seed_reproduces_every_measurement(self) -> None:
        first = simulate_candidate(candidate(), workload("balanced", 0.5, 0.5), 4, 17)
        second = simulate_candidate(candidate(), workload("balanced", 0.5, 0.5), 4, 17)

        self.assertEqual(first, second)
        self.assertEqual([row.repetition for row in first], [0, 1, 2, 3])

    def test_workload_mix_changes_the_loaded_side(self) -> None:
        transactional = simulate_candidate(
            candidate(), workload("transactional", 0.9, 0.1), 20, 23
        )
        analytical = simulate_candidate(
            candidate(), workload("analytical", 0.1, 0.9), 20, 23
        )

        transaction_latency = sum(row.oltp_p99_ms for row in transactional) / 20
        analytical_transaction_latency = sum(row.oltp_p99_ms for row in analytical) / 20
        analytical_latency = sum(row.olap_p95_ms for row in analytical) / 20
        transactional_analytical_latency = sum(row.olap_p95_ms for row in transactional) / 20

        self.assertGreater(transaction_latency, analytical_transaction_latency)
        self.assertGreater(analytical_latency, transactional_analytical_latency)

    def test_rejects_non_positive_repetition_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "repetitions"):
            simulate_candidate(candidate(), workload("balanced", 0.5, 0.5), 0, 1)


if __name__ == "__main__":
    unittest.main()
