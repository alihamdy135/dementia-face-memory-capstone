import unittest

from face_memory.metrics import evaluate_open_set, latency_summary, select_threshold


class OpenSetMetricsTests(unittest.TestCase):
    def setUp(self):
        self.true_ids = ["person-a", "person-a", None, None]
        self.candidate_ids = ["person-a", "person-b", "person-a", "person-a"]
        self.scores = [0.9, 0.8, 0.7, 0.4]

    def test_threshold_selection_uses_unknown_validation_queries(self):
        threshold = select_threshold(
            self.true_ids,
            self.candidate_ids,
            self.scores,
            max_unknown_fpir=0.5,
        )
        self.assertAlmostEqual(threshold, 0.9)

    def test_metrics_count_abstentions_as_wrong_for_known_identity(self):
        report = evaluate_open_set(
            self.true_ids,
            self.candidate_ids,
            self.scores,
            threshold=0.9,
        )
        self.assertAlmostEqual(report["overall_accuracy"], 0.75)
        self.assertAlmostEqual(report["known_top1_accuracy"], 0.5)
        self.assertAlmostEqual(report["unknown_fpir"], 0.0)
        self.assertAlmostEqual(report["unknown_rejection_recall"], 1.0)
        self.assertAlmostEqual(report["known_false_rejection_rate"], 0.5)
        self.assertAlmostEqual(report["coverage"], 0.25)

    def test_wrong_identity_is_not_counted_as_a_false_rejection(self):
        report = evaluate_open_set(
            self.true_ids,
            self.candidate_ids,
            self.scores,
            threshold=0.8,
        )
        self.assertAlmostEqual(report["known_false_rejection_rate"], 0.0)
        self.assertAlmostEqual(report["known_wrong_identity_rate"], 0.5)
        self.assertAlmostEqual(report["known_identification_failure_rate"], 0.5)

    def test_latency_summary_reports_median_and_tail(self):
        report = latency_summary([10.0, 20.0, 30.0, 40.0])
        self.assertEqual(report["count"], 4)
        self.assertAlmostEqual(report["mean_ms"], 25.0)
        self.assertAlmostEqual(report["median_ms"], 25.0)
        self.assertAlmostEqual(report["p95_ms"], 40.0)
        self.assertAlmostEqual(report["max_ms"], 40.0)

    def test_threshold_calibration_requires_unknown_examples(self):
        with self.assertRaises(ValueError):
            select_threshold(["person-a"], ["person-a"], [0.9], max_unknown_fpir=0.05)

    def test_min_margin_rejects_close_top_two_identities(self):
        report = evaluate_open_set(
            ["person-a", None],
            ["person-a", "person-a"],
            [0.85, 0.82],
            threshold=0.8,
            margins=[0.01, 0.03],
            min_margin=0.02,
        )
        self.assertEqual(report["known_top1_accuracy"], 0.0)
        self.assertEqual(report["unknown_fpir"], 1.0)


if __name__ == "__main__":
    unittest.main()
